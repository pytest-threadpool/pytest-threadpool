"""Unit tests for StatusLine."""

from pytest_threadpool._live_view import StatusLine
from pytest_threadpool._live_view._status_line import Position
from tests.unit_tests.live_view.conftest import strip_ansi


class TestStatusLine:
    """StatusLine is a fixed single-line region."""

    def test_default_position_is_bottom(self):
        sl = StatusLine()
        assert sl.position is Position.BOTTOM

    def test_set_text_and_render(self):
        sl = StatusLine()
        sl.set_text("hello world")
        rendered = sl.render(20)
        plain = strip_ansi(rendered)
        assert "hello world" in plain
        assert len(plain) == 20

    def test_render_truncates_long_text(self):
        sl = StatusLine()
        sl.set_text("A" * 50)
        rendered = sl.render(10)
        plain = strip_ansi(rendered)
        assert len(plain) == 10

    def test_render_pads_short_text(self):
        sl = StatusLine()
        sl.set_text("hi")
        rendered = sl.render(20)
        plain = strip_ansi(rendered)
        assert len(plain) == 20
        assert plain.startswith("hi")

    def test_height_is_always_one(self):
        sl = StatusLine()
        assert sl.height == 1

    def test_top_position(self):
        sl = StatusLine(Position.TOP)
        assert sl.position is Position.TOP

    def test_text_property(self):
        sl = StatusLine()
        assert sl.text == ""
        sl.set_text("test")
        assert sl.text == "test"

    def test_render_has_reverse_video(self):
        sl = StatusLine()
        sl.set_text("status")
        rendered = sl.render(20)
        assert "\033[7m" in rendered
        assert "\033[0m" in rendered
