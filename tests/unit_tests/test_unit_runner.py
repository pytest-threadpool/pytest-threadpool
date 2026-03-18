"""Unit tests for _runner.py internal helpers."""

import types

from pytest_threadpool._runner import _is_teamcity, _tc_escape


class TestIsTeamcity:
    """Tests for _is_teamcity detection helper."""

    def test_false_by_default(self, monkeypatch):
        config = types.SimpleNamespace(getoption=lambda key, default=0: default)
        monkeypatch.delenv("TEAMCITY_VERSION", raising=False)
        assert _is_teamcity(config) is False

    def test_true_with_cli_flag(self, monkeypatch):
        config = types.SimpleNamespace(getoption=lambda key, default=0: 1)
        monkeypatch.delenv("TEAMCITY_VERSION", raising=False)
        assert _is_teamcity(config) is True

    def test_true_with_env_var(self, monkeypatch):
        config = types.SimpleNamespace(getoption=lambda key, default=0: 0)
        monkeypatch.setenv("TEAMCITY_VERSION", "2024.1")
        assert _is_teamcity(config) is True

    def test_true_with_both(self, monkeypatch):
        config = types.SimpleNamespace(getoption=lambda key, default=0: 1)
        monkeypatch.setenv("TEAMCITY_VERSION", "2024.1")
        assert _is_teamcity(config) is True

    def test_false_with_empty_env_var(self, monkeypatch):
        config = types.SimpleNamespace(getoption=lambda key, default=0: 0)
        monkeypatch.setenv("TEAMCITY_VERSION", "")
        assert _is_teamcity(config) is False

    def test_cli_count_greater_than_one(self, monkeypatch):
        config = types.SimpleNamespace(getoption=lambda key, default=0: 2)
        monkeypatch.delenv("TEAMCITY_VERSION", raising=False)
        assert _is_teamcity(config) is True


class TestTcEscape:
    """Tests for _tc_escape TeamCity message value escaping."""

    def test_plain_text_unchanged(self):
        assert _tc_escape("hello world") == "hello world"

    def test_pipe_escaped(self):
        assert _tc_escape("a|b") == "a||b"

    def test_single_quote_escaped(self):
        assert _tc_escape("it's") == "it|'s"

    def test_newline_escaped(self):
        assert _tc_escape("line1\nline2") == "line1|nline2"

    def test_carriage_return_escaped(self):
        assert _tc_escape("a\rb") == "a|rb"

    def test_brackets_escaped(self):
        assert _tc_escape("[tag]") == "|[tag|]"

    def test_combined_escaping(self):
        assert _tc_escape("a|b\n'[x]") == "a||b|n|'|[x|]"

    def test_empty_string(self):
        assert _tc_escape("") == ""
