"""Low-level terminal I/O: alternate screen, cbreak, raw writes."""

from __future__ import annotations

import contextlib
import os
import sys
import termios
import threading
import tty
from typing import TYPE_CHECKING

from pytest_threadpool._live_view._ansi import (
    clear_screen,
    disable_mouse_tracking,
    enable_mouse_tracking,
    enter_alt_screen,
    exit_alt_screen,
    hide_cursor,
    move_to,
    pad_line,
    show_cursor,
)

if TYPE_CHECKING:
    from typing import IO

    from pytest_threadpool._live_view._buffer import ScreenBuffer


import re

_ANSI_RE = re.compile(r"\033\[[^m]*m")
_HL_OTHER = "\033[48;5;238;37m"  # dark grey bg, white text
_HL_CURRENT = "\033[48;5;214;30m"  # orange bg, black text
_HL_END = "\033[0m"


def _highlight_matches(line: str, query: str, *, current: bool = False) -> str:
    """Highlight case-insensitive matches in a line, skipping ANSI codes.

    *current* selects the "active match" style (orange) vs the default
    (dark grey) for non-current matches.
    """
    if not query:
        return line
    hl = _HL_CURRENT if current else _HL_OTHER
    q = query.lower()
    parts = _ANSI_RE.split(line)
    codes = _ANSI_RE.findall(line)
    result: list[str] = []
    for i, part in enumerate(parts):
        lower = part.lower()
        pos = 0
        while pos < len(part):
            idx = lower.find(q, pos)
            if idx < 0:
                result.append(part[pos:])
                break
            result.append(part[pos:idx])
            result.append(hl)
            result.append(part[idx : idx + len(q)])
            result.append(_HL_END)
            pos = idx + len(q)
        if i < len(codes):
            result.append(codes[i])
    return "".join(result)


class Display:
    """Alternate-screen terminal display.

    Enters alt screen, sets cbreak mode, hides cursor.
    ``write_region`` writes pre-formatted lines to a rectangular area.
    ``redraw_buffer`` renders a ScreenBuffer viewport with auto-scroll
    and dirty-line tracking (backward-compatible path).
    """

    def __init__(self, file: IO[str], width: int, height: int) -> None:
        self._file = file
        self._width = width
        self._height = height
        self._in_alt = False
        self._mouse_enabled = False
        self._lock = threading.Lock()
        self._saved_termios: list | None = None
        self._tty_fd: int = -1
        # Dirty-tracking for redraw_buffer (backward-compat).
        self._rendered: dict[int, tuple[object, ...]] = {}
        self._scroll_offset = 0

    def enter(self) -> None:
        """Enter alternate screen, set cbreak mode, hide cursor."""
        self._tty_fd = self._get_tty_fd()
        if self._tty_fd >= 0:
            try:
                self._saved_termios = termios.tcgetattr(self._tty_fd)
                tty.setcbreak(self._tty_fd)
            except termios.error:
                self._saved_termios = None

        self._file.write(enter_alt_screen() + hide_cursor() + clear_screen())
        self._file.flush()
        self._in_alt = True

    def leave(self) -> None:
        """Leave alternate screen, restore terminal mode, show cursor."""
        if self._in_alt:
            if self._mouse_enabled:
                self.disable_mouse()
            self._file.write(show_cursor() + exit_alt_screen())
            self._file.flush()
            self._in_alt = False
            self._rendered.clear()

        if self._saved_termios is not None and self._tty_fd >= 0:
            with contextlib.suppress(termios.error):
                termios.tcsetattr(self._tty_fd, termios.TCSAFLUSH, self._saved_termios)
            self._saved_termios = None

    def ensure_cbreak(self) -> bool:
        """Re-assert cbreak mode on the tty fd.

        Called periodically to guarantee that character-at-a-time input
        is active even if another component (e.g. pytest's capture
        plugin cleanup) restored cooked mode.

        Returns ``True`` if the terminal was found in cooked mode and
        had to be fixed.
        """
        if self._tty_fd < 0:
            return False
        try:
            mode = termios.tcgetattr(self._tty_fd)
            was_cooked = bool(mode[3] & termios.ICANON)
            if was_cooked:
                # Clear ICANON and ECHO directly rather than calling
                # tty.setcbreak() which uses TCSAFLUSH and discards
                # any pending input.
                mode[3] = mode[3] & ~(termios.ICANON | termios.ECHO)
                mode[6][termios.VMIN] = 1
                mode[6][termios.VTIME] = 0
                termios.tcsetattr(self._tty_fd, termios.TCSANOW, mode)
            return was_cooked
        except termios.error:
            return False

    def enable_mouse(self) -> None:
        """Enable mouse tracking (SGR extended mode)."""
        if not self._mouse_enabled:
            self._file.write(enable_mouse_tracking())
            self._file.flush()
            self._mouse_enabled = True

    def force_enable_mouse(self) -> None:
        """Unconditionally re-send mouse tracking enable sequences.

        Use when mouse tracking may have been inadvertently disabled
        by content written to the terminal (e.g. pytest summary output
        containing escape sequences).
        """
        self._file.write(enable_mouse_tracking())
        self._file.flush()
        self._mouse_enabled = True

    def disable_mouse(self) -> None:
        """Disable mouse tracking."""
        if self._mouse_enabled:
            self._file.write(disable_mouse_tracking())
            self._file.flush()
            self._mouse_enabled = False

    def write_region(self, row: int, col: int, lines: list[str], width: int) -> None:
        """Write *lines* to a rectangular screen region starting at (*row*, *col*).

        Each line is assumed to already be padded/formatted to *width*.
        Row and col are 0-based.
        """
        with self._lock:
            parts: list[str] = []
            for i, line in enumerate(lines):
                parts.append(move_to(row + i + 1, col + 1))  # 1-based
                parts.append(line)
            if parts:
                self._file.write("".join(parts))
                self._file.flush()

    def redraw_buffer(
        self,
        buffer: ScreenBuffer,
        *,
        scroll_offset: int | None = None,
        status_text: str | None = None,
        hint_text: str | None = None,
        left_offset: int = 0,
        highlight: str = "",
        highlight_line: int = -1,
    ) -> None:
        """Render a ScreenBuffer viewport with dirty tracking.

        When *scroll_offset* is ``None`` (default), auto-scrolls to keep
        the bottom visible.  Pass an explicit offset to override.

        *left_offset* shifts rendering to start at a given column
        (0-based), reducing the available width.  Used for split-pane
        layouts where a side panel occupies the left columns.

        When *status_text* / *hint_text* are provided they are rendered
        on the bottom rows (spanning the full terminal width regardless
        of *left_offset*).
        """
        if not self._in_alt:
            return

        with self._lock:
            col = left_offset + 1  # 1-based terminal column
            content_width = self._width - left_offset - 1

            lines = buffer.snapshot()
            total = len(lines)
            reserved = (1 if status_text is not None else 0) + (1 if hint_text is not None else 0)
            vp = self._height - reserved

            if scroll_offset is not None:
                max_off = max(0, total - vp)
                self._scroll_offset = max(0, min(scroll_offset, max_off))
            elif total <= vp:
                self._scroll_offset = 0
            else:
                self._scroll_offset = total - vp

            parts: list[str] = []
            rows_to_show = min(total, vp)

            for screen_row in range(rows_to_show):
                buf_row = self._scroll_offset + screen_row
                content = lines[buf_row]
                cache_key = (
                    self._scroll_offset,
                    left_offset,
                    highlight,
                    highlight_line,
                    content,
                )
                if self._rendered.get(screen_row) == cache_key:
                    continue
                rendered_line = content
                if highlight:
                    is_current = buf_row == highlight_line
                    rendered_line = _highlight_matches(content, highlight, current=is_current)
                parts.append(move_to(screen_row + 1, col))
                parts.append(pad_line(rendered_line, content_width))
                self._rendered[screen_row] = cache_key

            for screen_row in range(rows_to_show, vp):
                empty_key = (self._scroll_offset, left_offset, "")
                if self._rendered.get(screen_row) == empty_key:
                    continue
                parts.append(move_to(screen_row + 1, col))
                parts.append(" " * content_width)
                self._rendered[screen_row] = empty_key

            # Status and hint bars align with the content pane.
            if status_text is not None:
                status_row = vp + 1
                rendered = f"\033[7m{pad_line(status_text, content_width)}\033[0m"
                status_key = (-1, left_offset, status_text)
                if self._rendered.get(status_row) != status_key:
                    parts.append(move_to(status_row, col))
                    parts.append(rendered)
                    self._rendered[status_row] = status_key

            if hint_text is not None:
                hint_row = self._height
                rendered_hint = f"\033[2m{pad_line(hint_text, content_width)}\033[0m"
                hint_key = (-2, left_offset, hint_text)
                if self._rendered.get(hint_row) != hint_key:
                    parts.append(move_to(hint_row, col))
                    parts.append(rendered_hint)
                    self._rendered[hint_row] = hint_key

            if parts:
                self._file.write("".join(parts))
                self._file.flush()

    def redraw_pane(self, lines: list[str], col: int, width: int) -> None:
        """Write lines into a left-side pane starting at column *col* (0-based)."""
        if not self._in_alt:
            return
        with self._lock:
            parts: list[str] = []
            for i, line in enumerate(lines[: self._height]):
                parts.append(move_to(i + 1, col + 1))
                parts.append(pad_line(line, width))
            for i in range(len(lines), self._height):
                parts.append(move_to(i + 1, col + 1))
                parts.append(" " * width)
            if parts:
                self._file.write("".join(parts))
                self._file.flush()

    def redraw_separator(self, col: int) -> None:
        """Draw a dim vertical separator at column *col* (0-based)."""
        if not self._in_alt:
            return
        with self._lock:
            parts: list[str] = []
            for row in range(1, self._height + 1):
                parts.append(move_to(row, col + 1))
                parts.append("\033[2m\u2502\033[0m")
            self._file.write("".join(parts))
            self._file.flush()

    def redraw_lines(self, lines: list[str]) -> None:
        """Write pre-formatted lines to fill the entire screen.

        Used for modal overlays that replace the normal buffer content.
        Invalidates the dirty cache so the next ``redraw_buffer`` call
        repaints everything.
        """
        if not self._in_alt:
            return
        with self._lock:
            parts: list[str] = []
            for i, line in enumerate(lines[: self._height]):
                parts.append(move_to(i + 1, 1))
                parts.append(pad_line(line, self._width - 1))
            for i in range(len(lines), self._height):
                parts.append(move_to(i + 1, 1))
                parts.append(" " * (self._width - 1))
            if parts:
                self._file.write("".join(parts))
                self._file.flush()
            self._rendered.clear()

    def dump_lines(self, lines: list[str]) -> None:
        """Print lines with colors to the file (after leaving alt screen)."""
        for line in lines:
            self._file.write(line + "\033[0m\n")
        self._file.flush()

    def flush(self) -> None:
        self._file.flush()

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def in_alt(self) -> bool:
        return self._in_alt

    def _get_tty_fd(self) -> int:
        """Get a file descriptor for the controlling terminal.

        Returns an existing fd — never opens new fds.  Opening extra
        fds to the same tty creates competing readers that share the
        kernel input buffer, causing event theft.  Uses only portable
        APIs (no ``/dev/tty``).
        """
        # Try the Display's own output file first.
        try:
            fd = self._file.fileno()
            if os.isatty(fd):
                return fd
        except (OSError, ValueError, AttributeError):
            pass
        # Try Python's sys.stdin (handles reassignment by plugins).
        try:
            fd = sys.stdin.fileno()
            if os.isatty(fd):
                return fd
        except (OSError, ValueError):
            pass
        # Try stdout / stderr raw fds as last resort.
        for candidate in (1, 2):
            try:
                if os.isatty(candidate):
                    return candidate
            except OSError:
                pass
        return -1
