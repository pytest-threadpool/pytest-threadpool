"""Tests for error and edge-case scenarios during parallel execution."""
import shutil

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
