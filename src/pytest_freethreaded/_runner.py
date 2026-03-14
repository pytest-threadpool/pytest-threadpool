"""Parallel test runner orchestration."""

import os
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

from _pytest.runner import CallInfo, call_and_report, show_test_item

from ._fixtures import FixtureManager
from ._grouping import GroupKeyBuilder

# Test slot states
_SCHEDULED = "scheduled"
_RUNNING = "running"
_DONE = "done"


class _LiveReporter:
    """Reports parallel results with live per-file line updates.

    Pre-prints all collected file lines before execution starts.
    Each test slot shows one of three states:
      - scheduled: dim dot (waiting to run)
      - running:   bright spinning indicator
      - done:      colored result letter (./F/s)

    Falls back to plain immediate reporting when stdout is not a terminal.
    """

    def __init__(self, session, items):
        tr = session.config.pluginmanager.get_plugin("terminalreporter")
        self._tr = tr
        self._tw = tr._tw if tr else None
        self._total = len(items)
        self._reported = 0
        self._startpath = session.config.rootpath
        self._lock = threading.Lock()

        # Build file→items mapping in collection order
        self._file_order = []
        self._file_idx = {}
        self._file_items = OrderedDict()
        for item in items:
            fspath = item.fspath
            if fspath not in self._file_idx:
                self._file_idx[fspath] = len(self._file_order)
                self._file_order.append(fspath)
                self._file_items[fspath] = []
            self._file_items[fspath].append(item)

        # Per-item state: maps item → (_SCHEDULED | _RUNNING | _DONE, letter, color)
        self._item_state = {}
        for item in items:
            self._item_state[item] = (_SCHEDULED, ".", "")

        # detect capability
        self._live = (
            tr is not None
            and hasattr(tr, "_tw")
            and self._tw.hasmarkup
            and session.config.get_verbosity() <= 0
        )
        self._width = getattr(self._tw, "fullwidth", 80) if self._tw else 80

    @property
    def live(self):
        return self._live

    # -- suppression helpers --------------------------------------------------

    def suppress(self):
        """Temporarily suppress terminal reporter output."""
        if self._tw:
            self._orig_write = self._tw.write
            self._orig_line = self._tw.line
            self._tw.write = lambda *a, **kw: None
            self._tw.line = lambda *a, **kw: None

    def restore(self):
        """Restore terminal reporter output."""
        if self._tw:
            self._tw.write = self._orig_write
            self._tw.line = self._orig_line

    # -- pre-print all files --------------------------------------------------

    def pre_print(self):
        """Print all collected file lines with dim scheduled dots."""
        if not self._live:
            return
        f = self._tw._file
        for fspath in self._file_order:
            self._write_line(fspath)
            f.write("\n")
        f.flush()

    # -- state transitions ----------------------------------------------------

    def mark_running(self, item):
        """Mark a test as currently running and update its file line."""
        with self._lock:
            self._item_state[item] = (_RUNNING, "●", "")
            if self._live:
                self._update_file_line(item.fspath)

    def mark_done(self, item, report):
        """Mark a test as completed and update its file line."""
        with self._lock:
            self._reported += 1
            letter = self._letter_for(report)
            color = self._color_for(report)
            self._item_state[item] = (_DONE, letter, color)
            if self._live:
                self._update_file_line(item.fspath)

    def finish(self):
        """Reset terminal reporter state after live output."""
        if self._tr:
            self._tr.currentfspath = None
            self._tr._write_progress_information_filling_space = lambda: None

    # -- internals ------------------------------------------------------------

    def _update_file_line(self, fspath):
        """Rewrite a single file line using cursor movement."""
        f = self._tw._file
        idx = self._file_idx[fspath]
        bottom = len(self._file_order)
        lines_up = bottom - idx
        f.write(f"\033[{lines_up}A")
        self._write_line(fspath)
        f.write(f"\033[{lines_up}B")
        f.write("\r")
        f.flush()

    def _write_line(self, fspath):
        f = self._tw._file
        try:
            rel = os.path.relpath(str(fspath), str(self._startpath))
        except ValueError:
            rel = str(fspath)

        progress = f" [{100 * self._reported // self._total:3d}%]"

        f.write("\r\033[K")
        f.write(rel + " ")

        n_slots = 0
        for item in self._file_items[fspath]:
            state, letter, color = self._item_state[item]
            n_slots += 1
            if state == _SCHEDULED:
                # middle dot — visually lighter than result letters
                f.write(f"\033[2m·\033[0m")
            elif state == _RUNNING:
                # bright cyan indicator
                f.write(f"\033[36;1m●\033[0m")
            else:
                # completed — colored result
                if color:
                    f.write(f"{color}{letter}\033[0m")
                else:
                    f.write(letter)

        used = len(rel) + 1 + n_slots + len(progress)
        if used < self._width:
            f.write(" " * (self._width - used))
        f.write(progress)

    @staticmethod
    def _letter_for(report):
        if report.passed:
            return "."
        if report.failed:
            return "F"
        if report.skipped:
            return "s"
        return "?"

    def _color_for(self, report):
        if not self._tw.hasmarkup:
            return ""
        if report.passed:
            return "\033[32m"       # green
        if report.failed:
            return "\033[31;1m"     # red bold
        if report.skipped:
            return "\033[33m"       # yellow
        return ""


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

        # Phase 2: parallel calls with live reporting
        callable_items = [it for it in items if setup_passed.get(it)]
        workers = min(self._nthreads, len(callable_items)) if callable_items else 1

        call_results = {}
        reported = set()
        live = _LiveReporter(session, items)
        live.pre_print()

        def _do_call(test_item):
            live.mark_running(test_item)
            call_info = CallInfo.from_call(
                lambda: test_item.runtest(), when="call"
            )
            return test_item, call_info

        def _report_item(item):
            """Report a single item — live cursor mode or plain fallback."""
            ihook = item.ihook

            # Build the call report first (needed for live dot letter)
            call_rep = None
            if setup_passed[item] and item in call_results:
                call_info = call_results[item]
                call_rep = ihook.pytest_runtest_makereport(
                    item=item, call=call_info
                )

            report = call_rep if call_rep else setup_reports[item]

            if live.live:
                # Suppress terminal reporter output, fire hooks for stats
                live.suppress()
                ihook.pytest_runtest_logstart(
                    nodeid=item.nodeid, location=item.location
                )
                ihook.pytest_runtest_logreport(report=setup_reports[item])
                if setup_passed[item]:
                    if session.config.getoption("setupshow", False):
                        show_test_item(item)
                    if call_rep is not None:
                        ihook.pytest_runtest_logreport(report=call_rep)
                live.restore()
                live.mark_done(item, report)
            else:
                # Plain fallback (non-TTY, verbose, etc.)
                ihook.pytest_runtest_logstart(
                    nodeid=item.nodeid, location=item.location
                )
                ihook.pytest_runtest_logreport(report=setup_reports[item])
                if setup_passed[item]:
                    if session.config.getoption("setupshow", False):
                        show_test_item(item)
                    if call_rep is not None:
                        ihook.pytest_runtest_logreport(report=call_rep)

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
                    _report_item(item)
        else:
            for item in callable_items:
                _, call_info = _do_call(item)
                call_results[item] = call_info
                _report_item(item)

        # Phase 3: report any remaining items (setup failures, stragglers)
        for item in items:
            if item not in reported:
                _report_item(item)

        if live.live:
            live.finish()

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
