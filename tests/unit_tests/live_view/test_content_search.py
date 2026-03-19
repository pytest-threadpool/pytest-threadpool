"""Unit tests for content pane search and highlight."""

from __future__ import annotations

from pytest_threadpool._live_view._display import _highlight_matches


class TestHighlightMatches:
    """_highlight_matches applies inline ANSI highlighting."""

    def test_no_query_returns_unchanged(self):
        assert _highlight_matches("hello world", "") == "hello world"

    def test_plain_text_match(self):
        result = _highlight_matches("hello world", "world")
        assert "world" in result
        assert "\033[48;5;238;37m" in result  # other-match style

    def test_current_match_uses_orange(self):
        result = _highlight_matches("hello world", "world", current=True)
        assert "\033[48;5;214;30m" in result  # current-match style

    def test_case_insensitive(self):
        result = _highlight_matches("Hello World", "hello")
        assert "\033[48;5;238;37m" in result

    def test_multiple_matches(self):
        result = _highlight_matches("aaa bbb aaa", "aaa")
        # Should have two highlight starts.
        assert result.count("\033[48;5;238;37m") == 2

    def test_no_match_returns_unchanged(self):
        line = "hello world"
        assert _highlight_matches(line, "zzz") == line

    def test_ansi_codes_preserved(self):
        line = "\033[32mpassed\033[0m some text"
        result = _highlight_matches(line, "some")
        # Original ANSI codes should still be present.
        assert "\033[32m" in result
        assert "\033[0m" in result
        # And the match should be highlighted.
        assert "\033[48;5;238;37m" in result

    def test_match_inside_ansi_text(self):
        line = "\033[31mfailed assertion\033[0m"
        result = _highlight_matches(line, "failed")
        assert "\033[48;5;238;37m" in result
