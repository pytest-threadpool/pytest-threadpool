"""Tests for parallel function-scoped fixture setup and teardown.

Function-scoped FixtureDefs are cloned per-item so each worker creates
independent fixture instances.  These tests verify correctness across
yield fixtures, addfinalizer, chained dependencies, shared-scope
dependencies, xunit hooks, built-in fixtures, and actual parallel timing.
"""


class TestFuncScopedFixtureParallel:
    """Verify function-scoped fixtures work correctly when set up in parallel workers."""

    def test_yield_fixture_setup_and_teardown(self, ftdir):
        """Yield fixtures: setup and teardown both run exactly once per test."""
        ftdir.copy_case("fixture_func_yield_teardown")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_shared_scope_dependencies(self, ftdir):
        """Function fixture depending on session + module + class fixtures."""
        ftdir.copy_case("fixture_func_with_shared_deps")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_multiple_fixtures_per_test(self, ftdir):
        """Multiple function-scoped fixtures per test all get independent values."""
        ftdir.copy_case("fixture_func_multiple_per_test")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_chained_function_fixtures(self, ftdir):
        """Function fixture depending on another function fixture (LIFO teardown)."""
        ftdir.copy_case("fixture_func_chain")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_addfinalizer_style(self, ftdir):
        """request.addfinalizer works correctly for parallel function fixtures."""
        ftdir.copy_case("fixture_func_addfinalizer")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_combined_with_xunit_setup_method(self, ftdir):
        """Function fixtures combined with xunit setup_method/teardown_method."""
        ftdir.copy_case("fixture_func_with_xunit")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_tmp_path_unique_per_test(self, ftdir):
        """Built-in tmp_path fixture provides unique directories in parallel."""
        ftdir.copy_case("fixture_func_with_tmp_path")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_fixture_setup_runs_in_parallel(self, ftdir):
        """Slow function fixture setup runs concurrently, not sequentially."""
        ftdir.copy_case("fixture_func_setup_parallel")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)


class TestXunitTeardownParallel:
    """Verify xunit teardown hooks run for every parallel test."""

    def test_method_teardown_runs_for_all(self, ftdir):
        """setup_method and teardown_method both run for every parallel test."""
        ftdir.copy_case("xunit_method_teardown_runs")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)
