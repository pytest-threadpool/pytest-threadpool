"""Parallel tests using caplog fixture — verify native behavior."""

import logging

import pytest

from pytest_threadpool import parallelizable

pytestmark = parallelizable("children")

logger = logging.getLogger(__name__)


class TestCaplogRecords:
    """caplog.text and caplog.records work in parallel tests."""

    def test_caplog_text(self, caplog):
        with caplog.at_level(logging.INFO):
            logger.info("CAPLOG_TEXT_CHECK")
        assert "CAPLOG_TEXT_CHECK" in caplog.text

    def test_caplog_records(self, caplog):
        with caplog.at_level(logging.WARNING):
            logger.warning("CAPLOG_RECORDS_CHECK")
        assert len(caplog.records) == 1
        assert caplog.records[0].getMessage() == "CAPLOG_RECORDS_CHECK"

    def test_caplog_record_tuples(self, caplog):
        with caplog.at_level(logging.INFO):
            logger.info("TUPLE_A")
            logger.warning("TUPLE_B")
        assert len(caplog.record_tuples) == 2
        assert caplog.record_tuples[0][2] == "TUPLE_A"
        assert caplog.record_tuples[1][2] == "TUPLE_B"

    def test_caplog_messages(self, caplog):
        with caplog.at_level(logging.INFO):
            logger.info("MSG_ONLY")
        assert caplog.messages == ["MSG_ONLY"]


class TestCaplogIsolation:
    """Each parallel test gets its own caplog — no cross-test leaks."""

    def test_isolation_a(self, caplog):
        with caplog.at_level(logging.INFO):
            logger.info("ISO_A")
        assert caplog.messages == ["ISO_A"]

    def test_isolation_b(self, caplog):
        with caplog.at_level(logging.INFO):
            logger.info("ISO_B")
        assert caplog.messages == ["ISO_B"]

    def test_isolation_c(self, caplog):
        with caplog.at_level(logging.INFO):
            logger.info("ISO_C")
        assert caplog.messages == ["ISO_C"]


class TestCaplogMethods:
    """caplog methods work correctly in parallel tests."""

    def test_at_level(self, caplog):
        with caplog.at_level(logging.DEBUG):
            logger.debug("AT_LEVEL_DEBUG")
        assert "AT_LEVEL_DEBUG" in caplog.text

    def test_set_level(self, caplog):
        caplog.set_level(logging.INFO)
        logger.info("SET_LEVEL_INFO")
        assert "SET_LEVEL_INFO" in caplog.text

    def test_clear(self, caplog):
        with caplog.at_level(logging.WARNING):
            logger.warning("BEFORE_CLEAR")
            caplog.clear()
            logger.warning("AFTER_CLEAR")
        assert "BEFORE_CLEAR" not in caplog.text
        assert "AFTER_CLEAR" in caplog.text
        assert len(caplog.records) == 1


class TestCaplogWithFailure:
    """Failed tests show caplog content in report sections."""

    def test_pass_with_caplog(self, caplog):
        with caplog.at_level(logging.INFO):
            logger.info("CAPLOG_PASS")
        assert "CAPLOG_PASS" in caplog.text

    def test_fail_with_caplog(self, caplog):
        with caplog.at_level(logging.WARNING):
            logger.warning("CAPLOG_FAIL_RECORD")
        assert "CAPLOG_FAIL_RECORD" in caplog.text
        pytest.fail("intentional failure")
