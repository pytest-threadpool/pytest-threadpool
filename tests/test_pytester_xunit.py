"""Tests for xunit-style setup/teardown under parallel execution."""

import pytest


@pytest.mark.parallelizable("children")
class TestXunitUnderParallel:
    """Verify xunit setup/teardown hooks work correctly with parallel children."""

    def test_class_setup_teardown(self, ftdir):
        """setup_class runs once before parallel methods."""
        ftdir.copy_case("xunit_class_setup")
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=3)

    def test_method_setup_teardown(self, ftdir):
        """setup_method runs per method even with parallel children."""
        ftdir.copy_case("xunit_method_setup")
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=4)

    def test_combined_class_and_method(self, ftdir):
        """Both setup_class and setup_method work together."""
        ftdir.copy_case("xunit_combined_setup")
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=3)

    def test_module_setup_teardown(self, ftdir):
        """Module-level setup_module / teardown_module work."""
        ftdir.copy_case("xunit_module_setup")
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=1)

    def test_function_setup_teardown(self, ftdir):
        """Function-level setup_function / teardown_function work."""
        ftdir.copy_case("xunit_function_setup")
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=3)
