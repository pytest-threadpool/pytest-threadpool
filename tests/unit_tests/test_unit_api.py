"""Unit tests for the public marker API."""

import pytest

from pytest_freethreaded._api import not_parallelizable, parallelizable


class TestParallelizable:
    """Tests for the parallelizable() helper."""

    def test_returns_mark_decorator(self):
        result = parallelizable("children")
        assert isinstance(result, pytest.MarkDecorator)

    def test_mark_name(self):
        result = parallelizable("all")
        assert result.mark.name == "parallelizable"

    def test_scope_passed_as_arg(self):
        for scope in ("children", "parameters", "all"):
            result = parallelizable(scope)
            assert result.mark.args == (scope,)


class TestNotParallelizable:
    """Tests for the not_parallelizable marker."""

    def test_is_mark_decorator(self):
        assert isinstance(not_parallelizable, pytest.MarkDecorator)

    def test_mark_name(self):
        assert not_parallelizable.mark.name == "not_parallelizable"
