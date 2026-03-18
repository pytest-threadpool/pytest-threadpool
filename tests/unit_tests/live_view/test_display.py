"""Unit tests for Display."""

import io
import threading

from pytest_threadpool._live_view import Display, ScreenBuffer
from tests.unit_tests.live_view.conftest import strip_ansi


class TestDisplay:
    """Display renders the visible viewport of a ScreenBuffer."""

    def _make_display(self, width=40, height=10):
        f = io.StringIO()
        d = Display(f, width, height)
        return f, d

    def test_enter_sends_alt_screen(self):
        f, d = self._make_display()
        d.enter()
        assert "\033[?1049h" in f.getvalue()

    def test_leave_sends_exit_alt_screen(self):
        f, d = self._make_display()
        d.enter()
        f.truncate(0)
        f.seek(0)
        d.leave()
        assert "\033[?1049l" in f.getvalue()

    def test_leave_without_enter_is_noop(self):
        f, d = self._make_display()
        d.leave()
        assert f.getvalue() == ""

    def test_redraw_buffer_paints_all_lines(self):
        f, d = self._make_display(width=20, height=5)
        buf = ScreenBuffer()
        buf.add_lines(3)
        buf.set_line(0, "line0")
        buf.set_line(1, "line1")
        buf.set_line(2, "progress")
        d.enter()
        f.truncate(0)
        f.seek(0)

        d.redraw_buffer(buf)
        raw = f.getvalue()
        assert "line0" in raw
        assert "line1" in raw
        assert "progress" in raw

    def test_redraw_buffer_only_dirty_lines(self):
        f, d = self._make_display(width=30, height=5)
        buf = ScreenBuffer()
        buf.add_lines(3)
        buf.set_line(0, "AAA")
        buf.set_line(1, "BBB")
        buf.set_line(2, "CCC")
        d.enter()
        d.redraw_buffer(buf)
        f.truncate(0)
        f.seek(0)

        buf.set_line(1, "XXX")
        d.redraw_buffer(buf)

        raw = f.getvalue()
        plain = strip_ansi(raw)
        assert "XXX" in plain
        assert "AAA" not in plain
        assert "CCC" not in plain

    def test_redraw_buffer_noop_when_clean(self):
        f, d = self._make_display()
        buf = ScreenBuffer()
        buf.add_lines(2)
        buf.set_line(0, "x")
        buf.set_line(1, "y")
        d.enter()
        d.redraw_buffer(buf)
        f.truncate(0)
        f.seek(0)

        d.redraw_buffer(buf)
        assert f.getvalue() == ""

    def test_auto_scroll_shows_latest(self):
        """When buffer exceeds viewport, auto-scrolls to show the bottom."""
        f, d = self._make_display(width=20, height=3)
        buf = ScreenBuffer()
        buf.add_lines(10)
        for i in range(10):
            buf.set_line(i, f"line{i}")
        d.enter()
        f.truncate(0)
        f.seek(0)

        d.redraw_buffer(buf)
        raw = f.getvalue()
        assert "line7" in raw
        assert "line8" in raw
        assert "line9" in raw
        assert "line0" not in raw

    def test_explicit_scroll_offset(self):
        """Passing scroll_offset overrides auto-scroll."""
        f, d = self._make_display(width=20, height=3)
        buf = ScreenBuffer()
        buf.add_lines(10)
        for i in range(10):
            buf.set_line(i, f"line{i}")
        d.enter()
        f.truncate(0)
        f.seek(0)

        d.redraw_buffer(buf, scroll_offset=2)
        raw = f.getvalue()
        assert "line2" in raw
        assert "line3" in raw
        assert "line4" in raw
        assert "line0" not in raw
        assert "line9" not in raw

    def test_scroll_offset_clamps_to_max(self):
        """Explicit scroll_offset beyond max is clamped."""
        f, d = self._make_display(width=20, height=3)
        buf = ScreenBuffer()
        buf.add_lines(10)
        for i in range(10):
            buf.set_line(i, f"line{i}")
        d.enter()
        f.truncate(0)
        f.seek(0)

        d.redraw_buffer(buf, scroll_offset=999)
        raw = f.getvalue()
        # Should show last 3 lines (clamped to max).
        assert "line7" in raw
        assert "line8" in raw
        assert "line9" in raw

    def test_scroll_offset_clamps_negative(self):
        """Negative scroll_offset is clamped to 0."""
        f, d = self._make_display(width=20, height=3)
        buf = ScreenBuffer()
        buf.add_lines(10)
        for i in range(10):
            buf.set_line(i, f"line{i}")
        d.enter()
        f.truncate(0)
        f.seek(0)

        d.redraw_buffer(buf, scroll_offset=-5)
        raw = f.getvalue()
        assert "line0" in raw
        assert "line1" in raw
        assert "line2" in raw

    def test_buffer_grows_and_scrolls(self):
        """Adding lines to a full buffer triggers auto-scroll."""
        f, d = self._make_display(width=20, height=3)
        buf = ScreenBuffer()
        buf.add_lines(2)
        buf.set_line(0, "first")
        buf.set_line(1, "second")
        d.enter()
        d.redraw_buffer(buf)

        start = buf.add_lines(3)
        for i in range(3):
            buf.set_line(start + i, f"new{i}")
        f.truncate(0)
        f.seek(0)
        d.redraw_buffer(buf)

        raw = f.getvalue()
        assert "new0" in raw
        assert "new1" in raw
        assert "new2" in raw

    def test_ansi_codes_preserved(self):
        f, d = self._make_display(width=20, height=5)
        buf = ScreenBuffer()
        buf.add_lines(1)
        buf.set_line(0, "\033[32mgreen\033[0m")
        d.enter()
        f.truncate(0)
        f.seek(0)

        d.redraw_buffer(buf)
        assert "\033[32m" in f.getvalue()

    def test_atomic_write(self):
        writes = []
        original_write = io.StringIO.write

        class TrackingIO(io.StringIO):
            def write(self, s):
                writes.append(s)
                return original_write(self, s)

        f = TrackingIO()
        d = Display(f, 40, 10)
        buf = ScreenBuffer()
        buf.add_lines(5)
        for i in range(5):
            buf.set_line(i, f"line{i}")
        d.enter()
        writes.clear()

        buf.set_line(0, "CHANGED0")
        buf.set_line(2, "CHANGED2")
        buf.set_line(4, "CHANGED4")
        d.redraw_buffer(buf)
        assert len(writes) == 1

    def test_dump_prints_all_lines_with_colors(self):
        f, d = self._make_display()
        buf = ScreenBuffer()
        buf.add_lines(3)
        buf.set_line(0, "\033[32mresult0\033[0m")
        buf.set_line(1, "result1")
        buf.set_line(2, "10/10 [100%]")
        f.truncate(0)
        f.seek(0)

        d.dump_lines(buf.snapshot())
        raw = f.getvalue()
        assert "\033[32mresult0" in raw
        assert "result1" in raw
        assert "10/10 [100%]" in raw

    def test_concurrent_redraw_safe(self):
        f = io.StringIO()
        d = Display(f, 80, 20)
        buf = ScreenBuffer()
        buf.add_lines(10)
        for i in range(10):
            buf.set_line(i, f"init{i}")
        d.enter()

        barrier = threading.Barrier(4)

        def updater(tid):
            barrier.wait()
            for _ in range(50):
                for row in range(10):
                    buf.set_line(row, f"t{tid}-r{row}")
                d.redraw_buffer(buf)

        threads = [threading.Thread(target=updater, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def test_write_region(self):
        f, d = self._make_display(width=40, height=10)
        d.enter()
        f.truncate(0)
        f.seek(0)

        d.write_region(0, 0, ["hello", "world"], width=5)
        raw = f.getvalue()
        assert "hello" in raw
        assert "world" in raw

    def test_enable_disable_mouse(self):
        f, d = self._make_display()
        d.enter()
        f.truncate(0)
        f.seek(0)

        d.enable_mouse()
        raw = f.getvalue()
        assert "\033[?1000h" in raw
        assert "\033[?1006h" in raw

        f.truncate(0)
        f.seek(0)
        d.disable_mouse()
        raw = f.getvalue()
        assert "\033[?1000l" in raw
        assert "\033[?1006l" in raw

    def test_leave_disables_mouse(self):
        """Leaving alt screen disables mouse tracking if it was enabled."""
        f, d = self._make_display()
        d.enter()
        d.enable_mouse()
        f.truncate(0)
        f.seek(0)
        d.leave()
        raw = f.getvalue()
        assert "\033[?1000l" in raw

    def test_status_text_renders_on_last_row(self):
        """status_text is rendered on the last terminal row with reverse video."""
        f, d = self._make_display(width=30, height=5)
        buf = ScreenBuffer()
        buf.add_lines(2)
        buf.set_line(0, "content0")
        buf.set_line(1, "content1")
        d.enter()
        f.truncate(0)
        f.seek(0)

        d.redraw_buffer(buf, status_text="my status")
        raw = f.getvalue()
        plain = strip_ansi(raw)
        assert "content0" in plain
        assert "content1" in plain
        assert "my status" in plain
        # Reverse video escape should be present.
        assert "\033[7m" in raw

    def test_status_text_reserves_viewport_row(self):
        """With status_text, content viewport is reduced by 1 row."""
        f, d = self._make_display(width=20, height=4)
        buf = ScreenBuffer()
        buf.add_lines(10)
        for i in range(10):
            buf.set_line(i, f"line{i}")
        d.enter()
        f.truncate(0)
        f.seek(0)

        # Without status: 4-row viewport shows lines 6-9.
        # With status: 3-row viewport shows lines 7-9.
        d.redraw_buffer(buf, status_text="status")
        raw = f.getvalue()
        assert "line7" in raw
        assert "line8" in raw
        assert "line9" in raw
        assert "line6" not in raw
