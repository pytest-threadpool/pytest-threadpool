"""Unit tests for input parsing."""

from pytest_threadpool._live_view import KeyEvent, MouseEvent, parse_events


class TestParseEvents:
    """parse_events converts raw bytes to InputEvent objects."""

    def test_arrow_keys(self):
        data = b"\033[A\033[B\033[C\033[D"
        events = parse_events(data)
        assert events == [
            KeyEvent("Up"),
            KeyEvent("Down"),
            KeyEvent("Right"),
            KeyEvent("Left"),
        ]

    def test_printable_chars(self):
        data = b"abc"
        events = parse_events(data)
        assert events == [KeyEvent("a"), KeyEvent("b"), KeyEvent("c")]

    def test_tab(self):
        events = parse_events(b"\t")
        assert events == [KeyEvent("Tab")]

    def test_enter(self):
        events = parse_events(b"\r")
        assert events == [KeyEvent("Enter")]

    def test_ctrl_c(self):
        events = parse_events(b"\x03")
        assert events == [KeyEvent("Ctrl+C")]

    def test_escape(self):
        events = parse_events(b"\033")
        assert events == [KeyEvent("Escape")]

    def test_sgr_mouse_press(self):
        data = b"\033[<0;10;5M"
        events = parse_events(data)
        assert len(events) == 1
        assert isinstance(events[0], MouseEvent)
        assert events[0].button == 0
        assert events[0].col == 9  # 1-based -> 0-based
        assert events[0].row == 4
        assert events[0].pressed is True

    def test_sgr_mouse_release(self):
        data = b"\033[<0;10;5m"
        events = parse_events(data)
        assert len(events) == 1
        assert isinstance(events[0], MouseEvent)
        assert events[0].pressed is False

    def test_scroll_up_event(self):
        data = b"\033[<64;1;1M"
        events = parse_events(data)
        assert len(events) == 1
        assert isinstance(events[0], MouseEvent)
        assert events[0].button == 64

    def test_scroll_down_event(self):
        data = b"\033[<65;1;1M"
        events = parse_events(data)
        assert len(events) == 1
        assert isinstance(events[0], MouseEvent)
        assert events[0].button == 65

    def test_mixed_input(self):
        data = b"q\033[A\033[<64;5;10M"
        events = parse_events(data)
        assert len(events) == 3
        assert events[0] == KeyEvent("q")
        assert events[1] == KeyEvent("Up")
        assert isinstance(events[2], MouseEvent)
        assert events[2].button == 64

    def test_page_up_down(self):
        data = b"\033[5~\033[6~"
        events = parse_events(data)
        assert events == [KeyEvent("PageUp"), KeyEvent("PageDown")]

    def test_home_end(self):
        data = b"\033[H\033[F"
        events = parse_events(data)
        assert events == [KeyEvent("Home"), KeyEvent("End")]

    def test_backspace(self):
        events = parse_events(b"\x7f")
        assert events == [KeyEvent("Backspace")]
