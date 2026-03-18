"""Parallel tests with StreamHandler on logger — verify output grouping."""

import logging
import sys

import pytest

from pytest_threadpool import parallelizable

pytestmark = parallelizable("children")

logger = logging.getLogger("myapp.tests")

# Module-level StreamHandler: tests that handler.stream is patched
# even when created before the proxy is installed.
_module_handler = logging.StreamHandler(sys.stderr)
_module_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
logger.addHandler(_module_handler)
logger.setLevel(logging.DEBUG)


class TestModuleLevelStderrHandler:
    """Module-level StreamHandler(stderr) — output grouped per-test."""

    @pytest.mark.parametrize("n", range(3))
    def test_modhandler(self, n):
        logger.info("MODSTDERR_INFO_%d", n)
        logger.warning("MODSTDERR_WARN_%d", n)

    def test_modhandler_fail(self):
        logger.warning("MODSTDERR_FAIL")
        pytest.fail("intentional failure")


class TestFixtureStdoutHandler:
    """Fixture-scoped StreamHandler(stdout) — output grouped per-test."""

    @pytest.fixture(autouse=True)
    def _setup_handler(self):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        yield
        logger.removeHandler(handler)

    @pytest.mark.parametrize("n", range(3))
    def test_stdout_handler(self, n):
        logger.info("FIXSTDOUT_INFO_%d", n)
        logger.warning("FIXSTDOUT_WARN_%d", n)


class TestNoStreamHandler:
    """No StreamHandler — only _ThreadLocalLogHandler captures records."""

    @pytest.mark.parametrize("n", range(3))
    def test_no_handler(self, n):
        logger.warning("NOHANDLER_WARN_%d", n)
