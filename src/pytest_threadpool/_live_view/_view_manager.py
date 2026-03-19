"""ViewManager: orchestrates fields, display, status line, and lifecycle."""

from __future__ import annotations

import contextlib
import enum
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
from pytest_threadpool._live_view._tree_overlay import ItemTree, TreeOverlay

if TYPE_CHECKING:
    from typing import IO

# Scroll lines per mouse wheel notch.
_SCROLL_LINES = 3
# Target refresh rate for the background refresh thread.
_REFRESH_INTERVAL = 1.0 / 30  # ~30 fps


class Region(enum.StrEnum):
    """Identifiers for independently-redrawable screen regions."""

    CONTENT = "content"
    OVERLAY = "overlay"


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
        self._hint_text = (
            "  \u2191\u2193 scroll   PgUp/PgDn page   Home/End"
            "   Tab tree   Ctrl+\u2190\u2192 focus   Ctrl+C exit"
        )
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
        # Which pane owns keyboard input when split-pane is active.
        self._keyboard_focus: Region = Region.OVERLAY
        self._input_reader: InputReader | None = None
        self._refresh_thread: threading.Thread | None = None
        self._refresh_stop = threading.Event()
        # Region-based dirty tracking.  Any number of regions can be
        # registered by name (e.g. "content", "overlay", "tree",
        # "search").  ``_dirty_wake`` wakes the refresh loop;
        # ``_dirty_regions`` tracks which regions need redrawing.
        self._dirty_wake = threading.Event()
        self._dirty_regions: set[Region] = set()
        self._dirty_lock = threading.Lock()
        # Tree overlay (None when not shown).
        self._overlay: TreeOverlay | None = None
        self._test_tree: ItemTree | None = None
        # Configurable tree pane width (columns).  0 = auto (1/4 of width).
        self._tree_width_cfg: int = 0
        # Per-test output buffers keyed by nodeid.
        self._test_buffers: dict[str, ScreenBuffer] = {}
        # Which buffer the right pane is showing (None = main content).
        self._active_nodeid: str | None = None

    # --- Dirty-region helpers ---

    def _mark_dirty(self, *regions: Region) -> None:
        """Mark one or more regions as needing redraw."""
        with self._dirty_lock:
            self._dirty_regions.update(regions)
        self._dirty_wake.set()

    def _consume_dirty(self) -> set[Region]:
        """Return the set of dirty regions and clear them."""
        with self._dirty_lock:
            result = self._dirty_regions.copy()
            self._dirty_regions.clear()
        return result

    # --- Test tree / per-test output ---

    def add_test_items(self, nodeids: list[str]) -> None:
        """Add test item nodeids to the tree.

        Called per parallel group.  New nodeids are inserted into
        the existing tree; duplicates are ignored.
        """
        if self._test_tree is None:
            self._test_tree = ItemTree(nodeids)
        else:
            for nid in nodeids:
                self._test_tree._build([nid])
        if self._overlay is not None:
            self._overlay._rebuild()
            self._mark_dirty(Region.OVERLAY)

    def set_test_output(self, nodeid: str, lines: list[str]) -> None:
        """Store captured output lines for a specific test.

        Called by the runner after each test completes.  If the user
        is currently viewing this test's output, the content pane
        is refreshed.
        """
        buf = ScreenBuffer()
        if lines:
            row = buf.add_lines(len(lines))
            for i, line in enumerate(lines):
                buf.set_line(row + i, line)
        self._test_buffers[nodeid] = buf
        if self._active_nodeid == nodeid:
            self._mark_dirty(Region.CONTENT)

    @property
    def _active_buffer(self) -> ScreenBuffer:
        """The buffer currently shown in the content pane."""
        if self._active_nodeid is not None:
            buf = self._test_buffers.get(self._active_nodeid)
            if buf is None:
                # Test hasn't finished yet — show a placeholder.
                buf = ScreenBuffer()
                row = buf.add_lines(2)
                buf.set_line(row, self._active_nodeid)
                buf.set_line(row + 1, "\033[2m(running...)\033[0m")
                self._test_buffers[self._active_nodeid] = buf
            return buf
        return self._compat_buffer

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
        self._mark_dirty(Region.CONTENT)
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
        self._mark_dirty(Region.CONTENT)

    def allocate_lines(self, n: int) -> int:
        """Reserve *n* rows in the compat buffer."""
        self.ensure_entered()
        return self._compat_buffer.add_lines(n)

    def set_line(self, row: int, content: str) -> None:
        """Update a compat buffer row."""
        self._compat_buffer.set_line(row, content)
        self._mark_dirty(Region.CONTENT)

    def redraw(self) -> None:
        """Redraw the visible viewport immediately.

        Called by the runner thread when content changes.  When the
        tree overlay is active, marks content dirty so the refresh
        loop renders it in the right pane.
        """
        if self._overlay is not None:
            self._mark_dirty(Region.CONTENT)
            return
        self._display.redraw_buffer(
            self._active_buffer,
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

    @property
    def _tree_pane_width(self) -> int:
        """Width of the tree pane (0 when overlay is closed)."""
        if self._overlay is None or self._width < 80:
            return 0
        if self._tree_width_cfg > 0:
            return min(self._tree_width_cfg, self._width // 2)
        return max(25, self._width // 4)

    def _process_input(self) -> bool:
        """Drain all queued input events and route them.

        In split-pane mode:
        - Mouse scroll goes to whichever pane the cursor is over.
        - Keyboard events go to the focused pane (``_keyboard_focus``).
        - ``Ctrl+Left`` / ``Ctrl+Right`` switches keyboard focus.
        - ``Tab`` toggles the tree overlay on/off.

        Returns ``True`` if any events were processed.
        """
        if self._input_reader is None:
            return False
        events = self._input_reader.drain()
        if not events:
            return False

        tree_w = self._tree_pane_width
        overlay_changed = False
        content_changed = False

        for event in events:
            # --- Tab: toggle overlay ---
            if isinstance(event, KeyEvent) and event.key == "Tab":
                if self._overlay is not None:
                    self._overlay = None
                    self._active_nodeid = None
                    self._user_scroll = None
                    self._display._rendered.clear()
                    self._mark_dirty(Region.CONTENT)
                    return True
                if self._test_tree is not None:
                    pw = tree_w if tree_w > 0 else None
                    self._overlay = TreeOverlay(
                        self._test_tree,
                        self._width,
                        self._height,
                        pane_width=pw,
                    )
                    self._keyboard_focus = Region.OVERLAY
                    self._display._rendered.clear()
                    self._mark_dirty(Region.OVERLAY, Region.CONTENT)
                    return True
                continue

            # --- Focus switching: Ctrl+Left / Ctrl+Right ---
            if (
                isinstance(event, KeyEvent)
                and self._overlay is not None
                and event.key in ("Ctrl+Left", "Ctrl+Right")
            ):
                if event.key == "Ctrl+Left":
                    self._keyboard_focus = Region.OVERLAY
                else:
                    self._keyboard_focus = Region.CONTENT
                continue

            # --- Mouse scroll: route by column position ---
            if isinstance(event, MouseEvent) and event.button in (64, 65):
                mouse_delta = -_SCROLL_LINES if event.button == 64 else _SCROLL_LINES
                if self._overlay is not None and tree_w > 0 and event.col < tree_w:
                    self._overlay.scroll(mouse_delta)
                    overlay_changed = True
                else:
                    content_changed = self._apply_content_scroll(delta=mouse_delta)
                continue

            # --- Keyboard events ---
            if isinstance(event, KeyEvent):
                if self._overlay is not None and self._keyboard_focus == Region.OVERLAY:
                    result = self._overlay.handle_key(event.key)
                    if result == "close":
                        # Return to main summary view.
                        self._active_nodeid = None
                        self._user_scroll = None
                        self._display._rendered.clear()
                        self._mark_dirty(Region.CONTENT, Region.OVERLAY)
                        return True
                    if result is not None and result.startswith("jumpgroup:"):
                        # Switch right pane to combined group output.
                        nodeids = result[10:].split("\t")
                        self._show_group(nodeids)
                        overlay_changed = True
                        continue
                    if result is not None and result.startswith("jump:"):
                        # Switch right pane to a single test's output.
                        self._active_nodeid = result[5:]
                        self._user_scroll = None
                        self._display._rendered.clear()
                        self._mark_dirty(Region.CONTENT)
                        overlay_changed = True
                        continue
                    overlay_changed = True
                else:
                    content_changed = self._apply_content_key(event.key) or content_changed

        if overlay_changed:
            self._mark_dirty(Region.OVERLAY)
        if content_changed:
            self._mark_dirty(Region.CONTENT)
        return overlay_changed or content_changed

    def _apply_content_scroll(self, *, delta: int) -> bool:
        """Apply a scroll delta to the content pane. Returns True if changed."""
        total = self._active_buffer.nlines
        vp = self._viewport_height
        if total <= vp:
            return False
        max_off = total - vp
        if self._user_scroll is None:
            self._user_scroll = max_off
        self._user_scroll = max(0, min(self._user_scroll + delta, max_off))
        if self._user_scroll >= max_off:
            self._user_scroll = None
        return True

    def _show_group(self, nodeids: list[str]) -> None:
        """Build a combined buffer from multiple test outputs and show it."""
        group_key = "\t".join(nodeids)
        buf = ScreenBuffer()
        row = 0
        for nid in nodeids:
            test_buf = self._test_buffers.get(nid)
            if test_buf is not None:
                for line in test_buf.snapshot():
                    r = buf.add_lines(1)
                    buf.set_line(r, line)
                    row = r + 1
            else:
                r = buf.add_lines(2)
                buf.set_line(r, nid)
                buf.set_line(r + 1, "\033[2m(running...)\033[0m")
                row = r + 2
            # Separator between tests.
            if row > 0:
                r = buf.add_lines(1)
                buf.set_line(r, "")
                row = r + 1
        self._test_buffers[group_key] = buf
        self._active_nodeid = group_key
        self._user_scroll = None
        self._display._rendered.clear()
        self._mark_dirty(Region.CONTENT)

    def _apply_content_key(self, key: str) -> bool:
        """Apply a keyboard event to the content pane. Returns True if changed."""
        total = self._active_buffer.nlines
        vp = self._viewport_height
        if total <= vp:
            return False
        delta = 0
        if key == "Up":
            delta = -1
        elif key == "Down":
            delta = 1
        elif key == "PageUp":
            delta = -vp
        elif key == "PageDown":
            delta = vp
        elif key == "Home":
            self._user_scroll = 0
            return True
        elif key == "End":
            self._user_scroll = None
            return True
        else:
            return False
        return self._apply_content_scroll(delta=delta)

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
        self._mark_dirty(Region.CONTENT)

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

        Wakes when any region is marked dirty.  Only redraws the
        regions that actually changed — overlay and content are
        independent so background test updates don't cause the
        overlay to flicker.
        """
        cbreak_interval = 0.5
        last_cbreak = 0.0
        while not self._refresh_stop.is_set():
            self._dirty_wake.wait(timeout=_REFRESH_INTERVAL)
            self._dirty_wake.clear()
            if self._refresh_stop.is_set():
                break

            now = time.monotonic()
            if now - last_cbreak >= cbreak_interval:
                self._display.ensure_cbreak()
                last_cbreak = now

            self._process_input()
            dirty = self._consume_dirty()
            tree_w = self._tree_pane_width

            buf = self._active_buffer
            if self._overlay is not None and tree_w > 0:
                # Split-pane mode: tree on left, content on right.
                if Region.OVERLAY in dirty:
                    self._display.redraw_pane(self._overlay.render(), 0, tree_w)
                    self._display.redraw_separator(tree_w)
                if Region.CONTENT in dirty:
                    self._display.redraw_buffer(
                        buf,
                        scroll_offset=self._user_scroll,
                        status_text=self._status_line.text or None,
                        hint_text=self._hint_text or None,
                        left_offset=tree_w + 1,
                    )
            elif self._overlay is not None:
                # Narrow terminal — full-screen overlay fallback.
                if Region.OVERLAY in dirty:
                    self._display.redraw_lines(self._overlay.render())
            elif Region.CONTENT in dirty:
                self._display.redraw_buffer(
                    buf,
                    scroll_offset=self._user_scroll,
                    status_text=self._status_line.text or None,
                    hint_text=self._hint_text or None,
                )

    def _stop_refresh_loop(self) -> None:
        """Stop the background refresh thread."""
        self._refresh_stop.set()
        self._dirty_wake.set()  # Unblock wait() so the thread exits promptly.
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
            self._input_reader = InputReader(fd, notify=self._dirty_wake)
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
