"""Tests for caplog fixture behavior during parallel execution.

Verifies that ``caplog`` works natively in parallel tests — records,
text, record_tuples, messages, clear, set_level, and at_level all
behave the same as in sequential pytest.  Each worker gets its own
``LogCaptureHandler`` with a thread filter so parallel tests don't
leak records into each other's caplog.
"""


class TestCaplogRecordsWork:
    """caplog.text, records, record_tuples, and messages work in parallel."""

    def test_all_pass(self, ftdir):
        """All caplog assertions pass in parallel tests."""
        ftdir.copy_case("caplog_parallel")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=11, failed=1)

    def test_caplog_text_works(self, ftdir):
        """caplog.text contains the logged message."""
        ftdir.copy_case("caplog_parallel")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=11, failed=1)

        # The test_caplog_text test asserts "CAPLOG_TEXT_CHECK" in caplog.text
        # — if it passed, caplog.text works.

    def test_caplog_records_works(self, ftdir):
        """caplog.records contains the logged record."""
        ftdir.copy_case("caplog_parallel")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=11, failed=1)


class TestCaplogIsolation:
    """Each parallel test gets its own caplog with no cross-test leaks."""

    def test_isolation_all_pass(self, ftdir):
        """Three parallel tests each see only their own log message."""
        ftdir.copy_case("caplog_parallel")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=11, failed=1)

        # All isolation tests (ISO_A, ISO_B, ISO_C) assert
        # caplog.messages == ["ISO_X"] — if any leaked, it would fail.


class TestCaplogMethods:
    """caplog methods (at_level, set_level, clear) work in parallel."""

    def test_methods_all_pass(self, ftdir):
        """at_level, set_level, and clear all work in parallel."""
        ftdir.copy_case("caplog_parallel")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=11, failed=1)


class TestCaplogOnFailure:
    """Failed tests show log content in report sections."""

    def test_captured_log_section_present(self, ftdir):
        """Failed test gets 'Captured log call' section."""
        ftdir.copy_case("caplog_parallel")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=11, failed=1)

        assert "Captured log call" in result.stdout, (
            f"'Captured log call' section missing\nstdout:\n{result.stdout}"
        )

    def test_fail_record_in_section(self, ftdir):
        """Failed test's log record appears in the report."""
        ftdir.copy_case("caplog_parallel")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=11, failed=1)

        assert "CAPLOG_FAIL_RECORD" in result.stdout, (
            f"CAPLOG_FAIL_RECORD should appear in failure report\nstdout:\n{result.stdout}"
        )

    def test_pass_record_not_in_stdout(self, ftdir):
        """Passing test's log record does not appear in stdout."""
        ftdir.copy_case("caplog_parallel")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=11, failed=1)

        assert "CAPLOG_PASS" not in result.stdout, (
            f"CAPLOG_PASS from passing test leaked into stdout\nstdout:\n{result.stdout}"
        )

    def test_no_stderr_leak(self, ftdir):
        """No log records leak to stderr."""
        ftdir.copy_case("caplog_parallel")
        result = ftdir.run_pytest("--threadpool", "3", "--log-level=DEBUG", "-v")
        result.assert_outcomes(passed=11, failed=1)

        assert "CAPLOG_FAIL_RECORD" not in result.stderr, (
            f"Log record leaked to stderr\nstderr:\n{result.stderr}"
        )
