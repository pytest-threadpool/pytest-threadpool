"""Cursor navigation state machine.

Disabled by default (like vim normal mode in many CLI tools).
Activated by hotkey to allow line-by-line/character navigation.
"""

from __future__ import annotations

import enum


class CursorMode(enum.Enum):
    DISABLED = "disabled"
    ACTIVE = "active"


class Cursor:
    """Cursor position and mode within a field.

    When DISABLED, arrow keys scroll the active field.
    When ACTIVE, arrow keys move the cursor and auto-scroll
    if the cursor exits the viewport.
    """

    def __init__(self) -> None:
        self._mode = CursorMode.DISABLED
        self._row = 0
        self._col = 0

    @property
    def mode(self) -> CursorMode:
        return self._mode

    def activate(self) -> None:
        self._mode = CursorMode.ACTIVE

    def deactivate(self) -> None:
        self._mode = CursorMode.DISABLED

    def toggle(self) -> None:
        if self._mode is CursorMode.DISABLED:
            self._mode = CursorMode.ACTIVE
        else:
            self._mode = CursorMode.DISABLED

    @property
    def row(self) -> int:
        return self._row

    @property
    def col(self) -> int:
        return self._col

    def move_up(self) -> None:
        self._row = max(0, self._row - 1)

    def move_down(self) -> None:
        self._row += 1

    def move_left(self) -> None:
        self._col = max(0, self._col - 1)

    def move_right(self) -> None:
        self._col += 1

    def move_to(self, row: int, col: int) -> None:
        self._row = max(0, row)
        self._col = max(0, col)

    def clamp(self, max_row: int, max_col: int) -> None:
        """Clamp cursor position to within bounds."""
        self._row = max(0, min(self._row, max_row))
        self._col = max(0, min(self._col, max_col))
