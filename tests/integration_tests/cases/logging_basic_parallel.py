"""Parallel tests using standard logging — verify records are not lost."""

import logging

import pytest

from pytest_threadpool import parallelizable

logger = logging.getLogger(__name__)


@parallelizable("children")
class TestLoggingParallel:
    @pytest.mark.parametrize("n", range(4))
    def test_log_message(self, n):
        logger.warning("LOG_WARN_%d", n)
        logger.info("LOG_INFO_%d", n)
        print(f"PRINT_OUTPUT_{n}")


@parallelizable("children")
class TestLoggingLevels:
    def test_debug(self):
        logger.debug("LOG_DEBUG_MSG")

    def test_info(self):
        logger.info("LOG_INFO_MSG")

    def test_warning(self):
        logger.warning("LOG_WARNING_MSG")

    def test_error(self):
        logger.error("LOG_ERROR_MSG")


@parallelizable("children")
class TestLoggingWithFailure:
    def test_pass_with_log(self):
        logger.warning("PASS_LOG")

    def test_fail_with_log(self):
        logger.warning("FAIL_LOG")
        pytest.fail("intentional failure")
