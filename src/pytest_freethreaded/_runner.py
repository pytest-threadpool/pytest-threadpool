"""Parallel test runner orchestration."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from _pytest.runner import CallInfo, call_and_report, show_test_item

from ._fixtures import FixtureManager
from ._grouping import GroupKeyBuilder


class ParallelRunner:
    """Orchestrates parallel test execution.

    Groups consecutive items by parallel group key and runs each group
    either sequentially (key is None or single item) or in parallel.
    """

    def __init__(self, session, nthreads: int):
        self._session = session
        self._nthreads = nthreads

    def run_all(self) -> bool:
        """Main entry: group items and run each group."""
        session = self._session

        if (
            session.testsfailed
            and not session.config.option.continue_on_collection_errors
        ):
            raise session.Interrupted(
                "%d error%s during collection"
                % (session.testsfailed, "s" if session.testsfailed != 1 else "")
            )

        if session.config.option.collectonly:
            return True

        groups = GroupKeyBuilder.build_groups(session.items)

        for group_key, items in groups:
            if session.shouldfail:
                raise session.Failed(session.shouldfail)
            if session.shouldstop:
                raise session.Interrupted(session.shouldstop)

            if group_key is None or len(items) <= 1 or self._nthreads <= 1:
                for i, item in enumerate(items):
                    nextitem = items[i + 1] if i + 1 < len(items) else None
                    self._run_sequential(item, nextitem)
            else:
                self._run_parallel(items)

        return True

    def _run_sequential(self, item, nextitem) -> None:
        """Run the full default protocol for a single item."""
        ihook = item.ihook
        ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)

        if hasattr(item, "_request") and not item._request:
            item._initrequest()

        rep_setup = call_and_report(item, "setup", log=True)
        if rep_setup.passed:
            if item.config.getoption("setupshow", False):
                show_test_item(item)
            if not item.config.getoption("setuponly", False):
                call_and_report(item, "call", log=True)
        call_and_report(item, "teardown", log=True, nextitem=nextitem)

        if hasattr(item, "_request"):
            item._request = False
            item.funcargs = None

        ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)

    def _run_parallel(self, items) -> None:
        """Run a group's tests with parallel call phases.

        1. Sequential: setup every item (no reporting yet).
        2. Parallel:   item.runtest() in a thread pool.
        3. Sequential: report setup + call results per item.
        4. Sequential: teardown.
        """
        session = self._session
        setup_passed = {}
        setup_reports = {}
        per_item_fixture_fins = {}
        saved_collector_fins = []

        # Phase 1: sequential setup (silent)
        for item in items:
            if hasattr(item, "_request") and not item._request:
                item._initrequest()

            needed = set(item.listchain())
            if any(node not in needed for node in session._setupstate.stack):
                saved_collector_fins.extend(
                    FixtureManager.save_collector_finalizers(session, item)
                )
                session._setupstate.teardown_exact(nextitem=item)

            rep = call_and_report(item, "setup", log=False)
            setup_reports[item] = rep
            setup_passed[item] = rep.passed

            if rep.passed:
                per_item_fixture_fins[item] = (
                    FixtureManager.save_and_clear_function_fixtures(item)
                )

            if item in session._setupstate.stack:
                session._setupstate.stack.pop(item)

        if session.config.getoption("setuponly", False):
            for item in items:
                ihook = item.ihook
                ihook.pytest_runtest_logstart(
                    nodeid=item.nodeid, location=item.location
                )
                ihook.pytest_runtest_logreport(report=setup_reports[item])
                if setup_passed[item] and session.config.getoption(
                    "setupshow", False
                ):
                    show_test_item(item)
            self._teardown_all(items, per_item_fixture_fins, saved_collector_fins)
            return

        # Phase 2: parallel calls with immediate reporting
        callable_items = [it for it in items if setup_passed.get(it)]
        workers = min(self._nthreads, len(callable_items)) if callable_items else 1

        call_results = {}
        reported = set()

        def _do_call(test_item):
            call_info = CallInfo.from_call(
                lambda: test_item.runtest(), when="call"
            )
            return test_item, call_info

        def _report_item(item):
            """Report setup + call for a single item (must be called from
            the main thread so terminal output stays ordered)."""
            ihook = item.ihook
            ihook.pytest_runtest_logstart(
                nodeid=item.nodeid, location=item.location
            )
            ihook.pytest_runtest_logreport(report=setup_reports[item])
            if setup_passed[item]:
                if session.config.getoption("setupshow", False):
                    show_test_item(item)
                if item in call_results:
                    call_info = call_results[item]
                    rep = ihook.pytest_runtest_makereport(
                        item=item, call=call_info
                    )
                    ihook.pytest_runtest_logreport(report=rep)
            reported.add(item)

        if workers > 1 and len(callable_items) > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(_do_call, item): item for item in callable_items
                }
                for future in as_completed(futures):
                    exc = future.exception()
                    if exc is not None:
                        item = futures[future]
                        call_info = CallInfo.from_call(
                            lambda e=exc: (_ for _ in ()).throw(e),
                            when="call",
                        )
                        call_results[item] = call_info
                    else:
                        item, call_info = future.result()
                        call_results[item] = call_info
                    # Report this item and any preceding items that are
                    # already done, preserving original order for file
                    # attribution.
                    for it in items:
                        if it in reported:
                            continue
                        if it not in call_results and setup_passed.get(it):
                            break
                        _report_item(it)
        else:
            for item in callable_items:
                _, call_info = _do_call(item)
                call_results[item] = call_info

        # Phase 3: report any remaining items (setup failures, stragglers)
        for item in items:
            if item not in reported:
                _report_item(item)

        # Phase 4: teardown
        self._teardown_all(items, per_item_fixture_fins, saved_collector_fins)

    def _teardown_all(self, items, per_item_fixture_fins, saved_collector_fins) -> None:
        """Run per-item function-level finalizers, saved collector finalizers,
        then tear down remaining collectors."""
        session = self._session

        for item in items:
            fins = per_item_fixture_fins.get(item, [])

            def _run_fins(fns=fins):
                for fn in reversed(fns):
                    fn()

            teardown_info = CallInfo.from_call(_run_fins, when="teardown")
            rep = item.ihook.pytest_runtest_makereport(item=item, call=teardown_info)
            item.ihook.pytest_runtest_logreport(report=rep)

            if hasattr(item, "_request"):
                item._request = False
                item.funcargs = None

            item.ihook.pytest_runtest_logfinish(
                nodeid=item.nodeid, location=item.location
            )

        session._setupstate.teardown_exact(nextitem=None)

        exceptions = []
        for node, fins in reversed(saved_collector_fins):
            for fin in reversed(fins):
                try:
                    fin()
                except BaseException as e:
                    exceptions.append(e)
        if len(exceptions) == 1:
            raise exceptions[0]
        elif exceptions:
            raise BaseExceptionGroup(
                "errors during deferred collector teardown", exceptions
            )
