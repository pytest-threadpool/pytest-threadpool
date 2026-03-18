"""Tests for standard logging support during parallel execution.

Verifies that ``logging.Logger`` calls (info, warning, error, etc.) are
captured per-test and reported in "Captured log call" sections on failure,
matching sequential pytest behavior.

Log records should NOT appear in stdout for passing tests unless
``--log-cli-level`` is set.

Also verifies that ``logging.StreamHandler`` output (stderr/stdout) is
properly captured per-test and does not leak into global output.
"""

import re

# ---------------------------------------------------------------------------
# Log suppression for passing tests
# ---------------------------------------------------------------------------


class TestLogNotInStdoutForPassing:
    """Log records from passing tests do not appear in stdout."""

    def test_no_log_in_stdout_default_capture(self, ftdir):
        """In default capture mode, log output does not leak into stdout."""
        ftdir.copy_case("logging_basic_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "--log-level=INFO", "-v")
        result.assert_outcomes(passed=9, failed=1)

        assert "PASS_LOG" not in result.stdout, (
            f"PASS_LOG leaked into default-capture stdout\nstdout:\n{result.stdout}"
        )

    def test_no_log_in_stdout_passive_mode(self, ftdir):
        """With -vs, log output from passing tests does not appear in stdout."""
        ftdir.copy_case("logging_basic_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "--log-level=INFO", "-vs")
        result.assert_outcomes(passed=9, failed=1)

        assert "PASS_LOG" not in result.stdout, (
            f"PASS_LOG leaked into passive-mode stdout\nstdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# Log sections on failure
# ---------------------------------------------------------------------------


class TestLogOnFailure:
    """Log records appear in 'Captured log call' sections on failure."""

    def test_fail_log_in_captured_section(self, ftdir):
        """Failed test's log records appear in the failure report."""
        ftdir.copy_case("logging_basic_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "--log-level=INFO", "-v")
        result.assert_outcomes(passed=9, failed=1)

        assert "FAIL_LOG" in result.stdout, (
            f"FAIL_LOG should appear in failure report\nstdout:\n{result.stdout}"
        )
        assert "Captured log call" in result.stdout, (
            f"'Captured log call' section missing\nstdout:\n{result.stdout}"
        )

    def test_fail_log_in_passive_mode(self, ftdir):
        """Failed test's log records appear in -vs mode failure report."""
        ftdir.copy_case("logging_basic_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "--log-level=WARNING", "-vs")
        result.assert_outcomes(passed=9, failed=1)

        assert "FAIL_LOG" in result.stdout, (
            f"FAIL_LOG should appear in failure report\nstdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# Log level filtering
# ---------------------------------------------------------------------------


class TestLogLevelFiltering:
    """--log-level controls which records are captured."""

    def test_warning_level_excludes_debug(self, ftdir):
        """At WARNING level, DEBUG and INFO records are filtered out."""
        ftdir.copy_case("logging_basic_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "--log-level=WARNING", "-v")
        result.assert_outcomes(passed=9, failed=1)

        assert "LOG_DEBUG_MSG" not in result.stdout, (
            f"DEBUG should be filtered at WARNING level\nstdout:\n{result.stdout}"
        )
        assert "LOG_INFO_MSG" not in result.stdout, (
            f"INFO should be filtered at WARNING level\nstdout:\n{result.stdout}"
        )

    def test_info_level_includes_warning(self, ftdir):
        """At INFO level, WARNING records are captured."""
        ftdir.copy_case("logging_basic_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "--log-level=INFO", "-v")
        result.assert_outcomes(passed=9, failed=1)

        assert "FAIL_LOG" in result.stdout, (
            f"WARNING record should be captured at INFO level\nstdout:\n{result.stdout}"
        )

    def test_debug_level_captures_all(self, ftdir):
        """At DEBUG level, all records including DEBUG are captured."""
        ftdir.copy_case("logging_basic_parallel")
        result = ftdir.run_pytest("--threadpool", "4", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=9, failed=1)

        assert "FAIL_LOG" in result.stdout, (
            f"WARNING record should be captured at DEBUG level\nstdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# StreamHandler grouping — module-level stderr handler
# ---------------------------------------------------------------------------


class TestStreamHandlerGrouping:
    """StreamHandler output is captured per-test, not leaked globally."""

    def test_no_stderr_leak_with_module_handler(self, ftdir):
        """Module-level StreamHandler(stderr) output does not leak to stderr."""
        ftdir.copy_case("logging_streamhandler")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=9, failed=1)

        # StreamHandler output must NOT appear in subprocess stderr
        assert "MODSTDERR_INFO" not in result.stderr, (
            f"StreamHandler output leaked to global stderr\nstderr:\n{result.stderr}"
        )

    def test_no_stdout_leak_with_module_handler(self, ftdir):
        """Module-level StreamHandler(stderr) output does not leak into stdout."""
        ftdir.copy_case("logging_streamhandler")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=9, failed=1)

        # StreamHandler output from passing tests must not appear outside failure report
        for n in range(3):
            assert f"MODSTDERR_INFO_{n}" not in result.stdout.split("FAILURES")[0], (
                f"MODSTDERR_INFO_{n} leaked into stdout before FAILURES\nstdout:\n{result.stdout}"
            )

    def test_fail_shows_stderr_section(self, ftdir):
        """Failed test with module-level handler shows 'Captured stderr call'."""
        ftdir.copy_case("logging_streamhandler")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=9, failed=1)

        assert "Captured stderr call" in result.stdout, (
            f"'Captured stderr call' section missing for failed test\nstdout:\n{result.stdout}"
        )
        assert "MODSTDERR_FAIL" in result.stdout, (
            f"MODSTDERR_FAIL should appear in failure report\nstdout:\n{result.stdout}"
        )

    def test_fail_shows_log_section(self, ftdir):
        """Failed test shows 'Captured log call' section alongside stderr."""
        ftdir.copy_case("logging_streamhandler")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=9, failed=1)

        assert "Captured log call" in result.stdout, (
            f"'Captured log call' section missing\nstdout:\n{result.stdout}"
        )

    def test_stderr_grouped_per_test(self, ftdir):
        """Each test's stderr section contains only its own handler output."""
        ftdir.copy_case("logging_streamhandler")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=9, failed=1)

        # The failure report's "Captured stderr call" should only have
        # MODSTDERR_FAIL, not MODSTDERR_INFO_0/1/2 from passing tests.
        failure_section = result.stdout.split("FAILURES")[-1]
        stderr_match = re.search(
            r"Captured stderr call -+\n(.*?)(?=\n----|====|\Z)",
            failure_section,
            re.DOTALL,
        )
        assert stderr_match, f"No Captured stderr call section found\nstdout:\n{result.stdout}"
        stderr_content = stderr_match.group(1)
        assert "MODSTDERR_FAIL" in stderr_content, (
            f"MODSTDERR_FAIL missing from stderr section\n{stderr_content}"
        )
        for n in range(3):
            assert f"MODSTDERR_INFO_{n}" not in stderr_content, (
                f"MODSTDERR_INFO_{n} leaked into failure's stderr section\n{stderr_content}"
            )


# ---------------------------------------------------------------------------
# StreamHandler grouping — fixture-scoped stdout handler
# ---------------------------------------------------------------------------


class TestFixtureStdoutHandler:
    """Fixture-scoped StreamHandler(stdout) output captured per-test."""

    def test_no_stdout_leak(self, ftdir):
        """Fixture StreamHandler(stdout) output does not leak into stdout."""
        ftdir.copy_case("logging_streamhandler")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=9, failed=1)

        # FIXSTDOUT_* comes from passing tests — should not appear in stdout
        for n in range(3):
            assert f"FIXSTDOUT_INFO_{n}" not in result.stdout.split("FAILURES")[0], (
                f"FIXSTDOUT_INFO_{n} leaked into stdout\nstdout:\n{result.stdout}"
            )

    def test_no_stderr_leak(self, ftdir):
        """Fixture StreamHandler(stdout) output does not leak to stderr."""
        ftdir.copy_case("logging_streamhandler")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=9, failed=1)

        assert "FIXSTDOUT_INFO" not in result.stderr, (
            f"Fixture stdout handler leaked to stderr\nstderr:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# No handler — pure _ThreadLocalLogHandler capture
# ---------------------------------------------------------------------------


class TestNoStreamHandlerCapture:
    """Without any StreamHandler, log records are still captured per-test."""

    def test_no_handler_no_leak(self, ftdir):
        """Logger with no StreamHandler does not leak output."""
        ftdir.copy_case("logging_streamhandler")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=9, failed=1)

        # NOHANDLER_WARN should not appear in stdout or stderr for passing tests
        for n in range(3):
            assert f"NOHANDLER_WARN_{n}" not in result.stderr, (
                f"NOHANDLER_WARN_{n} leaked to stderr\nstderr:\n{result.stderr}"
            )
