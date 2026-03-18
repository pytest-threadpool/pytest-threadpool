"""Field: a rectangular working area backed by a ScreenBuffer.

Fields form a binary tree via splits.  Each leaf field has its own
buffer and scroll state.  Split (internal) nodes delegate content to
their children.
"""

from __future__ import annotations

import enum

from pytest_threadpool._live_view._ansi import pad_line
from pytest_threadpool._live_view._buffer import ScreenBuffer


class SplitDirection(enum.Enum):
    HORIZONTAL = "horizontal"  # side-by-side (left | right)
    VERTICAL = "vertical"  # stacked (top / bottom)


class Field:
    """A rectangular working area backed by a ScreenBuffer.

    Leaf fields own a buffer and accept content.
    Split fields are internal nodes whose children divide the space.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._buffer = ScreenBuffer()
        self._scroll_offset = 0
        # Split state (None for leaf fields).
        self._split_direction: SplitDirection | None = None
        self._children: tuple[Field, Field] | None = None
        self._split_ratio: float = 0.5

    # --- Identity ---

    @property
    def name(self) -> str:
        return self._name

    # --- Content API (leaf only) ---

    @property
    def buffer(self) -> ScreenBuffer:
        if not self.is_leaf:
            raise RuntimeError(f"Field {self._name!r} is split; access children instead")
        return self._buffer

    def add_lines(self, n: int) -> int:
        """Append *n* empty lines to this field's buffer."""
        return self.buffer.add_lines(n)

    def set_line(self, row: int, content: str) -> None:
        """Update a specific row in this field's buffer."""
        self.buffer.set_line(row, content)

    # --- Scroll state ---

    @property
    def scroll_offset(self) -> int:
        return self._scroll_offset

    def scroll_to(self, offset: int) -> None:
        """Set the scroll offset, clamped to valid range."""
        self._scroll_offset = max(0, offset)

    def scroll_by(self, delta: int, viewport_height: int) -> None:
        """Adjust scroll offset by *delta*, clamped to valid range."""
        max_offset = max(0, self._buffer.nlines - viewport_height)
        new = self._scroll_offset + delta
        self._scroll_offset = max(0, min(new, max_offset))

    # --- Split operations ---

    @property
    def is_leaf(self) -> bool:
        return self._children is None

    @property
    def children(self) -> tuple[Field, Field] | None:
        return self._children

    @property
    def split_direction(self) -> SplitDirection | None:
        return self._split_direction

    @property
    def split_ratio(self) -> float:
        return self._split_ratio

    def split(self, direction: SplitDirection, *, ratio: float = 0.5) -> tuple[Field, Field]:
        """Split this field into two children.

        Returns (first, second) where first is top/left and second is
        bottom/right depending on direction.  The current field becomes
        an internal node and no longer accepts direct content writes.
        """
        if not self.is_leaf:
            raise RuntimeError(f"Field {self._name!r} is already split")
        if not 0.0 < ratio < 1.0:
            raise ValueError(f"ratio must be between 0 and 1 exclusive, got {ratio}")

        first = Field(f"{self._name}.0")
        second = Field(f"{self._name}.1")
        self._split_direction = direction
        self._split_ratio = ratio
        self._children = (first, second)
        return first, second

    def leaves(self) -> list[Field]:
        """Return all leaf fields in depth-first order."""
        if self.is_leaf:
            return [self]
        assert self._children is not None
        return self._children[0].leaves() + self._children[1].leaves()

    # --- Rendering ---

    def visible_lines(self, viewport_height: int, viewport_width: int) -> list[str]:
        """Return the lines visible in the current viewport.

        Each line is padded/truncated to *viewport_width*.
        """
        if not self.is_leaf:
            return []

        lines = self._buffer.snapshot()
        total = len(lines)

        # Clamp scroll offset.
        max_offset = max(0, total - viewport_height)
        if self._scroll_offset > max_offset:
            self._scroll_offset = max_offset

        start = self._scroll_offset
        end = min(start + viewport_height, total)
        visible = lines[start:end]

        result = [pad_line(line, viewport_width) for line in visible]
        # Pad remaining viewport rows with empty lines.
        while len(result) < viewport_height:
            result.append(" " * viewport_width)
        return result
