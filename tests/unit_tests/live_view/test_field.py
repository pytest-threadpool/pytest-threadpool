"""Unit tests for Field and splitting."""

import pytest

from pytest_threadpool._live_view import Field, SplitDirection, _visible_len
from tests.unit_tests.live_view.conftest import strip_ansi


class TestField:
    """Field is a rectangular working area backed by a ScreenBuffer."""

    def test_leaf_field_accepts_content(self):
        f = Field("main")
        start = f.add_lines(3)
        assert start == 0
        f.set_line(0, "hello")
        f.set_line(1, "world")
        assert f.buffer.snapshot() == ["hello", "world", ""]

    def test_name_property(self):
        f = Field("test-field")
        assert f.name == "test-field"

    def test_is_leaf_by_default(self):
        f = Field("x")
        assert f.is_leaf is True
        assert f.children is None
        assert f.split_direction is None

    def test_scroll_to(self):
        f = Field("main")
        f.add_lines(20)
        f.scroll_to(5)
        assert f.scroll_offset == 5

    def test_scroll_to_clamps_negative(self):
        f = Field("main")
        f.scroll_to(-10)
        assert f.scroll_offset == 0

    def test_scroll_by(self):
        f = Field("main")
        f.add_lines(20)
        f.scroll_by(5, viewport_height=10)
        assert f.scroll_offset == 5

    def test_scroll_by_clamps_to_max(self):
        f = Field("main")
        f.add_lines(20)
        f.scroll_by(100, viewport_height=10)
        assert f.scroll_offset == 10  # 20 - 10

    def test_scroll_by_clamps_negative(self):
        f = Field("main")
        f.add_lines(20)
        f.scroll_to(5)
        f.scroll_by(-100, viewport_height=10)
        assert f.scroll_offset == 0

    def test_visible_lines_basic(self):
        f = Field("main")
        f.add_lines(3)
        f.set_line(0, "aaa")
        f.set_line(1, "bbb")
        f.set_line(2, "ccc")
        lines = f.visible_lines(viewport_height=5, viewport_width=10)
        assert len(lines) == 5
        assert "aaa" in strip_ansi(lines[0])
        assert "bbb" in strip_ansi(lines[1])
        assert "ccc" in strip_ansi(lines[2])

    def test_visible_lines_scrolled(self):
        f = Field("main")
        f.add_lines(10)
        for i in range(10):
            f.set_line(i, f"line{i}")
        f.scroll_to(5)
        lines = f.visible_lines(viewport_height=3, viewport_width=20)
        assert len(lines) == 3
        plain = [strip_ansi(ln) for ln in lines]
        assert "line5" in plain[0]
        assert "line6" in plain[1]
        assert "line7" in plain[2]

    def test_visible_lines_padded_to_width(self):
        f = Field("main")
        f.add_lines(1)
        f.set_line(0, "hi")
        lines = f.visible_lines(viewport_height=3, viewport_width=20)
        for line in lines:
            assert _visible_len(line) == 20

    def test_visible_lines_empty_field(self):
        f = Field("empty")
        lines = f.visible_lines(viewport_height=5, viewport_width=10)
        assert len(lines) == 5
        for line in lines:
            assert line == " " * 10


class TestFieldSplit:
    """Splitting a field creates two children."""

    def test_split_creates_children(self):
        f = Field("root")
        first, second = f.split(SplitDirection.VERTICAL)
        assert not f.is_leaf
        assert f.children == (first, second)
        assert f.split_direction is SplitDirection.VERTICAL
        assert first.is_leaf
        assert second.is_leaf

    def test_split_names(self):
        f = Field("root")
        first, second = f.split(SplitDirection.HORIZONTAL)
        assert first.name == "root.0"
        assert second.name == "root.1"

    def test_split_ratio(self):
        f = Field("root")
        f.split(SplitDirection.VERTICAL, ratio=0.3)
        assert f.split_ratio == 0.3

    def test_split_field_rejects_content(self):
        f = Field("root")
        f.split(SplitDirection.VERTICAL)
        try:
            f.add_lines(1)
            pytest.fail("Expected RuntimeError")
        except RuntimeError:
            pass

    def test_double_split_raises(self):
        f = Field("root")
        f.split(SplitDirection.VERTICAL)
        try:
            f.split(SplitDirection.HORIZONTAL)
            pytest.fail("Expected RuntimeError")
        except RuntimeError:
            pass

    def test_invalid_ratio_raises(self):
        f = Field("root")
        try:
            f.split(SplitDirection.VERTICAL, ratio=0.0)
            pytest.fail("Expected ValueError")
        except ValueError:
            pass
        try:
            f.split(SplitDirection.VERTICAL, ratio=1.0)
            pytest.fail("Expected ValueError")
        except ValueError:
            pass

    def test_children_accept_content_independently(self):
        f = Field("root")
        first, second = f.split(SplitDirection.VERTICAL)
        first.add_lines(2)
        first.set_line(0, "top")
        second.add_lines(2)
        second.set_line(0, "bottom")
        assert first.buffer.snapshot() == ["top", ""]
        assert second.buffer.snapshot() == ["bottom", ""]

    def test_nested_split(self):
        root = Field("root")
        top, bottom = root.split(SplitDirection.VERTICAL)
        left, right = top.split(SplitDirection.HORIZONTAL)
        assert not root.is_leaf
        assert not top.is_leaf
        assert left.is_leaf
        assert right.is_leaf
        assert bottom.is_leaf

    def test_leaves(self):
        root = Field("root")
        top, bottom = root.split(SplitDirection.VERTICAL)
        left, right = top.split(SplitDirection.HORIZONTAL)
        leaves = root.leaves()
        assert leaves == [left, right, bottom]

    def test_leaves_single_field(self):
        f = Field("solo")
        assert f.leaves() == [f]
