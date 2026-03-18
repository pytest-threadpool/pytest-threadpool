"""Layout engine: computes screen rectangles from the field tree."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from pytest_threadpool._live_view._field import SplitDirection

if TYPE_CHECKING:
    from pytest_threadpool._live_view._field import Field
    from pytest_threadpool._live_view._status_line import StatusLine


@dataclasses.dataclass(frozen=True)
class Rect:
    """A screen rectangle (0-based row/col)."""

    row: int
    col: int
    width: int
    height: int


class LayoutManager:
    """Computes the screen rectangle for each leaf field."""

    def compute(
        self,
        root_field: Field,
        screen_width: int,
        screen_height: int,
        status_line: StatusLine | None = None,
    ) -> dict[str, Rect]:
        """Walk the field tree and return {field.name: Rect} for every leaf."""
        from pytest_threadpool._live_view._status_line import Position

        available_top = 0
        available_height = screen_height

        if status_line is not None:
            if status_line.position is Position.TOP:
                available_top = 1
                available_height -= 1
            else:
                available_height -= 1

        root_rect = Rect(
            row=available_top,
            col=0,
            width=screen_width,
            height=available_height,
        )
        result: dict[str, Rect] = {}
        self._walk(root_field, root_rect, result)
        return result

    def status_line_row(
        self,
        screen_height: int,
        status_line: StatusLine,
    ) -> int:
        """Return the screen row (0-based) for the status line."""
        from pytest_threadpool._live_view._status_line import Position

        if status_line.position is Position.TOP:
            return 0
        return screen_height - 1

    def _walk(
        self,
        field: Field,
        rect: Rect,
        result: dict[str, Rect],
    ) -> None:
        if field.is_leaf:
            result[field.name] = rect
            return

        assert field.children is not None
        first, second = field.children
        ratio = field.split_ratio

        if field.split_direction is SplitDirection.VERTICAL:
            first_h = max(1, int(rect.height * ratio))
            second_h = max(1, rect.height - first_h)
            self._walk(first, Rect(rect.row, rect.col, rect.width, first_h), result)
            self._walk(
                second,
                Rect(rect.row + first_h, rect.col, rect.width, second_h),
                result,
            )
        else:
            first_w = max(1, int(rect.width * ratio))
            second_w = max(1, rect.width - first_w)
            self._walk(first, Rect(rect.row, rect.col, first_w, rect.height), result)
            self._walk(
                second,
                Rect(rect.row, rect.col + first_w, second_w, rect.height),
                result,
            )
