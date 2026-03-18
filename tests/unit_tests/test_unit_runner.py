"""Unit tests for _runner.py internal helpers."""

import logging
import threading
import types

from pytest_threadpool._runner import _is_teamcity, _tc_escape, _ThreadLocalLogHandler


class TestIsTeamcity:
    """Tests for _is_teamcity detection helper."""

    def test_false_by_default(self):
        config = types.SimpleNamespace(getoption=lambda key, default=0: default)
        assert _is_teamcity(config, env={}) is False

    def test_true_with_cli_flag(self):
        config = types.SimpleNamespace(getoption=lambda key, default=0: 1)
        assert _is_teamcity(config, env={}) is True

    def test_true_with_env_var(self):
        config = types.SimpleNamespace(getoption=lambda key, default=0: 0)
        assert _is_teamcity(config, env={"TEAMCITY_VERSION": "2024.1"}) is True

    def test_true_with_both(self):
        config = types.SimpleNamespace(getoption=lambda key, default=0: 1)
        assert _is_teamcity(config, env={"TEAMCITY_VERSION": "2024.1"}) is True

    def test_false_with_empty_env_var(self):
        config = types.SimpleNamespace(getoption=lambda key, default=0: 0)
        assert _is_teamcity(config, env={"TEAMCITY_VERSION": ""}) is False

    def test_cli_count_greater_than_one(self):
        config = types.SimpleNamespace(getoption=lambda key, default=0: 2)
        assert _is_teamcity(config, env={}) is True


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


class TestThreadLocalLogHandler:
    """Tests for _ThreadLocalLogHandler per-thread log capture."""

    def test_no_records_when_not_activated(self):
        handler = _ThreadLocalLogHandler(level=logging.DEBUG)
        record = logging.LogRecord("test", logging.WARNING, "", 0, "msg", (), None)
        handler.emit(record)
        records, text = handler.deactivate()
        assert records == []
        assert text == ""

    def test_captures_records_when_activated(self):
        handler = _ThreadLocalLogHandler(level=logging.DEBUG)
        handler.activate()
        record = logging.LogRecord("test", logging.WARNING, "", 0, "hello", (), None)
        handler.emit(record)
        records, _text = handler.deactivate()
        assert len(records) == 1
        assert records[0].getMessage() == "hello"

    def test_formatted_text_output(self):
        formatter = logging.Formatter("%(levelname)s %(message)s")
        handler = _ThreadLocalLogHandler(level=logging.DEBUG, formatter=formatter)
        handler.activate()
        record = logging.LogRecord("test", logging.WARNING, "", 0, "msg", (), None)
        handler.emit(record)
        _, text = handler.deactivate()
        assert "WARNING msg" in text

    def test_deactivate_clears_state(self):
        handler = _ThreadLocalLogHandler(level=logging.DEBUG)
        handler.activate()
        record = logging.LogRecord("test", logging.WARNING, "", 0, "msg", (), None)
        handler.emit(record)
        handler.deactivate()
        # Second deactivate returns empty
        records, text = handler.deactivate()
        assert records == []
        assert text == ""

    def test_level_filtering(self):
        handler = _ThreadLocalLogHandler(level=logging.WARNING)
        handler.activate()
        debug_rec = logging.LogRecord("test", logging.DEBUG, "", 0, "debug", (), None)
        warn_rec = logging.LogRecord("test", logging.WARNING, "", 0, "warn", (), None)
        # Handler.emit is only called if level check passes in logging machinery.
        # Test the handler's own level check.
        if handler.level <= debug_rec.levelno:
            handler.emit(debug_rec)
        if handler.level <= warn_rec.levelno:
            handler.emit(warn_rec)
        records, _ = handler.deactivate()
        assert len(records) == 1
        assert records[0].getMessage() == "warn"

    def test_per_thread_isolation(self):
        handler = _ThreadLocalLogHandler(level=logging.DEBUG)
        results = {}
        barrier = threading.Barrier(2, timeout=10)

        def worker(name):
            handler.activate()
            barrier.wait()
            record = logging.LogRecord("test", logging.WARNING, "", 0, name, (), None)
            handler.emit(record)
            barrier.wait()
            records, _ = handler.deactivate()
            results[name] = [r.getMessage() for r in records]

        threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert results["w0"] == ["w0"]
        assert results["w1"] == ["w1"]
