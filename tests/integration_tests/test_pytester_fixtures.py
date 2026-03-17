"""Tests for fixture correctness under parallel execution."""


class TestFixturesUnderParallel:
    """Verify fixture setup/teardown behaves correctly with parallel children."""

    def test_class_scoped_fixture_setup_once(self, ftdir):
        """Class-scoped fixture runs exactly once despite parallel methods."""
        ftdir.copy_case("fixture_class_scoped_once")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=3)

    def test_class_scoped_yield_fixture(self, ftdir):
        """Class-scoped yield fixture: setup before parallel, teardown after."""
        ftdir.copy_case("fixture_class_yield")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=3)

    def test_function_scoped_fixture(self, ftdir):
        """Function-scoped fixtures get fresh values per test."""
        ftdir.copy_case("fixture_function_scoped")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=4)

    def test_parameterized_fixture(self, ftdir):
        """Parameterized class-scoped fixture expands correctly."""
        ftdir.copy_case("fixture_parameterized")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=4)

    def test_multiple_fixture_scopes(self, ftdir):
        """Session + module + class fixtures compose correctly."""
        ftdir.copy_case("fixture_multiple_scopes")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=3)

    def test_yield_fixture_cleanup(self, ftdir):
        """Yield fixture teardown runs after all parallel methods."""
        ftdir.copy_case("fixture_yield_cleanup")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=3)

    def test_autouse_function_scoped_in_parallel(self, ftdir):
        """Autouse function-scoped fixtures get fresh values per test in parallel."""
        ftdir.copy_case("fixture_autouse_function")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_interdependent_finalizer_ordering(self, ftdir):
        """Dependent fixtures tear down in LIFO order (tx before db)."""
        ftdir.copy_case("fixture_interdependent_finalizers")
        result = ftdir.run_pytest("--threadpool", "2")
        result.assert_outcomes(passed=3)

    def test_fixture_teardown_exception_runs_all_finalizers(self, ftdir):
        """A failing finalizer must not prevent remaining finalizers from running."""
        ftdir.copy_case("fixture_teardown_exception")
        result = ftdir.run_pytest("--threadpool", "2")
        # 3 passed (including verify), 1 teardown error from resource_a
        assert "3 passed" in result.stdout
        assert "1 error" in result.stdout
        # The verify test proves all finalizers ran despite the exception
        assert "FAILED" not in result.stdout

    def test_session_fixture_shared_across_groups(self, ftdir):
        """Session fixture: same object across parallel groups and sequential tests."""
        ftdir.copy_case("fixture_session_across_groups")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=6)

    def test_module_fixture_shared_across_groups(self, ftdir):
        """Module-scoped fixture is the same object across parallel groups and sequential tests."""
        ftdir.copy_case("fixture_module_across_groups")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=6)

    def test_class_fixture_shared_within_isolated_across(self, ftdir):
        """Class-scoped fixture: same object within class, different across classes."""
        ftdir.copy_case("fixture_class_across_groups")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=5)

    def test_package_fixture_shared_across_modules(self, ftdir):
        """Package-scoped fixture is the same object across modules in a package group."""
        from tests.integration_tests.cases.fixture_package_across_groups import (
            CONFTEST_SRC,
            INIT_SRC,
            MOD_A_SRC,
            MOD_B_SRC,
            VERIFY_SRC,
        )

        pkg = ftdir.mkdir("mypkg")
        (pkg / "__init__.py").write_text(INIT_SRC)
        (pkg / "conftest.py").write_text(CONFTEST_SRC)
        (pkg / "test_mod_a.py").write_text(MOD_A_SRC)
        (pkg / "test_mod_b.py").write_text(MOD_B_SRC)
        (ftdir.path / "test_verify.py").write_text(VERIFY_SRC)
        result = ftdir.run_pytest(
            "--threadpool", "4", str(pkg), str(ftdir.path / "test_verify.py")
        )
        result.assert_outcomes(passed=5)
