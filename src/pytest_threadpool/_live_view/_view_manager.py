"""ViewManager: orchestrates fields, display, status line, and lifecycle."""

from __future__ import annotations

import contextlib
import os
import signal
import threading
import time
from typing import TYPE_CHECKING

from pytest_threadpool._live_view._buffer import ScreenBuffer
from pytest_threadpool._live_view._cursor import Cursor
from pytest_threadpool._live_view._display import Display
from pytest_threadpool._live_view._field import Field
from pytest_threadpool._live_view._input import InputReader, KeyEvent, MouseEvent
from pytest_threadpool._live_view._layout import LayoutManager
from pytest_threadpool._live_view._scroll_column import ScrollColumn
from pytest_threadpool._live_view._status_line import Position, StatusLine

if TYPE_CHECKING:
    from typing import IO

# Scroll lines per mouse wheel notch.
_SCROLL_LINES = 3
# Target refresh rate for the background refresh thread.
_REFRESH_INTERVAL = 1.0 / 30  # ~30 fps


class ViewManager:
    """Coordinates fields, display, status line, and lifecycle.

    Backward-compatible with the old single-buffer API used by
    ``_runner.py`` and ``plugin.py``.

    A dedicated background refresh thread (~30 fps) processes input
    events and redraws the display independently of the runner thread,
    ensuring scroll input is always responsive.
    """

    def __init__(self, file: IO[str], width: int) -> None:
        self._file = file
        self._width = width
        try:
            self._height = os.get_terminal_size(file.fileno()).lines
        except (OSError, ValueError):
            self._height = 24

        self._display = Display(file, width, self._height)
        self._root_field = Field("root")
        self._active_field: Field = self._root_field
        self._status_line = StatusLine(Position.BOTTOM)
        self._hint_text = "  \u2191\u2193 scroll   PgUp/PgDn page   Home/End   Ctrl+C exit"
        self._cursor = Cursor()
        self._layout = LayoutManager()
        self._scroll_column = ScrollColumn()
        self._entered = threading.Event()
        self._enter_lock = threading.Lock()

        # Backward-compat: a shared ScreenBuffer for the old API.
        self._compat_buffer = ScreenBuffer()
        # Number of header lines (skipped on dump since pytest prints them).
        self._header_lines = 0
        # User scroll offset (None = auto-scroll to bottom).
        self._user_scroll: int | None = None
        self._input_reader: InputReader | None = None
        self._refresh_thread: threading.Thread | None = None
        self._refresh_stop = threading.Event()
        # Set when the display needs a repaint (content or scroll changed).
        self._dirty = threading.Event()

    # --- Backward-compatible API (used by _runner.py) ---

    def ensure_entered(self) -> None:
        """Enter alt screen on first call.  No-op after that.

        Thread-safe: the ``_enter_lock`` serialises first entry, and
        ``_entered`` (a ``threading.Event``) is set inside the lock
        before starting background threads.  The ``is_set()`` fast
        path means subsequent calls avoid the lock entirely.
        """
        if self._entered.is_set():
            return
        with self._enter_lock:
            if self._entered.is_set():
                return
            self._display.enter()
            self._display.enable_mouse()
            # Set the flag *before* starting threads so that any
            # concurrent caller exits immediately and never creates
            # duplicate readers/refresh loops.
            self._entered.set()
            self._start_input_reader()
            self._start_refresh_loop()

    def add_header(self, text: str) -> None:
        """Add a header line (e.g. session info) to the compat buffer.

        Header lines are displayed on the alt screen but skipped on
        dump, since pytest's terminal reporter prints them to stdout.
        """
        self.ensure_entered()
        row = self._compat_buffer.add_lines(1)
        self._compat_buffer.set_line(row, text)
        self._header_lines += 1
        self._dirty.set()
        self._display.redraw_buffer(
            self._compat_buffer,
            status_text=self._status_line.text or None,
            hint_text=self._hint_text or None,
        )

    def add_content(self, text: str) -> None:
        """Add a content line to the compat buffer.

        Unlike ``add_header``, content lines are included in the dump
        after leaving the alt screen (e.g. the failure summary).
        """
        self.ensure_entered()
        row = self._compat_buffer.add_lines(1)
        self._compat_buffer.set_line(row, text)
        self._dirty.set()

    def allocate_lines(self, n: int) -> int:
        """Reserve *n* rows in the compat buffer."""
        self.ensure_entered()
        return self._compat_buffer.add_lines(n)

    def set_line(self, row: int, content: str) -> None:
        """Update a compat buffer row."""
        self._compat_buffer.set_line(row, content)
        self._dirty.set()

    def redraw(self) -> None:
        """Redraw the visible viewport immediately.

        Called by the runner thread when content changes.  Respects the
        current user scroll offset.  Input processing is handled by the
        background refresh thread (~30 fps) independently.
        """
        self._display.redraw_buffer(
            self._compat_buffer,
            scroll_offset=self._user_scroll,
            status_text=self._status_line.text or None,
            hint_text=self._hint_text or None,
        )

    @property
    def _viewport_height(self) -> int:
        """Content viewport height, accounting for status and hint lines."""
        reserved = 0
        if self._status_line.text:
            reserved += 1
        if self._hint_text:
            reserved += 1
        return self._height - reserved

    def _process_input(self) -> bool:
        """Drain all queued input events, batch scroll delta.

        Returns ``True`` if any scroll-affecting events were processed.
        Does NOT call redraw — the caller is responsible for that.
        """
        if self._input_reader is None:
            return False
        events = self._input_reader.drain()
        if not events:
            return False

        total = self._compat_buffer.nlines
        vp = self._viewport_height
        if total <= vp:
            return False

        delta = 0
        snap_home = False
        snap_end = False

        for event in events:
            if isinstance(event, MouseEvent):
                if event.button == 64:  # scroll up
                    delta -= _SCROLL_LINES
                elif event.button == 65:  # scroll down
                    delta += _SCROLL_LINES
            elif isinstance(event, KeyEvent):
                if event.key == "Up":
                    delta -= 1
                elif event.key == "Down":
                    delta += 1
                elif event.key == "PageUp":
                    delta -= vp
                elif event.key == "PageDown":
                    delta += vp
                elif event.key == "Home":
                    snap_home = True
                    snap_end = False
                    delta = 0
                elif event.key == "End":
                    snap_end = True
                    snap_home = False
                    delta = 0

        if snap_home:
            self._user_scroll = 0
        elif snap_end:
            self._user_scroll = None
        elif delta != 0:
            max_off = total - vp
            if self._user_scroll is None:
                self._user_scroll = max_off
            self._user_scroll = max(0, min(self._user_scroll + delta, max_off))
            if self._user_scroll >= max_off:
                self._user_scroll = None
        else:
            return False

        self._dirty.set()
        return True

    def wait_and_leave(self) -> None:
        """Show status prompt, wait for Ctrl+C, then leave + dump.

        The main thread only waits for Ctrl+C here.  All input
        processing and rendering is handled exclusively by the
        background refresh thread — no lock contention, no data race
        on ``_user_scroll``.
        """
        if not self._entered.is_set():
            return
        if threading.current_thread() is not threading.main_thread():
            return  # pragma: no cover

        # Re-assert cbreak mode and mouse tracking — pytest hooks that
        # ran between run_all() and here may have restored cooked
        # terminal mode or written escape sequences that disabled
        # mouse tracking.
        self._display.ensure_cbreak()
        self._display.force_enable_mouse()

        # Ensure the input reader is alive — it may have been stopped
        # by the device-level singleton if a duplicate was briefly
        # created before the enter lock took effect.
        self._start_input_reader()

        self._status_line.set_text("tests complete \u2014 press Ctrl+C to exit")
        self._dirty.set()

        stop = threading.Event()
        prev_handler = signal.getsignal(signal.SIGINT)

        def _handler(signum: int, frame: object) -> None:
            stop.set()

        signal.signal(signal.SIGINT, _handler)
        try:
            stop.wait()
        finally:
            signal.signal(signal.SIGINT, prev_handler)

        self._stop_refresh_loop()
        self._stop_input_reader()
        self._display.leave()
        # Skip header lines — pytest's terminal reporter prints them.
        all_lines = self._compat_buffer.snapshot()
        self._display.dump_lines(all_lines[self._header_lines :])

        with contextlib.suppress(KeyboardInterrupt):
            self._file.write("")

    def _start_refresh_loop(self) -> None:
        """Start the background refresh thread (~30 fps)."""
        self._refresh_stop.clear()
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop, daemon=True, name="live-view-refresh"
        )
        self._refresh_thread.start()

    def _refresh_loop(self) -> None:
        """Background loop: process input + redraw at ~30 fps.

        Wakes immediately when ``_dirty`` is set (by scroll input or
        content changes), otherwise polls at the refresh interval.

        Periodically re-asserts cbreak mode in case another component
        (e.g. pytest's capture plugin cleanup) restored cooked mode.
        """
        cbreak_interval = 0.5  # re-assert cbreak every 500 ms
        last_cbreak = 0.0
        while not self._refresh_stop.is_set():
            self._dirty.wait(timeout=_REFRESH_INTERVAL)
            if self._refresh_stop.is_set():
                break

            now = time.monotonic()
            if now - last_cbreak >= cbreak_interval:
                self._display.ensure_cbreak()
                last_cbreak = now

            self._process_input()
            if self._dirty.is_set():
                self._dirty.clear()
                self._display.redraw_buffer(
                    self._compat_buffer,
                    scroll_offset=self._user_scroll,
                    status_text=self._status_line.text or None,
                    hint_text=self._hint_text or None,
                )

    def _stop_refresh_loop(self) -> None:
        """Stop the background refresh thread."""
        self._refresh_stop.set()
        self._dirty.set()  # Unblock _dirty.wait() so the thread exits promptly.
        if self._refresh_thread is not None:
            self._refresh_thread.join(timeout=2)
            self._refresh_thread = None

    def _start_input_reader(self) -> None:
        """Start the background input reader if a tty fd is available.

        Reuses the Display's tty fd exclusively — opening additional
        fds to the same tty via ``/dev/tty`` would create competing
        readers sharing the kernel input buffer, causing event theft.
        """
        fd = self._display._tty_fd
        if fd >= 0:
            self._input_reader = InputReader(fd, notify=self._dirty)
            self._input_reader.start()

    def _stop_input_reader(self) -> None:
        if self._input_reader is not None:
            self._input_reader.stop()
            self._input_reader = None

    # --- New field-based API ---

    @property
    def root_field(self) -> Field:
        return self._root_field

    @property
    def active_field(self) -> Field:
        return self._active_field

    def set_active_field(self, field: Field) -> None:
        self._active_field = field

    def cycle_active_field(self) -> None:
        """Cycle the active field to the next leaf in depth-first order."""
        leaves = self._root_field.leaves()
        if not leaves:
            return
        try:
            idx = next(i for i, f in enumerate(leaves) if f is self._active_field)
            self._active_field = leaves[(idx + 1) % len(leaves)]
        except StopIteration:
            self._active_field = leaves[0]

    @property
    def status_line(self) -> StatusLine:
        return self._status_line

    @property
    def cursor(self) -> Cursor:
        return self._cursor

    @property
    def scroll_column(self) -> ScrollColumn:
        return self._scroll_column

    @property
    def layout(self) -> LayoutManager:
        return self._layout

    # --- Properties ---

    @property
    def file(self) -> IO[str]:
        return self._file

    @property
    def width(self) -> int:
        return self._width

    @property
    def display(self) -> Display:
        return self._display

    @property
    def buffer(self) -> ScreenBuffer:
        return self._compat_buffer
