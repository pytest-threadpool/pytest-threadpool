"""Parallel test runner orchestration."""

import io
import os
import queue
import sys
import threading
from collections import OrderedDict

from _pytest.runner import CallInfo, call_and_report, show_test_item

from pytest_threadpool._fixtures import FixtureManager
from pytest_threadpool._grouping import GroupKeyBuilder


class _ThreadLocalStream:
    """Thread-local stream proxy for suppressing worker stdout/stderr.

    Installed once on sys.stdout/sys.stderr before parallel workers start.
    Worker threads call ``activate()`` to redirect their writes to a
    per-thread StringIO buffer, and ``deactivate()`` to stop.  Writes
    from non-worker threads (e.g. the main thread, live reporter) pass
    through to the real stream.
    """

    def __init__(self, real: object):
        self._real = real
        self._local = threading.local()

    def activate(self) -> None:
        self._local.buf = io.StringIO()

    def deactivate(self) -> None:
        self._local.buf = None

    def write(self, s: str) -> int:
        buf = getattr(self._local, "buf", None)
        return buf.write(s) if buf is not None else self._real.write(s)  # type: ignore[union-attr]

    def flush(self) -> None:
        buf = getattr(self._local, "buf", None)
        if buf is not None:
            buf.flush()
        else:
            self._real.flush()  # type: ignore[union-attr]

    def __getattr__(self, name: str) -> object:
        return getattr(self._real, name)


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
        # noinspection PyProtectedMember
        # No public accessor for TerminalWriter; needed for hasmarkup,
        # raw file handle (ANSI cursor movement), and write suppression.
        self._tw = tr._tw if tr else None  # pyright: ignore[reportPrivateUsage]
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
            and self._tw is not None
            and hasattr(tr, "_tw")
            and self._tw.hasmarkup
            and session.config.get_verbosity() <= 0
        )
        self._width = getattr(self._tw, "fullwidth", 80) if self._tw else 80
        # noinspection PyProtectedMember
        # No public accessor on TerminalWriter for the underlying file handle.
        # We need it for direct ANSI escape writes (cursor movement, colors)
        # that bypass TerminalWriter formatting.
        self._file = self._tw._file if self._tw else None  # pyright: ignore[reportPrivateUsage]

        # Track whether dumb mode has written any file lines, so we
        # know when to prefix with \n for line separation.
        self._dumb_needs_sep = False

        # Pre-compute colors for worker-thread display updates
        markup = self._tw.hasmarkup if self._tw else False
        self._pass_color = "\033[32m" if markup else ""
        self._fail_color = "\033[31;1m" if markup else ""

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
        """Print all collected file lines with dim scheduled dots and a progress line."""
        if not self._live:
            return
        assert self._file is not None
        f = self._file
        # Start on a fresh line so we don't overwrite any preceding
        # output (e.g. sequential test results between parallel groups).
        f.write("\n")
        for fspath in self._file_order:
            self._write_line_live(fspath)
            f.write("\n")
        self._write_progress_line()
        f.flush()

    # -- state transitions ----------------------------------------------------

    def mark_running(self, item):
        """Mark a test as currently running and update its file line."""
        with self._lock:
            self._item_state[item] = (_RUNNING, "●", "")
            if self._live:
                self._update_file_line(item.fspath)

    def mark_done(self, item, report):
        """Mark a test as completed and update its file line.

        In live mode, updates in-place with cursor movement.
        In dumb mode, writes the full file line once all tests in
        that file have completed (no cursor movement needed).

        If already marked done by mark_call_done, corrects the letter
        if the final report differs (e.g. skip detected as failure).
        """
        with self._lock:
            letter = self._letter_for(report)
            color = self._color_for(report)
            already_done = self._item_state[item][0] == _DONE
            if already_done and self._item_state[item][1] == letter:
                return
            if not already_done:
                self._reported += 1
            self._item_state[item] = (_DONE, letter, color)
            if self._live:
                self._update_file_line(item.fspath)
            else:
                self._maybe_flush_file(item.fspath)

    def mark_call_done(self, item, excinfo):
        """Mark a test call as completed from the worker thread.

        Uses excinfo to determine pass/fail immediately, so the display
        updates as soon as the call finishes rather than waiting for the
        main thread to process hooks.
        """
        with self._lock:
            self._reported += 1
            if excinfo is None:
                letter, color = ".", self._pass_color
            else:
                letter, color = "F", self._fail_color
            self._item_state[item] = (_DONE, letter, color)
            if self._live:
                self._update_file_line(item.fspath)
            else:
                self._maybe_flush_file(item.fspath)

    def finish(self):
        """Reset terminal reporter state after live output."""
        if self._live and self._tw and self._file:
            # End the progress line and move cursor back up so the
            # terminal reporter's next _tw.line() call (from
            # write_fspath_result or the summary separator) brings
            # the cursor back down without creating a blank line.
            self._file.write("\n\033[A")
            self._file.flush()
        if self._tr:
            self._tr.currentfspath = None
            # noinspection PyProtectedMember
            # No public API to suppress the final "[100%]" that the terminal
            # reporter's pytest_runtestloop wrapper writes after the test loop.
            self._tr._write_progress_information_filling_space = lambda: None  # pyright: ignore[reportPrivateUsage]

    # -- internals ------------------------------------------------------------

    def _update_file_line(self, fspath):
        """Rewrite a single file line and progress using cursor movement (live mode)."""
        assert self._file is not None
        f = self._file
        idx = self._file_idx[fspath]
        bottom = len(self._file_order)
        lines_up = bottom - idx
        f.write(f"\033[{lines_up}A")
        self._write_line_live(fspath)
        f.write(f"\033[{lines_up}B")
        f.write("\r")
        self._write_progress_line()
        f.flush()

    def _maybe_flush_file(self, fspath):
        """In dumb mode, write a file line once all its tests are done."""
        if not self._tw or not self._file:
            return
        file_items = self._file_items[fspath]
        if all(self._item_state[it][0] == _DONE for it in file_items):
            self._write_line_plain(fspath)

    def _write_line_live(self, fspath):
        """Write a file line with ANSI formatting (live terminal mode)."""
        assert self._file is not None
        f = self._file
        rel = self._rel_path(fspath)

        f.write("\r\033[K")
        f.write(rel + " ")

        for item in self._file_items[fspath]:
            state, letter, color = self._item_state[item]
            if state == _SCHEDULED:
                f.write("\033[2m·\033[0m")
            elif state == _RUNNING:
                f.write("\033[36;1m●\033[0m")
            else:
                if color:
                    f.write(f"{color}{letter}\033[0m")
                else:
                    f.write(letter)

    def _write_line_plain(self, fspath):
        """Write a file line without ANSI codes (dumb/pipe mode).

        No trailing newline: subsequent calls prefix with \\n for line
        separation.  This lets the terminal reporter's write_fspath_result
        naturally end the last line without creating a blank line.
        """
        assert self._file is not None
        f = self._file
        rel = self._rel_path(fspath)
        progress = f" [{100 * self._reported // self._total:3d}%]"

        letters = ""
        for item in self._file_items[fspath]:
            _, letter, _ = self._item_state[item]
            letters += letter

        sep = "\n" if self._dumb_needs_sep else ""
        f.write(f"{sep}{rel} {letters}{progress}")
        f.flush()
        self._dumb_needs_sep = True

    def _write_progress_line(self):
        """Write/update the progress line at the bottom."""
        assert self._file is not None
        f = self._file
        pct = 100 * self._reported // self._total
        f.write(f"\r\033[K{self._reported}/{self._total} [{pct:3d}%]")

    def _rel_path(self, fspath):
        try:
            return os.path.relpath(str(fspath), str(self._startpath))
        except ValueError:
            return str(fspath)

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
        if not self._tw or not self._tw.hasmarkup:
            return ""
        if report.passed:
            return "\033[32m"  # green
        if report.failed:
            return "\033[31;1m"  # red bold
        if report.skipped:
            return "\033[33m"  # yellow
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

        if session.testsfailed and not session.config.option.continue_on_collection_errors:
            raise session.Interrupted(
                f"{session.testsfailed} error"
                f"{'s' if session.testsfailed != 1 else ''} during collection"
            )

        if session.config.option.collectonly:
            return True

        groups = GroupKeyBuilder.build_groups(session.items)
        has_parallel = any(
            k is not None and len(gi) > 1 and self._nthreads > 1 for k, gi in groups
        )

        needs_sep = False
        for group_key, items in groups:
            if session.shouldfail:
                raise session.Failed(session.shouldfail)
            if session.shouldstop:
                raise session.Interrupted(session.shouldstop)

            if group_key is None or len(items) <= 1 or self._nthreads <= 1:
                for i, item in enumerate(items):
                    nextitem = items[i + 1] if i + 1 < len(items) else None
                    if has_parallel:
                        self._run_sequential_nodeid(item, nextitem)
                    else:
                        self._run_sequential(item, nextitem)
                needs_sep = bool(items)
            else:
                self._run_parallel(items, after_sequential=needs_sep)
                needs_sep = True

        return True

    def _run_sequential(self, item, nextitem) -> None:
        """Run the full default protocol for a single item."""
        ihook = item.ihook
        ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)

        # noinspection PyProtectedMember
        # No public API for request lifecycle management; mirrors pytest's
        # own runner.py (_pytest.runner.runtestprotocol).
        if hasattr(item, "_request") and not item._request:  # pyright: ignore[reportPrivateUsage]
            item._initrequest()  # pyright: ignore[reportPrivateUsage]

        rep_setup = call_and_report(item, "setup", log=True)
        if rep_setup.passed:
            if item.config.getoption("setupshow", False):
                show_test_item(item)
            if not item.config.getoption("setuponly", False):
                call_and_report(item, "call", log=True)
        call_and_report(item, "teardown", log=True, nextitem=nextitem)

        if hasattr(item, "_request"):
            item._request = False  # pyright: ignore[reportPrivateUsage]
            item.funcargs = None

        ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)

    def _run_sequential_nodeid(self, item, nextitem) -> None:
        """Run a single item sequentially with nodeid-style reporting.

        Used for sequential items in mixed parallel/sequential sessions
        so the output (``file::test PASSED``) visually distinguishes
        them from parallel groups (``file .....``).
        """
        tr = self._session.config.pluginmanager.get_plugin("terminalreporter")
        # noinspection PyProtectedMember
        tw = tr._tw if tr and hasattr(tr, "_tw") else None  # pyright: ignore[reportPrivateUsage]
        # noinspection PyProtectedMember
        f = getattr(tw, "_file", None) if tw else None  # pyright: ignore[reportPrivateUsage]

        # Suppress terminal reporter output so we can write our own format
        orig_write = None
        orig_line = None
        if tw:
            orig_write = tw.write
            orig_line = tw.line
            tw.write = lambda *a, **kw: None
            tw.line = lambda *a, **kw: None

        try:
            ihook = item.ihook
            ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)

            # noinspection PyProtectedMember
            if hasattr(item, "_request") and not item._request:  # pyright: ignore[reportPrivateUsage]
                item._initrequest()  # pyright: ignore[reportPrivateUsage]

            rep_setup = call_and_report(item, "setup", log=True)
            call_rep = None
            if rep_setup.passed:
                if item.config.getoption("setupshow", False):
                    show_test_item(item)
                if not item.config.getoption("setuponly", False):
                    call_rep = call_and_report(item, "call", log=True)
            call_and_report(item, "teardown", log=True, nextitem=nextitem)

            if hasattr(item, "_request"):
                item._request = False  # pyright: ignore[reportPrivateUsage]
                item.funcargs = None

            ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)
        finally:
            if tw and orig_write is not None:
                tw.write = orig_write
                tw.line = orig_line

        # Write nodeid-style result line
        if f:
            report = call_rep if call_rep is not None else rep_setup
            if report.passed:
                word = "PASSED"
                color = "\033[32m" if tw and tw.hasmarkup else ""
            elif report.failed:
                word = "FAILED"
                color = "\033[31;1m" if tw and tw.hasmarkup else ""
            elif report.skipped:
                word = "SKIPPED"
                color = "\033[33m" if tw and tw.hasmarkup else ""
            else:
                word = "?"
                color = ""
            reset = "\033[0m" if color else ""
            f.write(f"\n{item.nodeid} {color}{word}{reset}")
            f.flush()

    def _run_parallel(self, items, after_sequential: bool = False) -> None:
        """Run a group's tests with parallel fixture setup and calls.

        Function-scoped FixtureDefs are cloned per-item so their setup can
        run concurrently alongside the test call.  Shared fixtures
        (module/class/session scope) are set up once via the first item,
        then served from cache to all workers.

        1. Sequential: set up first item (populates shared fixture caches).
        2. Sequential: prepare remaining items (_initrequest + clone FixtureDefs).
        3. Parallel:   workers run setup (cloned fixtures) + call per item.
        4. Sequential: report, teardown.
        """
        session = self._session
        setup_passed = {}
        setup_reports = {}
        per_item_fixture_fins = {}
        saved_collector_fins = []

        # noinspection PyProtectedMember
        # item._request/_initrequest and session._setupstate: no public API
        # for request lifecycle or setup state management.  Mirrors pytest's
        # own runner.py (_pytest.runner.runtestprotocol / SetupState).
        def _setup_first_item(item):
            """Full sequential setup for the first item (caches shared fixtures)."""
            if hasattr(item, "_request") and not item._request:  # pyright: ignore[reportPrivateUsage]
                item._initrequest()  # pyright: ignore[reportPrivateUsage]

            needed = set(item.listchain())
            if any(node not in needed for node in session._setupstate.stack):  # pyright: ignore[reportPrivateUsage]
                saved_collector_fins.extend(
                    FixtureManager.save_collector_finalizers(session, item)
                )
                session._setupstate.teardown_exact(nextitem=item)  # pyright: ignore[reportPrivateUsage]

            rep = call_and_report(item, "setup", log=False)
            setup_reports[item] = rep
            setup_passed[item] = rep.passed

            if rep.passed:
                per_item_fixture_fins[item] = FixtureManager.save_and_clear_function_fixtures(item)
            else:
                FixtureManager.clear_function_fixture_caches(item)

            if item in session._setupstate.stack:  # pyright: ignore[reportPrivateUsage]
                session._setupstate.stack.pop(item)  # pyright: ignore[reportPrivateUsage]

        if session.config.getoption("setuponly", False):
            for item in items:
                _setup_first_item(item)
            for item in items:
                ihook = item.ihook
                ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
                ihook.pytest_runtest_logreport(report=setup_reports[item])
                if setup_passed[item] and session.config.getoption("setupshow", False):
                    show_test_item(item)
            self._teardown_all(items, per_item_fixture_fins, {}, saved_collector_fins)
            return

        # Phase 1+2: fire hooks for all items, populate shared fixture caches,
        # and clone function-scoped FixtureDefs.
        #
        # The first item that passes hook evaluation resolves shared fixtures
        # (module/class/session scope) to populate FixtureDef caches.  All
        # subsequent items get cache hits for shared fixtures.  Function-scoped
        # fixtures are NOT created here — they are deferred to parallel workers.
        #
        # noinspection PyProtectedMember
        parallel_items = []
        shared_populated_modules: set = set()

        for item in items:
            if hasattr(item, "_request") and not item._request:  # pyright: ignore[reportPrivateUsage]
                item._initrequest()  # pyright: ignore[reportPrivateUsage]

            # Handle collector transitions (needed for PKG_CHILDREN groups
            # that span multiple modules).
            needed = set(item.listchain())
            if any(node not in needed for node in session._setupstate.stack):  # pyright: ignore[reportPrivateUsage]
                saved_collector_fins.extend(
                    FixtureManager.save_collector_finalizers(session, item)
                )
                session._setupstate.teardown_exact(nextitem=item)  # pyright: ignore[reportPrivateUsage]

            # Fire setup hooks with a custom setup function:
            # - First eligible item per module: resolve shared fixtures (populates caches)
            # - Remaining items in same module: no-op (shared caches already populated)
            # This evaluates skip/xfail markers and initializes capture/logging
            # without creating function-scoped fixtures.
            # Per-module tracking ensures cross-module PKG_CHILDREN groups
            # correctly populate shared fixtures for each module.
            original_setup = item.setup
            if item.module not in shared_populated_modules:
                item.setup = lambda i=item: FixtureManager.populate_shared_fixtures(i)
            else:
                item.setup = lambda: None
            try:
                hook_rep = call_and_report(item, "setup", log=False)
            finally:
                item.setup = original_setup

            # Pop item from setupstate (pushed by _setupstate.setup inside the
            # hook) so the next item's hook doesn't fail the stack assertion.
            if item in session._setupstate.stack:  # pyright: ignore[reportPrivateUsage]
                session._setupstate.stack.pop(item)  # pyright: ignore[reportPrivateUsage]

            if not hook_rep.passed:
                # Hooks raised (skip, skipif, xfail NOTRUN, etc.)
                setup_reports[item] = hook_rep
                setup_passed[item] = False
                continue

            shared_populated_modules.add(item.module)

            FixtureManager.clone_function_fixturedefs(item)
            parallel_items.append(item)

        # Push all parallel items to setupstate stack so addfinalizer
        # assertions pass during fixture resolution in worker threads.
        # Done after the hook loop so items don't interfere with each
        # other's _setupstate.setup() assertions.
        for item in parallel_items:
            session._setupstate.stack[item] = ([item.teardown], None)  # pyright: ignore[reportPrivateUsage]

        # Phase 3: parallel setup + call
        workers = min(self._nthreads, len(parallel_items) or 1)
        call_results = {}
        reported = set()
        live = _LiveReporter(session, items)
        if after_sequential:
            live._dumb_needs_sep = True
        live.pre_print()

        cancelled = threading.Event()

        def _do_setup_call_teardown(test_item):
            """Setup + call + teardown worker (for items with cloned FixtureDefs).

            Fixture setup uses cloned function-scoped FixtureDefs so each
            worker creates independent fixture instances without racing
            on shared FixtureDef state.  Shared fixtures are already cached
            from the first item's sequential setup, so their FixtureDef.execute()
            is a cache-hit read.

            Function-scoped fixture teardown (yield cleanup, addfinalizer
            callbacks, xunit teardown_method) also runs in the worker since
            each item's finalizers are independent.

            addfinalizer is redirected to a per-item list to avoid the
            setupstate stack assertion (the item IS in the stack, but
            list.append on the stack entry is also safe on free-threaded Python;
            the redirect simply avoids coupling to setupstate internals).
            """
            if cancelled.is_set():
                return test_item, None, None, None
            return _do_worker_body(test_item)

        def _do_worker_body(test_item):
            # Redirect node.addfinalizer to per-item list
            original_addfinalizer = test_item.addfinalizer
            node_fins = []
            test_item.addfinalizer = lambda fin: node_fins.append(fin)

            try:
                setup_info = CallInfo.from_call(lambda: test_item.setup(), when="setup")
            finally:
                test_item.addfinalizer = original_addfinalizer

            if setup_info.excinfo is None:
                fixture_fins = FixtureManager.save_and_clear_function_fixtures(test_item)
                call_info = None
                if not cancelled.is_set():
                    live.mark_running(test_item)
                    call_info = CallInfo.from_call(lambda: test_item.runtest(), when="call")
                    if not cancelled.is_set():
                        live.mark_call_done(test_item, call_info.excinfo)

                # Run function-scoped fixture teardown in the worker.
                # Includes yield cleanup, addfinalizer callbacks, and
                # node-level finalizers captured during setup.
                all_fins = list(node_fins) + fixture_fins

                def _run_fins(fns=all_fins):
                    exceptions = []
                    for fn in reversed(fns):
                        try:
                            fn()
                        except BaseException as e:
                            exceptions.append(e)
                    if len(exceptions) == 1:
                        raise exceptions[0]
                    if exceptions:
                        raise BaseExceptionGroup("errors during fixture teardown", exceptions)

                teardown_info = CallInfo.from_call(_run_fins, when="teardown")
                return test_item, setup_info, call_info, teardown_info

            FixtureManager.clear_function_fixture_caches(test_item)
            return test_item, setup_info, None, None

        def _report_item(item):
            """Report a single item — live cursor mode or plain fallback."""
            ihook = item.ihook

            live.suppress()
            try:
                call_rep = None
                if setup_passed[item] and item in call_results:
                    call_info = call_results[item]
                    call_rep = ihook.pytest_runtest_makereport(item=item, call=call_info)

                report = call_rep or setup_reports[item]

                ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
                ihook.pytest_runtest_logreport(report=setup_reports[item])
                if setup_passed[item]:
                    if session.config.getoption("setupshow", False):
                        show_test_item(item)
                    if call_rep is not None:
                        ihook.pytest_runtest_logreport(report=call_rep)
            finally:
                live.restore()
            live.mark_done(item, report)

            reported.add(item)

        teardown_infos = {}

        # Install thread-local stream proxies so worker print() output
        # doesn't corrupt test result lines.  In live mode this prevents
        # ANSI cursor corruption; in verbose/dumb mode it prevents
        # interleaved output on the same line as test results.
        # Each worker activates its own buffer; the main thread and
        # reporter writes pass through to the real streams.
        stdout_proxy: _ThreadLocalStream | None = None
        stderr_proxy: _ThreadLocalStream | None = None
        capture_option = session.config.getoption("capture", "fd")
        if workers > 1 and len(parallel_items) > 1 and capture_option != "no":
            stdout_proxy = _ThreadLocalStream(sys.stdout)
            stderr_proxy = _ThreadLocalStream(sys.stderr)
            sys.stdout = stdout_proxy  # type: ignore[assignment]
            sys.stderr = stderr_proxy  # type: ignore[assignment]

        interrupted = False
        if workers > 1 and len(parallel_items) > 1:
            work_queue = queue.SimpleQueue()
            result_queue = queue.SimpleQueue()

            def _pool_worker():
                while True:
                    work_item = work_queue.get()
                    if work_item is None or cancelled.is_set():
                        return
                    if stdout_proxy is not None:
                        stdout_proxy.activate()
                        stderr_proxy.activate()  # type: ignore[union-attr]
                    try:
                        item, setup_info, call_info, td_info = _do_setup_call_teardown(work_item)
                        if setup_info is not None:
                            setup_rep = item.ihook.pytest_runtest_makereport(
                                item=item, call=setup_info
                            )
                            setup_reports[item] = setup_rep
                            setup_passed[item] = setup_info.excinfo is None
                        if td_info is not None:
                            teardown_infos[item] = td_info
                        result_queue.put((item, call_info))
                    except BaseException as exc:
                        call_info = CallInfo.from_call(
                            lambda e=exc: (_ for _ in ()).throw(e),
                            when="call",
                        )
                        result_queue.put((work_item, call_info))
                    finally:
                        if stdout_proxy is not None:
                            stdout_proxy.deactivate()
                            stderr_proxy.deactivate()  # type: ignore[union-attr]

            threads = []
            for _ in range(workers):
                t = threading.Thread(target=_pool_worker, daemon=True)
                t.start()
                threads.append(t)

            # Submit all parallel items (setup + call + teardown)
            for item in parallel_items:
                work_queue.put(item)

            try:
                collected = 0
                while collected < len(parallel_items):
                    finished_item, call_info = result_queue.get()
                    if call_info is not None:
                        call_results[finished_item] = call_info
                    _report_item(finished_item)
                    collected += 1
            except KeyboardInterrupt:
                interrupted = True
                cancelled.set()

            for _ in range(workers):
                work_queue.put(None)
            if not interrupted:
                for t in threads:
                    t.join()
        else:
            # Single worker fallback
            try:
                for item in parallel_items:
                    if stdout_proxy is not None:
                        stdout_proxy.activate()
                        stderr_proxy.activate()  # type: ignore[union-attr]
                    try:
                        item, setup_info, call_info, td_info = _do_setup_call_teardown(item)
                        if setup_info is not None:
                            setup_rep = item.ihook.pytest_runtest_makereport(
                                item=item, call=setup_info
                            )
                            setup_reports[item] = setup_rep
                            setup_passed[item] = setup_info.excinfo is None
                        if td_info is not None:
                            teardown_infos[item] = td_info
                    finally:
                        if stdout_proxy is not None:
                            stdout_proxy.deactivate()
                            stderr_proxy.deactivate()  # type: ignore[union-attr]
                    if call_info is not None:
                        call_results[item] = call_info
                    _report_item(item)
            except KeyboardInterrupt:
                interrupted = True

        # Report any remaining items (setup failures, stragglers)
        if not interrupted:
            for item in items:
                if item not in reported:
                    _report_item(item)

        live.finish()

        # Restore real stdout/stderr after all workers are done
        if stdout_proxy is not None:
            sys.stdout = stdout_proxy._real  # type: ignore[assignment]
            sys.stderr = stderr_proxy._real  # type: ignore[union-attr, assignment]

        # Pop parallel items from setupstate stack
        # noinspection PyProtectedMember
        for item in parallel_items:
            if item in session._setupstate.stack:  # pyright: ignore[reportPrivateUsage]
                session._setupstate.stack.pop(item)  # pyright: ignore[reportPrivateUsage]

        # Teardown reporting + collector teardown (always runs, even after interrupt)
        self._teardown_all(items, per_item_fixture_fins, teardown_infos, saved_collector_fins)

        if interrupted:
            raise KeyboardInterrupt

    def _teardown_all(
        self, items, per_item_fixture_fins, teardown_infos, saved_collector_fins
    ) -> None:
        """Report teardown results, run any remaining finalizers, and tear down
        collectors.

        For items with pre-computed teardown_infos (from parallel workers),
        only reporting happens here.  For items without (setuponly mode),
        finalizers from per_item_fixture_fins are executed sequentially.
        """
        session = self._session

        for item in items:
            if item in teardown_infos:
                # Teardown already ran in the worker — just report.
                teardown_info = teardown_infos[item]
            else:
                # Fallback: run finalizers now (setuponly mode).
                fins = per_item_fixture_fins.get(item, [])

                def _run_fins(fns=fins):
                    exceptions = []
                    for fn in reversed(fns):
                        try:
                            fn()
                        except BaseException as e:
                            exceptions.append(e)
                    if len(exceptions) == 1:
                        raise exceptions[0]
                    if exceptions:
                        raise BaseExceptionGroup("errors during fixture teardown", exceptions)

                teardown_info = CallInfo.from_call(_run_fins, when="teardown")

            rep = item.ihook.pytest_runtest_makereport(item=item, call=teardown_info)
            item.ihook.pytest_runtest_logreport(report=rep)

            # noinspection PyProtectedMember
            if hasattr(item, "_request"):
                item._request = False  # pyright: ignore[reportPrivateUsage]
                item.funcargs = None

            item.ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)

        # noinspection PyProtectedMember
        session._setupstate.teardown_exact(nextitem=None)  # pyright: ignore[reportPrivateUsage]

        exceptions = []
        for _node, fins in reversed(saved_collector_fins):
            for fin in reversed(fins):
                try:
                    fin()
                except BaseException as e:
                    exceptions.append(e)
        if len(exceptions) == 1:
            raise exceptions[0]
        if exceptions:
            raise BaseExceptionGroup("errors during deferred collector teardown", exceptions)
