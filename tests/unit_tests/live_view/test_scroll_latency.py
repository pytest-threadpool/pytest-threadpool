"""Scroll latency tests — simulates post-test report view.

Reproduces the exact output shape from a full test run (~50 content rows),
sets the status line to the Ctrl+C prompt, then measures how quickly scroll
events (arrow keys, mouse wheel) result in the viewport actually shifting.

Every individual scroll event must produce a visible viewport change within
20 ms.
"""

import fcntl
import io
import os
import pty
import queue
import select
import struct
import termios
import threading
import time
import tty

from pytest_threadpool._live_view import ViewManager
from pytest_threadpool._live_view._input import (
    InputEvent,
    InputReader,
    KeyEvent,
    MouseEvent,
)

# Realistic session output (abbreviated to ~50 lines matching user's report).
_SESSION_LINES = [
    "=" * 100 + " test session starts " + "=" * 100,
    "platform linux -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0",
    "rootdir: /home/work/repos/pytest-freethreaded-example",
    "configfile: pyproject.toml",
    "plugins: cov-7.0.0, teamcity-messages-1.33, threadpool-0.3.7",
    "collected 477 items",
    "",
    "tests/integration_tests/test_caplog.py .........",
    "tests/integration_tests/test_capture.py ............",
    "tests/integration_tests/test_ide_reporter.py .................",
    "tests/integration_tests/test_live_view.py .........",
    "tests/integration_tests/test_logging.py ...............",
    "tests/integration_tests/test_pytester_class.py ...",
    "tests/integration_tests/test_pytester_edge_cases.py .....",
    "tests/integration_tests/test_pytester_fixtures.py .............",
    "tests/integration_tests/test_pytester_func_fixtures.py ....",
    "tests/integration_tests/test_pytester_marks.py .......",
    "tests/integration_tests/test_pytester_package.py .........",
    "tests/integration_tests/test_pytester_parallel_teardown.py",
    "tests/integration_tests/test_pytester_reporting.py ........",
    "tests/integration_tests/test_pytester_scopes.py ...........",
    "tests/integration_tests/test_pytester_sequential.py ..",
    "tests/integration_tests/test_pytester_shared.py .....",
    "tests/integration_tests/test_pytester_xunit.py ..........",
    "tests/integration_tests/test_scoped_output.py .............",
    "193/193 [100%]",
    "tests/unit_tests/live_view/test_ansi.py ................",
    "tests/unit_tests/live_view/test_buffer.py ....",
    "tests/unit_tests/live_view/test_cursor.py ...............",
    "tests/unit_tests/live_view/test_display.py ....................",
    "tests/unit_tests/live_view/test_field.py ......................",
    "tests/unit_tests/live_view/test_input.py ..............",
    "tests/unit_tests/live_view/test_layout.py .......",
    "tests/unit_tests/live_view/test_scroll_column.py .......",
    "tests/unit_tests/live_view/test_status_line.py ........",
    "tests/unit_tests/live_view/test_view_manager.py .........",
    "tests/unit_tests/test_unit_api.py .....",
    "tests/unit_tests/test_unit_fixtures.py .............",
    "tests/unit_tests/test_unit_grouping.py ...................",
    "tests/unit_tests/test_unit_markers.py ...................",
    "tests/unit_tests/test_unit_plugin.py .........",
    "tests/unit_tests/test_unit_runner.py ....................",
    "tests/unit_tests/test_unit_stream_proxy.py .........",
    "284/284 [100%]",
]

_MAX_LATENCY_MS = 20


class WriteTracker(io.StringIO):
    """StringIO that records timestamps of write() calls."""

    def __init__(self) -> None:
        super().__init__()
        self.write_times: list[float] = []
        self._lock = threading.Lock()

    def write(self, s: str) -> int:
        with self._lock:
            self.write_times.append(time.monotonic())
        return super().write(s)

    def last_write_time(self) -> float:
        with self._lock:
            return self.write_times[-1] if self.write_times else 0.0

    def clear_times(self) -> None:
        with self._lock:
            self.write_times.clear()


class AsyncInputReader:
    """Fake InputReader that supports async injection + notify."""

    def __init__(self, notify: threading.Event) -> None:
        self._queue: queue.Queue[InputEvent] = queue.Queue()
        self._notify = notify

    def drain(self) -> list[InputEvent]:
        events: list[InputEvent] = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    def inject(self, event: InputEvent) -> None:
        self._queue.put(event)
        self._notify.set()

    def stop(self) -> None:
        pass


def _setup_post_test_vm(
    width: int = 200, height: int = 24
) -> tuple[WriteTracker, ViewManager, AsyncInputReader]:
    """Build a ViewManager in the post-test state with realistic content.

    Uses a WriteTracker as the output file so we can measure when
    the display actually writes (not just when _user_scroll changes).

    Bypasses ``ensure_entered()`` to avoid starting a real InputReader
    on stdin / /dev/tty which would hang in CI.
    """
    f = WriteTracker()
    vm = ViewManager(f, width)
    vm._height = height
    vm._display._height = height

    # Mark as entered WITHOUT calling ensure_entered (which opens tty).
    vm._entered = True
    vm._display._in_alt = True

    # Populate buffer directly.
    for line in _SESSION_LINES:
        row = vm._compat_buffer.add_lines(1)
        vm._compat_buffer.set_line(row, line)
        vm._header_lines += 1

    # Wire up async input reader BEFORE starting refresh loop.
    reader = AsyncInputReader(notify=vm._dirty)
    vm._input_reader = reader

    # Enter post-test state.
    vm._status_line.set_text("tests complete \u2014 press Ctrl+C to exit")
    vm._dirty.set()

    # Start only the refresh loop (not the input reader).
    vm._start_refresh_loop()
    time.sleep(0.05)

    return f, vm, reader


def _measure_scroll_latency(
    f: WriteTracker,
    vm: ViewManager,
    reader: AsyncInputReader,
    event: InputEvent,
) -> float:
    """Inject *event*, return ms until the display actually redraws."""
    scroll_before = vm._user_scroll
    write_count_before = len(f.write_times)
    t0 = time.monotonic()
    reader.inject(event)
    # Spin-wait for BOTH scroll state change AND display write.
    deadline = t0 + 0.5
    while time.monotonic() < deadline:
        scroll_changed = vm._user_scroll != scroll_before
        new_writes = len(f.write_times) > write_count_before
        if scroll_changed and new_writes:
            return (time.monotonic() - t0) * 1000
        time.sleep(0.0001)  # 0.1 ms resolution
    return (time.monotonic() - t0) * 1000


class TestScrollLatency:
    """Scroll latency must stay under 20 ms in post-test report view."""

    def test_mouse_scroll_up_latency(self):
        f, vm, reader = _setup_post_test_vm()
        try:
            for i in range(5):
                latency = _measure_scroll_latency(
                    f, vm, reader, MouseEvent(button=64, row=0, col=0, pressed=True)
                )
                assert latency < _MAX_LATENCY_MS, (
                    f"mouse scroll-up #{i}: {latency:.1f} ms > {_MAX_LATENCY_MS} ms"
                )
        finally:
            vm._stop_refresh_loop()

    def test_mouse_scroll_down_latency(self):
        f, vm, reader = _setup_post_test_vm()
        try:
            # First scroll up to have room to scroll down.
            reader.inject(KeyEvent(key="Home"))
            time.sleep(0.05)

            for i in range(5):
                latency = _measure_scroll_latency(
                    f, vm, reader, MouseEvent(button=65, row=0, col=0, pressed=True)
                )
                assert latency < _MAX_LATENCY_MS, (
                    f"mouse scroll-down #{i}: {latency:.1f} ms > {_MAX_LATENCY_MS} ms"
                )
        finally:
            vm._stop_refresh_loop()

    def test_arrow_key_up_latency(self):
        f, vm, reader = _setup_post_test_vm()
        try:
            for i in range(5):
                latency = _measure_scroll_latency(f, vm, reader, KeyEvent(key="Up"))
                assert latency < _MAX_LATENCY_MS, (
                    f"arrow-up #{i}: {latency:.1f} ms > {_MAX_LATENCY_MS} ms"
                )
        finally:
            vm._stop_refresh_loop()

    def test_arrow_key_down_latency(self):
        f, vm, reader = _setup_post_test_vm()
        try:
            # Scroll to top first.
            reader.inject(KeyEvent(key="Home"))
            time.sleep(0.05)

            for i in range(5):
                latency = _measure_scroll_latency(f, vm, reader, KeyEvent(key="Down"))
                assert latency < _MAX_LATENCY_MS, (
                    f"arrow-down #{i}: {latency:.1f} ms > {_MAX_LATENCY_MS} ms"
                )
        finally:
            vm._stop_refresh_loop()

    def test_mixed_events_latency(self):
        """Interleaved arrow keys and mouse scroll events."""
        f, vm, reader = _setup_post_test_vm()
        try:
            # Use few events to avoid hitting the scroll boundary.
            events = [
                MouseEvent(button=64, row=0, col=0, pressed=True),
                KeyEvent(key="Up"),
                MouseEvent(button=64, row=0, col=0, pressed=True),
                KeyEvent(key="Up"),
            ]
            for i, event in enumerate(events):
                latency = _measure_scroll_latency(f, vm, reader, event)
                assert latency < _MAX_LATENCY_MS, (
                    f"mixed #{i} ({event}): {latency:.1f} ms > {_MAX_LATENCY_MS} ms"
                )
        finally:
            vm._stop_refresh_loop()


# Raw terminal bytes for scroll/arrow events.
_SCROLL_UP_BYTES = b"\033[<64;1;1M"  # SGR mouse scroll up
_SCROLL_DOWN_BYTES = b"\033[<65;1;1M"  # SGR mouse scroll down
_ARROW_UP_BYTES = b"\033[A"
_ARROW_DOWN_BYTES = b"\033[B"


def _setup_pipe_vm(width: int = 200, height: int = 24) -> tuple[WriteTracker, ViewManager, int]:
    """Build a post-test ViewManager with a real InputReader on a pipe.

    Bypasses ``ensure_entered()`` to avoid opening the real terminal.
    """
    f = WriteTracker()
    vm = ViewManager(f, width)
    vm._height = height
    vm._display._height = height
    vm._entered = True
    vm._display._in_alt = True

    for line in _SESSION_LINES:
        row = vm._compat_buffer.add_lines(1)
        vm._compat_buffer.set_line(row, line)
        vm._header_lines += 1

    # Wire up a real InputReader on a pipe fd.
    read_fd, write_fd = os.pipe()
    vm._input_reader = InputReader(read_fd, notify=vm._dirty)
    vm._input_reader.start()

    vm._status_line.set_text("tests complete \u2014 press Ctrl+C to exit")
    vm._dirty.set()

    vm._start_refresh_loop()
    time.sleep(0.05)

    return f, vm, write_fd


def _measure_pipe_latency(f: WriteTracker, vm: ViewManager, wfd: int, raw: bytes) -> float:
    """Write raw bytes to pipe, return ms until display redraws."""
    before_scroll = vm._user_scroll
    before_writes = len(f.write_times)
    t0 = time.monotonic()
    os.write(wfd, raw)
    deadline = t0 + 0.5
    while time.monotonic() < deadline:
        if vm._user_scroll != before_scroll and len(f.write_times) > before_writes:
            return (time.monotonic() - t0) * 1000
        time.sleep(0.0001)
    return (time.monotonic() - t0) * 1000


class TestScrollLatencyRealPipe:
    """Same latency tests using a real pipe + real InputReader.

    Exercises the full path: raw bytes -> select() -> os.read()
    -> parse_events -> queue -> notify -> refresh loop
    -> _process_input -> redraw_buffer -> file.write().
    """

    def test_mouse_scroll_up_latency_pipe(self):
        f, vm, wfd = _setup_pipe_vm()
        try:
            for i in range(5):
                lat = _measure_pipe_latency(f, vm, wfd, _SCROLL_UP_BYTES)
                assert lat < _MAX_LATENCY_MS, f"pipe scroll-up #{i}: {lat:.1f} ms"
        finally:
            os.close(wfd)
            vm._stop_refresh_loop()
            vm._stop_input_reader()

    def test_arrow_key_up_latency_pipe(self):
        f, vm, wfd = _setup_pipe_vm()
        try:
            for i in range(5):
                lat = _measure_pipe_latency(f, vm, wfd, _ARROW_UP_BYTES)
                assert lat < _MAX_LATENCY_MS, f"pipe arrow-up #{i}: {lat:.1f} ms"
        finally:
            os.close(wfd)
            vm._stop_refresh_loop()
            vm._stop_input_reader()

    def test_mixed_events_latency_pipe(self):
        f, vm, wfd = _setup_pipe_vm()
        try:
            raw_events = [
                _SCROLL_UP_BYTES,
                _ARROW_UP_BYTES,
                _SCROLL_UP_BYTES,
                _ARROW_UP_BYTES,
            ]
            for i, raw in enumerate(raw_events):
                lat = _measure_pipe_latency(f, vm, wfd, raw)
                assert lat < _MAX_LATENCY_MS, f"pipe mixed #{i}: {lat:.1f} ms"
        finally:
            os.close(wfd)
            vm._stop_refresh_loop()
            vm._stop_input_reader()


def _setup_pty_vm(width: int = 120, height: int = 24) -> tuple[int, ViewManager, int]:
    """Build a post-test ViewManager using a real pty pair.

    Returns (master_fd, view_manager, slave_fd).  The master fd
    simulates the terminal emulator — write input bytes to it and
    read display output from it.  The slave fd is the "terminal"
    side used by the ViewManager for both display writes and input reads.

    Bypasses ``ensure_entered()`` and manually wires up the InputReader
    on the slave fd so it reads from the pty (not the real terminal).
    """
    master_fd, slave_fd = pty.openpty()

    # Set the slave to cbreak mode (no line buffering).
    tty.setcbreak(slave_fd)

    # Set the pty size so ViewManager sees the right height.
    winsize = struct.pack("HHHH", height, width, 0, 0)
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

    # Open a Python file object on the slave for the Display.
    slave_file = os.fdopen(os.dup(slave_fd), "w")

    vm = ViewManager(slave_file, width)
    vm._height = height
    vm._display._height = height
    vm._entered = True
    vm._display._in_alt = True
    # Point the Display's tty fd at the slave so ensure_cbreak works.
    vm._display._tty_fd = slave_fd

    # Populate the buffer directly.
    for line in _SESSION_LINES:
        row = vm._compat_buffer.add_lines(1)
        vm._compat_buffer.set_line(row, line)
        vm._header_lines += 1

    # Enable mouse tracking on the slave pty.
    slave_file.write("\033[?1000h\033[?1006h")
    slave_file.flush()

    # Drain display output so pty buffer doesn't fill.
    _drain_master(master_fd)

    # Wire up InputReader on the slave fd (reads from the pty).
    vm._input_reader = InputReader(slave_fd, notify=vm._dirty)
    vm._input_reader.start()

    # Enter post-test state.
    vm._status_line.set_text("tests complete \u2014 press Ctrl+C to exit")
    vm._dirty.set()

    vm._start_refresh_loop()
    time.sleep(0.05)
    _drain_master(master_fd)

    return master_fd, vm, slave_fd


def _drain_master(master_fd: int, timeout: float = 0.05) -> bytes:
    """Read and discard all pending output from the pty master."""
    chunks = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master_fd], [], [], 0.01)
        if ready:
            try:
                chunks.append(os.read(master_fd, 65536))
            except OSError:
                break
        else:
            break
    return b"".join(chunks)


def _measure_pty_latency(master_fd: int, vm: ViewManager, raw: bytes) -> float:
    """Write raw bytes to pty master, return ms until scroll changes."""
    scroll_before = vm._user_scroll
    t0 = time.monotonic()
    os.write(master_fd, raw)
    deadline = t0 + 0.5
    while time.monotonic() < deadline:
        if vm._user_scroll != scroll_before:
            elapsed = (time.monotonic() - t0) * 1000
            # Drain display output to prevent pty buffer from filling.
            _drain_master(master_fd, timeout=0.01)
            return elapsed
        time.sleep(0.0001)
    # Drain and report what the InputReader saw.
    _drain_master(master_fd, timeout=0.01)
    return (time.monotonic() - t0) * 1000


class TestScrollLatencyPty:
    """Scroll latency tests using a real pseudo-terminal.

    This exercises the full kernel tty path including cbreak mode,
    mouse tracking enable/disable, and pty I/O — matching real usage
    more closely than pipe-based tests.
    """

    def test_mouse_scroll_arrives_on_pty(self):
        """Mouse scroll events written to the pty master reach the
        InputReader and change the viewport scroll offset."""
        master_fd, vm, slave_fd = _setup_pty_vm()
        try:
            for i in range(5):
                lat = _measure_pty_latency(master_fd, vm, _SCROLL_UP_BYTES)
                assert lat < _MAX_LATENCY_MS, (
                    f"pty scroll-up #{i}: {lat:.1f} ms > {_MAX_LATENCY_MS} ms"
                )
        finally:
            vm._stop_refresh_loop()
            vm._stop_input_reader()
            os.close(master_fd)
            os.close(slave_fd)

    def test_arrow_keys_arrive_on_pty(self):
        """Arrow key events travel through the pty correctly."""
        master_fd, vm, slave_fd = _setup_pty_vm()
        try:
            for i in range(5):
                lat = _measure_pty_latency(master_fd, vm, _ARROW_UP_BYTES)
                assert lat < _MAX_LATENCY_MS, (
                    f"pty arrow-up #{i}: {lat:.1f} ms > {_MAX_LATENCY_MS} ms"
                )
        finally:
            vm._stop_refresh_loop()
            vm._stop_input_reader()
            os.close(master_fd)
            os.close(slave_fd)

    def test_mouse_tracking_survives_content_writes(self):
        """Mouse events still arrive after content with ANSI codes
        has been written to the display (simulating summary output)."""
        master_fd, vm, slave_fd = _setup_pty_vm()
        try:
            # Simulate pytest summary output with ANSI markup.
            summary_lines = [
                "",
                "\033[1m" + "=" * 60 + " short test summary " + "=" * 60 + "\033[0m",
                "\033[31mFAILED\033[0m tests/test_foo.py::test_bar - assert 1 == 2",
                "\033[1m" + "=" * 60 + " 1 failed, 484 passed " + "=" * 60 + "\033[0m",
            ]
            for line in summary_lines:
                vm.add_content(line)
            vm._dirty.set()
            time.sleep(0.05)
            _drain_master(master_fd)

            # Now send mouse scroll — should still work.
            for i in range(5):
                lat = _measure_pty_latency(master_fd, vm, _SCROLL_UP_BYTES)
                assert lat < _MAX_LATENCY_MS, f"pty post-summary scroll #{i}: {lat:.1f} ms"
        finally:
            vm._stop_refresh_loop()
            vm._stop_input_reader()
            os.close(master_fd)
            os.close(slave_fd)

    def test_rapid_scroll_total_delta(self):
        """Rapid scroll events produce the correct total scroll delta.

        The pty may coalesce multiple writes into a single read, so we
        check the cumulative scroll offset rather than counting individual
        state changes.  Each scroll-up event moves by ``_SCROLL_LINES``
        (3 lines).
        """
        master_fd, vm, slave_fd = _setup_pty_vm()
        try:
            n_events = 20
            # Record initial scroll position.
            scroll_start = vm._user_scroll
            # Send all events rapidly.
            for _ in range(n_events):
                os.write(master_fd, _SCROLL_UP_BYTES)
            # Wait for processing to settle.
            time.sleep(0.3)
            _drain_master(master_fd, timeout=0.05)
            scroll_end = vm._user_scroll

            # Resolve None (auto-scroll = max offset).
            total = vm._compat_buffer.nlines
            vp = vm._viewport_height
            max_off = max(0, total - vp)
            start = max_off if scroll_start is None else scroll_start
            end = max_off if scroll_end is None else scroll_end

            actual_delta = start - end  # scroll-up decreases offset
            # Each scroll-up moves 3 lines; expect at least 80% of total.
            expected_min = int(n_events * 3 * 0.8)
            # But cap at how far we can actually scroll.
            expected_min = min(expected_min, start)
            assert actual_delta >= expected_min, (
                f"Scroll delta {actual_delta} < {expected_min} (start={start} end={end})"
            )
        finally:
            vm._stop_refresh_loop()
            vm._stop_input_reader()
            os.close(master_fd)
            os.close(slave_fd)
