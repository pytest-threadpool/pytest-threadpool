"""Tests for error and edge-case scenarios during parallel execution."""


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
