"""Tests for error and edge-case scenarios during parallel execution."""
import os
import signal
import subprocess
import sys
import shutil
import time

from tests.conftest import CASES_DIR


class TestFreethreadedValidation:
    """Verify the plugin rejects --freethreaded on GIL-enabled Python."""

    def test_rejects_gil_enabled_python(self, ftdir):
        """--freethreaded must error when running on a GIL-enabled build."""
        ftdir.copy_case("validate_freethreaded")
        # Copy the conftest that fakes sys._is_gil_enabled = True
        shutil.copy2(
            CASES_DIR / "validate_freethreaded_conftest.py",
            ftdir.path / "conftest.py",
        )
        result = ftdir.run_pytest("--freethreaded", "2")
        assert result.returncode != 0
        assert "free-threaded Python build" in result.stderr or "free-threaded Python build" in result.stdout


class TestSetupFailures:
    """Verify correct handling when test setup fails in parallel groups."""

    def test_all_tests_fail_setup(self, ftdir):
        """All tests in a parallel group fail during setup — no crash, all reported."""
        ftdir.copy_case("setup_all_fail")
        result = ftdir.run_pytest("--freethreaded", "3")
        assert "3 error" in result.stdout
        assert "passed" not in result.stdout.split("=")[-1]

    def test_mixed_setup_pass_fail(self, ftdir):
        """Some tests pass setup, some fail — passing tests run, failures reported."""
        ftdir.copy_case("setup_mixed_pass_fail")
        result = ftdir.run_pytest("--freethreaded", "3")
        assert "2 passed" in result.stdout
        assert "1 error" in result.stdout


class TestExceptionHandling:
    """Verify BaseException subclasses are handled during parallel execution."""

    def test_system_exit_in_test_body(self, ftdir):
        """SystemExit in a parallel test body is caught and reported as failure."""
        ftdir.copy_case("edge_system_exit")
        result = ftdir.run_pytest("--freethreaded", "3")
        assert "1 failed" in result.stdout
        assert "2 passed" in result.stdout

    def test_keyboard_interrupt_in_test_body(self, ftdir):
        """KeyboardInterrupt in a parallel test body is caught and reported as failure."""
        ftdir.copy_case("edge_keyboard_interrupt")
        result = ftdir.run_pytest("--freethreaded", "3")
        assert "1 failed" in result.stdout
        assert "2 passed" in result.stdout


class TestConcurrencyEdgeCases:
    """Verify edge cases around thread interaction."""

    def test_nested_threads(self, ftdir):
        """Tests that spawn their own threads work correctly in parallel."""
        ftdir.copy_case("edge_nested_threads")
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=4)

    def test_sigint_exits_promptly(self, ftdir):
        """SIGINT during parallel execution cancels futures and exits promptly."""
        ftdir.copy_case("edge_sigint")
        proc = subprocess.Popen(
            [sys.executable, "-m", "pytest", str(ftdir.path),
             "--freethreaded", "3"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(ftdir.path),
        )
        # Wait briefly for tests to start running, then send SIGINT
        time.sleep(1)
        proc.send_signal(signal.SIGINT)
        # Must exit within a few seconds, not 30s
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise AssertionError(
                "Process did not exit within 10s after SIGINT — "
                "futures were not cancelled promptly"
            )
        assert proc.returncode != 0
        assert "KeyboardInterrupt" in stdout or "KeyboardInterrupt" in stderr
