"""Unit tests for LayoutManager."""

from pytest_threadpool._live_view import (
    Field,
    LayoutManager,
    Rect,
    SplitDirection,
    StatusLine,
)
from pytest_threadpool._live_view._status_line import Position


class TestLayoutManager:
    """LayoutManager computes screen rectangles from the field tree."""

    def test_single_field_fills_screen(self):
        lm = LayoutManager()
        root = Field("root")
        rects = lm.compute(root, screen_width=80, screen_height=24)
        assert rects == {"root": Rect(row=0, col=0, width=80, height=24)}

    def test_vertical_split(self):
        lm = LayoutManager()
        root = Field("root")
        top, bottom = root.split(SplitDirection.VERTICAL, ratio=0.5)
        rects = lm.compute(root, screen_width=80, screen_height=24)
        assert rects[top.name].row == 0
        assert rects[top.name].height == 12
        assert rects[bottom.name].row == 12
        assert rects[bottom.name].height == 12

    def test_horizontal_split(self):
        lm = LayoutManager()
        root = Field("root")
        left, right = root.split(SplitDirection.HORIZONTAL, ratio=0.5)
        rects = lm.compute(root, screen_width=80, screen_height=24)
        assert rects[left.name].col == 0
        assert rects[left.name].width == 40
        assert rects[right.name].col == 40
        assert rects[right.name].width == 40

    def test_status_line_bottom_reserves_row(self):
        lm = LayoutManager()
        root = Field("root")
        sl = StatusLine(Position.BOTTOM)
        rects = lm.compute(root, screen_width=80, screen_height=24, status_line=sl)
        assert rects["root"] == Rect(row=0, col=0, width=80, height=23)
        assert lm.status_line_row(24, sl) == 23

    def test_status_line_top_reserves_row(self):
        lm = LayoutManager()
        root = Field("root")
        sl = StatusLine(Position.TOP)
        rects = lm.compute(root, screen_width=80, screen_height=24, status_line=sl)
        assert rects["root"] == Rect(row=1, col=0, width=80, height=23)
        assert lm.status_line_row(24, sl) == 0

    def test_nested_split(self):
        lm = LayoutManager()
        root = Field("root")
        top, bottom = root.split(SplitDirection.VERTICAL, ratio=0.5)
        left, right = top.split(SplitDirection.HORIZONTAL, ratio=0.5)
        rects = lm.compute(root, screen_width=80, screen_height=24)

        assert rects[left.name] == Rect(row=0, col=0, width=40, height=12)
        assert rects[right.name] == Rect(row=0, col=40, width=40, height=12)
        assert rects[bottom.name] == Rect(row=12, col=0, width=80, height=12)

    def test_unequal_ratio(self):
        lm = LayoutManager()
        root = Field("root")
        top, bottom = root.split(SplitDirection.VERTICAL, ratio=0.25)
        rects = lm.compute(root, screen_width=80, screen_height=24)
        assert rects[top.name].height == 6  # int(24 * 0.25)
        assert rects[bottom.name].height == 18
