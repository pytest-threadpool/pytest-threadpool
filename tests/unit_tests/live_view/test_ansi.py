"""Unit tests for ANSI utilities."""

from pytest_threadpool._live_view import _visible_len
from pytest_threadpool._live_view._ansi import (
    clear_screen,
    disable_mouse_tracking,
    enable_mouse_tracking,
    enter_alt_screen,
    exit_alt_screen,
    hide_cursor,
    move_to,
    pad_line,
    reset_sgr,
    show_cursor,
    visible_len,
)
from tests.unit_tests.live_view.conftest import strip_ansi


class TestVisibleLen:
    def test_plain_text(self):
        assert visible_len("hello") == 5

    def test_with_ansi(self):
        assert visible_len("\033[32mhello\033[0m") == 5

    def test_empty(self):
        assert visible_len("") == 0

    def test_only_ansi(self):
        assert visible_len("\033[32m\033[0m") == 0

    def test_backward_compat_alias(self):
        assert _visible_len("hello") == 5


class TestPadLine:
    def test_pads_short_text(self):
        result = pad_line("hi", 10)
        plain = strip_ansi(result)
        assert len(plain) == 10
        assert plain.startswith("hi")

    def test_truncates_long_text(self):
        result = pad_line("A" * 20, 10)
        plain = strip_ansi(result)
        assert len(plain) == 10

    def test_preserves_ansi(self):
        result = pad_line("\033[32mhi\033[0m", 10)
        assert "\033[32m" in result
        plain = strip_ansi(result)
        assert len(plain) == 10

    def test_resets_at_end(self):
        result = pad_line("hi", 10)
        assert "\033[0m" in result

    def test_zero_width(self):
        assert pad_line("hello", 0) == ""


class TestEscapeBuilders:
    def test_move_to(self):
        assert move_to(1, 1) == "\033[1;1H"
        assert move_to(10, 20) == "\033[10;20H"

    def test_hide_show_cursor(self):
        assert hide_cursor() == "\033[?25l"
        assert show_cursor() == "\033[?25h"

    def test_alt_screen(self):
        assert enter_alt_screen() == "\033[?1049h"
        assert exit_alt_screen() == "\033[?1049l"

    def test_clear_screen(self):
        assert "\033[H" in clear_screen()
        assert "\033[2J" in clear_screen()

    def test_reset_sgr(self):
        assert reset_sgr() == "\033[0m"

    def test_mouse_tracking(self):
        assert "\033[?1000h" in enable_mouse_tracking()
        assert "\033[?1006h" in enable_mouse_tracking()
        assert "\033[?1000l" in disable_mouse_tracking()
        assert "\033[?1006l" in disable_mouse_tracking()
