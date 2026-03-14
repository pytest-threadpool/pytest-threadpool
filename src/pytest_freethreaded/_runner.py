"""Parallel test runner orchestration."""

import os
import queue
import threading
from collections import OrderedDict

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
        f = self._file
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
        if self._live and self._tw:
            # Finalize the progress line and move to the next line
            self._file.write("\n")
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
        if not self._tw:
            return
        file_items = self._file_items[fspath]
        if all(self._item_state[it][0] == _DONE for it in file_items):
            self._write_line_plain(fspath)

    def _write_line_live(self, fspath):
        """Write a file line with ANSI formatting (live terminal mode)."""
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
        """Write a file line without ANSI codes (dumb/pipe mode)."""
        f = self._file
        rel = self._rel_path(fspath)
        progress = f" [{100 * self._reported // self._total:3d}%]"

        letters = ""
        for item in self._file_items[fspath]:
            _, letter, _ = self._item_state[item]
            letters += letter

        line = f"{rel} {letters}{progress}\n"
        f.write(line)
        f.flush()

    def _write_progress_line(self):
        """Write/update the progress line at the bottom."""
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

    def _run_parallel(self, items) -> None:
        """Run a group's tests with parallel call phases.

        1. Sequential: setup every item (no reporting yet).
        2. Parallel:   item.runtest() in a thread pool.
        3. Sequential: report setup and call results per item.
        4. Sequential: teardown.
        """
        session = self._session
        setup_passed = {}
        setup_reports = {}
        per_item_fixture_fins = {}
        saved_collector_fins = []

        # Phase 1: sequential setup (silent)
        # noinspection PyProtectedMember
        # item._request/_initrequest and session._setupstate: no public API
        # for request lifecycle or setup state management.  Mirrors pytest's
        # own runner.py (_pytest.runner.runtestprotocol / SetupState).
        for item in items:
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
                per_item_fixture_fins[item] = (
                    FixtureManager.save_and_clear_function_fixtures(item)
                )
            else:
                FixtureManager.clear_function_fixture_caches(item)

            if item in session._setupstate.stack:  # pyright: ignore[reportPrivateUsage]
                session._setupstate.stack.pop(item)  # pyright: ignore[reportPrivateUsage]

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
            if cancelled.is_set():
                return test_item, CallInfo.from_call(
                    lambda: None, when="call"
                )
            live.mark_running(test_item)
            call_info = CallInfo.from_call(
                lambda: test_item.runtest(), when="call"
            )
            if not cancelled.is_set():
                live.mark_call_done(test_item, call_info.excinfo)
            return test_item, call_info

        def _report_item(item):
            """Report a single item — live cursor mode or plain fallback."""
            ihook = item.ihook

            # Build the call report first (needed for a live dot letter)
            call_rep = None
            if setup_passed[item] and item in call_results:
                call_info = call_results[item]
                call_rep = ihook.pytest_runtest_makereport(
                    item=item, call=call_info
                )

            report = call_rep if call_rep else setup_reports[item]

            # Suppress terminal reporter output, fire hooks for stats only.
            # try/finally ensures restore() runs even on KeyboardInterrupt,
            # otherwise the terminal writer stays suppressed and pytest's
            # interrupt traceback is silently lost.
            live.suppress()
            try:
                ihook.pytest_runtest_logstart(
                    nodeid=item.nodeid, location=item.location
                )
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

        interrupted = False
        cancelled = threading.Event()
        if workers > 1 and len(callable_items) > 1:
            work_queue = queue.SimpleQueue()
            result_queue = queue.SimpleQueue()

            def _pool_worker():
                while True:
                    work_item = work_queue.get()
                    if work_item is None or cancelled.is_set():
                        return
                    try:
                        result = _do_call(work_item)
                    except BaseException as exc:
                        # Ensure the result queue always gets an entry so the
                        # main thread never blocks forever on .get().
                        call_info = CallInfo.from_call(
                            lambda e=exc: (_ for _ in ()).throw(e),
                            when="call",
                        )
                        result = (work_item, call_info)
                    result_queue.put(result)

            threads = []
            for _ in range(workers):
                t = threading.Thread(target=_pool_worker, daemon=True)
                t.start()
                threads.append(t)

            for ci in callable_items:
                work_queue.put(ci)

            try:
                remaining = len(callable_items)
                while remaining > 0:
                    item, call_info = result_queue.get()
                    call_results[item] = call_info
                    _report_item(item)
                    remaining -= 1
            except KeyboardInterrupt:
                interrupted = True
                cancelled.set()

            # Signal workers to stop (best-effort; they're daemon threads)
            for _ in range(workers):
                work_queue.put(None)
            if not interrupted:
                for t in threads:
                    t.join()
        else:
            try:
                for item in callable_items:
                    _, call_info = _do_call(item)
                    call_results[item] = call_info
                    _report_item(item)
            except KeyboardInterrupt:
                interrupted = True

        # Phase 3: report any remaining items (setup failures, stragglers)
        if not interrupted:
            for item in items:
                if item not in reported:
                    _report_item(item)

        live.finish()

        # Phase 4: teardown (always runs, even after interrupt)
        self._teardown_all(items, per_item_fixture_fins, saved_collector_fins)

        if interrupted:
            raise KeyboardInterrupt()

    def _teardown_all(self, items, per_item_fixture_fins, saved_collector_fins) -> None:
        """Run per-item function-level finalizers, saved collector finalizers,
        then tear down remaining collectors."""
        session = self._session

        for item in items:
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
                elif exceptions:
                    raise BaseExceptionGroup(
                        "errors during fixture teardown", exceptions
                    )

            teardown_info = CallInfo.from_call(_run_fins, when="teardown")
            rep = item.ihook.pytest_runtest_makereport(item=item, call=teardown_info)
            item.ihook.pytest_runtest_logreport(report=rep)

            # noinspection PyProtectedMember
            if hasattr(item, "_request"):
                item._request = False  # pyright: ignore[reportPrivateUsage]
                item.funcargs = None

            item.ihook.pytest_runtest_logfinish(
                nodeid=item.nodeid, location=item.location
            )

        # noinspection PyProtectedMember
        session._setupstate.teardown_exact(nextitem=None)  # pyright: ignore[reportPrivateUsage]

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
