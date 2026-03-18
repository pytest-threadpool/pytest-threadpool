"""Unit tests for Cursor."""

from pytest_threadpool._live_view import Cursor, CursorMode


class TestCursor:
    """Cursor navigation state machine."""

    def test_default_mode_is_disabled(self):
        c = Cursor()
        assert c.mode is CursorMode.DISABLED

    def test_activate(self):
        c = Cursor()
        c.activate()
        assert c.mode is CursorMode.ACTIVE

    def test_deactivate(self):
        c = Cursor()
        c.activate()
        c.deactivate()
        assert c.mode is CursorMode.DISABLED

    def test_toggle(self):
        c = Cursor()
        c.toggle()
        assert c.mode is CursorMode.ACTIVE
        c.toggle()
        assert c.mode is CursorMode.DISABLED

    def test_default_position(self):
        c = Cursor()
        assert c.row == 0
        assert c.col == 0

    def test_move_down(self):
        c = Cursor()
        c.move_down()
        c.move_down()
        assert c.row == 2

    def test_move_up(self):
        c = Cursor()
        c.move_to(5, 0)
        c.move_up()
        assert c.row == 4

    def test_move_up_clamps_at_zero(self):
        c = Cursor()
        c.move_up()
        assert c.row == 0

    def test_move_right(self):
        c = Cursor()
        c.move_right()
        c.move_right()
        assert c.col == 2

    def test_move_left(self):
        c = Cursor()
        c.move_to(0, 5)
        c.move_left()
        assert c.col == 4

    def test_move_left_clamps_at_zero(self):
        c = Cursor()
        c.move_left()
        assert c.col == 0

    def test_move_to(self):
        c = Cursor()
        c.move_to(10, 20)
        assert c.row == 10
        assert c.col == 20

    def test_move_to_clamps_negative(self):
        c = Cursor()
        c.move_to(-5, -3)
        assert c.row == 0
        assert c.col == 0

    def test_clamp(self):
        c = Cursor()
        c.move_to(100, 200)
        c.clamp(max_row=10, max_col=20)
        assert c.row == 10
        assert c.col == 20

    def test_clamp_no_change_when_within_bounds(self):
        c = Cursor()
        c.move_to(5, 5)
        c.clamp(max_row=10, max_col=10)
        assert c.row == 5
        assert c.col == 5
