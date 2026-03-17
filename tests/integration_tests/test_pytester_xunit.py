"""Tests for xunit-style setup/teardown under parallel execution."""


class TestXunitUnderParallel:
    """Verify xunit setup/teardown hooks work correctly with parallel children."""

    def test_class_setup_teardown(self, ftdir):
        """setup_class runs once before parallel methods."""
        ftdir.copy_case("xunit_class_setup")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=3)

    def test_method_setup_teardown(self, ftdir):
        """setup_method runs per method even with parallel children."""
        ftdir.copy_case("xunit_method_setup")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=4)

    def test_combined_class_and_method(self, ftdir):
        """Both setup_class and setup_method work together."""
        ftdir.copy_case("xunit_combined_setup")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=3)

    def test_module_setup_teardown(self, ftdir):
        """Module-level setup_module / teardown_module work."""
        ftdir.copy_case("xunit_module_setup")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=1)

    def test_function_setup_teardown(self, ftdir):
        """Function-level setup_function / teardown_function work."""
        ftdir.copy_case("xunit_function_setup")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=3)

    def test_method_setup_mixed_parallel(self, ftdir):
        """setup_method/teardown_method run for both parallel and not_parallelizable methods."""
        ftdir.copy_case("xunit_method_mixed_parallel")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_function_setup_mixed_parallel(self, ftdir):
        """setup_function/teardown_function run for both parallel and sequential functions."""
        ftdir.copy_case("xunit_function_mixed_parallel")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_setup_class_across_groups(self, ftdir):
        """setup_class/teardown_class: once per class across parallel groups."""
        ftdir.copy_case("xunit_setup_class_across_groups")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=5)

    def test_setup_module_across_groups(self, ftdir):
        """setup_module runs once, survives across parallel groups and sequential tests."""
        ftdir.copy_case("xunit_setup_module_across_groups")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=5)

    def test_setup_method_across_groups(self, ftdir):
        """setup_method/teardown_method fire for every method across parallel classes."""
        ftdir.copy_case("xunit_setup_method_across_groups")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=5)
