"""Tests for parallel scope types and marker priority."""


class TestParallelScopes:
    """Verify parameters, all, children scopes and override priority."""

    def test_parameters_scope(self, ftdir):
        """Parametrized variants run concurrently with 'parameters' scope."""
        ftdir.copy_case("scope_parameters")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=3)

    def test_all_scope_merges_children_and_params(self, ftdir):
        """'all' merges plain methods and parametrized variants into one batch."""
        ftdir.copy_case("scope_all_merged")
        result = ftdir.run_pytest("--threadpool", "5")
        result.assert_outcomes(passed=5)

    def test_children_does_not_merge_params(self, ftdir):
        """'children' keeps parametrized variants in separate groups."""
        ftdir.copy_case("scope_children_separate_params")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=3)

    def test_own_marker_overrides_class(self, ftdir):
        """Method's own 'parameters' overrides class 'children'."""
        ftdir.copy_case("scope_method_overrides_class")
        result = ftdir.run_pytest("--threadpool", "5")
        result.assert_outcomes(passed=6)

    def test_not_parallelizable_overrides_class(self, ftdir):
        """@not_parallelizable on a method opts it out of class children batch."""
        ftdir.copy_case("scope_not_parallelizable_method")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=4)

    def test_not_parallelizable_bare_function(self, ftdir):
        """@not_parallelizable on bare functions in a parallel module."""
        ftdir.copy_case("scope_not_parallelizable_function")
        result = ftdir.run_pytest("--threadpool", "auto", "-s")
        result.assert_outcomes(passed=2)
        order = [line.split("ORDER:")[1] for line in result.outlines if "ORDER:" in line]
        assert order == ["a", "b"]

    def test_module_level_children(self, ftdir):
        """Module-level pytestmark parallelizable('children') works."""
        ftdir.copy_case("scope_module_children")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=3)

    def test_dynamic_parametrize(self, ftdir):
        """pytest_generate_tests parametrize runs concurrently with 'parameters' scope."""
        ftdir.copy_case("scope_dynamic_parametrize")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=3)

    def test_all_not_parallelizable_runs_sequential(self, ftdir):
        """All items with @not_parallelizable run on MainThread, no thread pool."""
        ftdir.copy_case("scope_all_not_parallelizable")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)
