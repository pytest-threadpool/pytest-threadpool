"""Tests for fixture correctness under parallel execution."""

import pytest


class TestFixturesUnderParallel:
    """Verify fixture setup/teardown behaves correctly with parallel children."""

    def test_class_scoped_fixture_setup_once(self, ftdir):
        """Class-scoped fixture runs exactly once despite parallel methods."""
        ftdir.copy_case("fixture_class_scoped_once")
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=3)

    def test_class_scoped_yield_fixture(self, ftdir):
        """Class-scoped yield fixture: setup before parallel, teardown after."""
        ftdir.copy_case("fixture_class_yield")
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=3)

    def test_function_scoped_fixture(self, ftdir):
        """Function-scoped fixtures get fresh values per test."""
        ftdir.copy_case("fixture_function_scoped")
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=4)

    def test_parameterized_fixture(self, ftdir):
        """Parameterized class-scoped fixture expands correctly."""
        ftdir.copy_case("fixture_parameterized")
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=4)

    def test_multiple_fixture_scopes(self, ftdir):
        """Session + module + class fixtures compose correctly."""
        ftdir.copy_case("fixture_multiple_scopes")
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=3)

    def test_yield_fixture_cleanup(self, ftdir):
        """Yield fixture teardown runs after all parallel methods."""
        ftdir.copy_case("fixture_yield_cleanup")
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=3)

    def test_fixture_teardown_exception_runs_all_finalizers(self, ftdir):
        """A failing finalizer must not prevent remaining finalizers from running."""
        ftdir.copy_case("fixture_teardown_exception")
        result = ftdir.run_pytest("--freethreaded", "2")
        # 3 passed (including verify), 1 teardown error from resource_a
        assert "3 passed" in result.stdout
        assert "1 error" in result.stdout
        # The verify test proves all finalizers ran despite the exception
        assert "FAILED" not in result.stdout
