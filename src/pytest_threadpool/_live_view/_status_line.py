"""Fixed status line pinned to top or bottom of terminal."""

from __future__ import annotations

import enum

from pytest_threadpool._live_view._ansi import pad_line


class Position(enum.Enum):
    TOP = "top"
    BOTTOM = "bottom"


class StatusLine:
    """A single-line region pinned to the top or bottom of the viewport.

    Does not scroll.  Renders a single line of text, padded/truncated
    to the given width.
    """

    def __init__(self, position: Position = Position.BOTTOM) -> None:
        self._position = position
        self._text = ""

    def set_text(self, text: str) -> None:
        """Update the status line content."""
        self._text = text

    @property
    def text(self) -> str:
        return self._text

    def render(self, width: int) -> str:
        """Return the padded/truncated status line with reverse-video styling."""
        # \033[7m = reverse video, makes the status line visually distinct.
        return f"\033[7m{pad_line(self._text, width)}\033[0m"

    @property
    def position(self) -> Position:
        return self._position

    @property
    def height(self) -> int:
        """Status line always occupies exactly 1 row."""
        return 1
