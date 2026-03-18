"""Unit tests for ScrollColumn."""

from pytest_threadpool._live_view import ScrollColumn


class TestScrollColumn:
    """ScrollColumn renders a 1-char-wide scroll indicator."""

    def test_no_bar_when_content_fits(self):
        sc = ScrollColumn()
        result = sc.render(viewport_height=10, content_height=5, scroll_offset=0)
        assert len(result) == 10
        assert all(c == "" for c in result)

    def test_no_bar_when_exact_fit(self):
        sc = ScrollColumn()
        result = sc.render(viewport_height=10, content_height=10, scroll_offset=0)
        assert all(c == "" for c in result)

    def test_thumb_at_top(self):
        sc = ScrollColumn()
        result = sc.render(viewport_height=10, content_height=100, scroll_offset=0)
        assert len(result) == 10
        assert result[0] == ScrollColumn.THUMB
        assert result[-1] == ScrollColumn.TRACK

    def test_thumb_at_bottom(self):
        sc = ScrollColumn()
        result = sc.render(viewport_height=10, content_height=100, scroll_offset=90)
        assert len(result) == 10
        assert result[-1] == ScrollColumn.THUMB
        assert result[0] == ScrollColumn.TRACK

    def test_thumb_in_middle(self):
        sc = ScrollColumn()
        result = sc.render(viewport_height=10, content_height=100, scroll_offset=45)
        assert len(result) == 10
        thumb_positions = [i for i, c in enumerate(result) if c == ScrollColumn.THUMB]
        assert len(thumb_positions) >= 1
        assert thumb_positions[0] > 0
        assert thumb_positions[-1] < 9

    def test_all_chars_are_thumb_or_track(self):
        sc = ScrollColumn()
        result = sc.render(viewport_height=10, content_height=50, scroll_offset=10)
        for c in result:
            assert c in (ScrollColumn.THUMB, ScrollColumn.TRACK)

    def test_thumb_size_proportional(self):
        sc = ScrollColumn()
        r1 = sc.render(viewport_height=10, content_height=12, scroll_offset=0)
        r2 = sc.render(viewport_height=10, content_height=1000, scroll_offset=0)
        thumb1 = sum(1 for c in r1 if c == ScrollColumn.THUMB)
        thumb2 = sum(1 for c in r2 if c == ScrollColumn.THUMB)
        assert thumb1 > thumb2
