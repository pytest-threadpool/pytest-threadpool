"""Tests for sequential behavior when no parallel markers are used."""


class TestSequentialExecution:
    """Verify unmarked tests run sequentially even with --threadpool."""

    def test_unmarked_class_runs_sequentially(self, ftdir):
        """Class without parallelizable marker preserves test order."""
        ftdir.copy_case("sequential_unmarked_class")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=4)

    def test_bare_functions_run_sequentially(self, ftdir):
        """Bare module functions run sequentially on one thread."""
        ftdir.copy_case("sequential_bare_functions")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=4)
