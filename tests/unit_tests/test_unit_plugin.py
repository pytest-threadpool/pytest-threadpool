"""Unit tests for plugin.py internal helpers."""

import types
from unittest.mock import patch

from pytest_freethreaded.plugin import _is_free_threaded, _thread_count


class TestThreadCount:
    """Tests for _thread_count helper."""

    def test_none_when_option_is_none(self):
        config = types.SimpleNamespace(getoption=lambda key: None)
        assert _thread_count(config) is None

    def test_auto_returns_cpu_count(self):
        config = types.SimpleNamespace(getoption=lambda key: "auto")
        result = _thread_count(config)
        assert isinstance(result, int)
        assert result >= 1

    def test_auto_fallback_when_cpu_count_is_none(self):
        config = types.SimpleNamespace(getoption=lambda key: "auto")
        with patch("os.cpu_count", return_value=None):
            assert _thread_count(config) == 4

    def test_numeric_string_returns_int(self):
        config = types.SimpleNamespace(getoption=lambda key: "8")
        assert _thread_count(config) == 8

    def test_single_thread(self):
        config = types.SimpleNamespace(getoption=lambda key: "1")
        assert _thread_count(config) == 1


class TestIsFreeThreaded:
    """Tests for _is_free_threaded helper."""

    def test_returns_bool(self):
        result = _is_free_threaded()
        assert isinstance(result, bool)

    def test_true_when_gil_disabled(self):
        with patch(
            "sysconfig.get_config_vars",
            return_value={"Py_GIL_DISABLED": 1},
        ):
            assert _is_free_threaded() is True

    def test_false_when_gil_enabled(self):
        with patch(
            "sysconfig.get_config_vars",
            return_value={"Py_GIL_DISABLED": 0},
        ):
            assert _is_free_threaded() is False

    def test_false_when_key_missing(self):
        with patch(
            "sysconfig.get_config_vars",
            return_value={},
        ):
            assert _is_free_threaded() is False
