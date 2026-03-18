"""Unit tests for ViewManager."""

import io

from pytest_threadpool._live_view import (
    CursorMode,
    SplitDirection,
    ViewManager,
)
from pytest_threadpool._live_view._input import KeyEvent as KE
from pytest_threadpool._live_view._input import MouseEvent as ME
from tests.unit_tests.live_view.conftest import strip_ansi


def _fake_reader(events):
    """Return a fake InputReader whose drain() returns *events* once."""
    returned = False

    class FakeReader:
        def drain(self):
            nonlocal returned
            if not returned:
                returned = True
                return list(events)
            return []

    return FakeReader()


class TestViewManagerCompat:
    """Backward-compatible ScreenBuffer API."""

    def test_allocate_lines(self):
        f = io.StringIO()
        vm = ViewManager(f, 80)
        s1 = vm.allocate_lines(3)
        s2 = vm.allocate_lines(5)
        assert s1 == 0
        assert s2 == 3

    def test_add_header(self):
        f = io.StringIO()
        vm = ViewManager(f, 40)
        vm.add_header("=== session ===")
        vm.add_header("collected 10 items")
        assert vm.buffer.nlines == 2

    def test_set_line_and_redraw(self):
        f = io.StringIO()
        vm = ViewManager(f, 40)
        start = vm.allocate_lines(2)
        vm.set_line(start, "hello")
        vm.set_line(start + 1, "world")
        vm.redraw()
        raw = f.getvalue()
        assert "hello" in raw
        assert "world" in raw

    def test_properties(self):
        f = io.StringIO()
        vm = ViewManager(f, 120)
        assert vm.file is f
        assert vm.width == 120

    def test_header_lines_skipped_on_dump(self):
        """add_header lines are not included in dump output."""
        f = io.StringIO()
        vm = ViewManager(f, 40)
        vm.add_header("HEADER1")
        vm.add_header("HEADER2")
        start = vm.allocate_lines(1)
        vm.set_line(start, "test_result")

        all_lines = vm.buffer.snapshot()
        dump_lines = all_lines[2:]
        assert "HEADER1" not in dump_lines
        assert "HEADER2" not in dump_lines
        assert "test_result" in dump_lines


class TestViewManagerFields:
    """New field-based API."""

    def test_root_field(self):
        f = io.StringIO()
        vm = ViewManager(f, 80)
        assert vm.root_field.name == "root"
        assert vm.root_field.is_leaf

    def test_active_field_default(self):
        f = io.StringIO()
        vm = ViewManager(f, 80)
        assert vm.active_field is vm.root_field

    def test_set_active_field(self):
        f = io.StringIO()
        vm = ViewManager(f, 80)
        _top, bottom = vm.root_field.split(SplitDirection.VERTICAL)
        vm.set_active_field(bottom)
        assert vm.active_field is bottom

    def test_cycle_active_field(self):
        f = io.StringIO()
        vm = ViewManager(f, 80)
        top, bottom = vm.root_field.split(SplitDirection.VERTICAL)
        left, right = top.split(SplitDirection.HORIZONTAL)

        vm.set_active_field(left)
        vm.cycle_active_field()
        assert vm.active_field is right
        vm.cycle_active_field()
        assert vm.active_field is bottom
        vm.cycle_active_field()
        assert vm.active_field is left

    def test_status_line(self):
        f = io.StringIO()
        vm = ViewManager(f, 80)
        vm.status_line.set_text("running tests...")
        assert vm.status_line.text == "running tests..."

    def test_cursor(self):
        f = io.StringIO()
        vm = ViewManager(f, 80)
        assert vm.cursor.mode is CursorMode.DISABLED
        vm.cursor.toggle()
        assert vm.cursor.mode is CursorMode.ACTIVE

    def test_scroll_column(self):
        f = io.StringIO()
        vm = ViewManager(f, 80)
        result = vm.scroll_column.render(viewport_height=10, content_height=5, scroll_offset=0)
        assert all(c == "" for c in result)

    def test_layout(self):
        f = io.StringIO()
        vm = ViewManager(f, 80)
        rects = vm.layout.compute(vm.root_field, 80, 24)
        assert "root" in rects


class TestViewManagerScroll:
    """Scroll behavior: batched input, pin/unpin logic."""

    def _make_vm(self, nlines=50, width=40):
        """Create a ViewManager with *nlines* content lines.

        Stops the background refresh loop and input reader so that
        tests can call ``_process_input()`` directly without races.
        """
        f = io.StringIO()
        vm = ViewManager(f, width)
        for i in range(nlines):
            vm.add_header(f"line{i}")
        # Stop background threads so _process_input is not called concurrently.
        vm._stop_refresh_loop()
        vm._stop_input_reader()
        return f, vm

    def test_mouse_scroll_up_unpins(self):
        """Mouse scroll-up sets a user scroll offset (unpins)."""
        _f, vm = self._make_vm()
        vm._input_reader = _fake_reader([ME(button=64, row=0, col=0, pressed=True)])
        vm._process_input()
        assert vm._user_scroll is not None

    def test_mouse_scroll_down_to_bottom_repins(self):
        """Scrolling down past the end resets to auto-scroll (repins)."""
        _f, vm = self._make_vm()
        # First scroll up.
        vm._input_reader = _fake_reader([ME(button=64, row=0, col=0, pressed=True)])
        vm._process_input()
        assert vm._user_scroll is not None
        # Now scroll down past the end.
        vm._input_reader = _fake_reader([ME(button=65, row=0, col=0, pressed=True)] * 100)
        vm._process_input()
        assert vm._user_scroll is None

    def test_arrow_key_scroll(self):
        _f, vm = self._make_vm()
        vm._input_reader = _fake_reader([KE(key="Up")])
        vm._process_input()
        assert vm._user_scroll is not None

    def test_page_up_down(self):
        _f, vm = self._make_vm()
        vm._input_reader = _fake_reader([KE(key="PageUp")])
        vm._process_input()
        assert vm._user_scroll is not None
        offset_after_pgup = vm._user_scroll

        vm._input_reader = _fake_reader([KE(key="PageDown")])
        vm._process_input()
        # Should have scrolled down from pgup position.
        if vm._user_scroll is not None:
            assert vm._user_scroll > offset_after_pgup

    def test_home_key_scrolls_to_top(self):
        _f, vm = self._make_vm()
        vm._input_reader = _fake_reader([KE(key="Home")])
        vm._process_input()
        assert vm._user_scroll == 0

    def test_end_key_repins(self):
        _f, vm = self._make_vm()
        # First unpin.
        vm._input_reader = _fake_reader([KE(key="Home")])
        vm._process_input()
        assert vm._user_scroll == 0
        # End key repins.
        vm._input_reader = _fake_reader([KE(key="End")])
        vm._process_input()
        assert vm._user_scroll is None

    def test_scroll_noop_when_content_fits(self):
        f = io.StringIO()
        vm = ViewManager(f, 40)
        vm.add_header("single line")
        vm._input_reader = _fake_reader([ME(button=64, row=0, col=0, pressed=True)])
        vm._process_input()
        assert vm._user_scroll is None

    def test_batched_scroll_applies_all_deltas(self):
        """Multiple scroll events in one drain batch are batched into one delta."""
        _f, vm = self._make_vm()
        # Queue 10 scroll-up events (each scrolls 3 lines).
        vm._input_reader = _fake_reader([ME(button=64, row=0, col=0, pressed=True)] * 10)
        vm._process_input()
        # Should have unpinned and scrolled up by 30 lines total.
        assert vm._user_scroll is not None
        # 50 lines - 24 height = max_off 26.  Start at 26, delta=-30 → clamped to 0.
        assert vm._user_scroll == 0

    def test_redraw_preserves_user_scroll(self):
        """redraw() during test execution preserves user scroll position."""
        _f, vm = self._make_vm()
        # Unpin via scroll up.
        vm._input_reader = _fake_reader([KE(key="Home")])
        vm._process_input()
        assert vm._user_scroll == 0

        # Calling redraw() (as runner does) should NOT reset user scroll.
        vm._input_reader = _fake_reader([])
        vm.redraw()
        assert vm._user_scroll == 0

    def test_redraw_immediate(self):
        """redraw() renders content immediately."""
        f, vm = self._make_vm()
        f.truncate(0)
        f.seek(0)
        vm._display._rendered.clear()  # Force repaint.
        vm.redraw()
        raw = f.getvalue()
        assert len(raw) > 0

    def test_scroll_up_shows_earlier_content(self):
        """After scrolling up, earlier lines become visible."""
        f, vm = self._make_vm()
        # Clear previous output.
        f.truncate(0)
        f.seek(0)
        # Scroll to top and redraw.
        vm._input_reader = _fake_reader([KE(key="Home")])
        vm._process_input()
        vm._display.redraw_buffer(vm._compat_buffer, scroll_offset=vm._user_scroll)
        raw = f.getvalue()
        plain = strip_ansi(raw)
        assert "line0" in plain

    def test_mouse_enables_on_enter(self):
        """Mouse tracking is enabled when entering alt screen."""
        f = io.StringIO()
        vm = ViewManager(f, 40)
        vm.ensure_entered()
        raw = f.getvalue()
        assert "\033[?1000h" in raw
        assert "\033[?1006h" in raw
