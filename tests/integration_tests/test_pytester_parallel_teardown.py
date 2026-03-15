"""Tests for parallel function-scoped fixture and xunit teardown.

Function-scoped teardown (yield cleanup, addfinalizer callbacks,
xunit teardown_method/teardown_function) runs in the same worker
thread as setup and call, in parallel across items.
"""


class TestParallelTeardown:
    """Verify function-scoped teardown runs in parallel workers."""

    def test_teardown_runs_in_parallel(self, ftdir):
        """Slow teardowns complete faster than sequential total."""
        ftdir.copy_case("teardown_parallel_timing")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_teardown_same_thread_as_call(self, ftdir):
        """Yield fixture teardown runs on the same thread as the test call."""
        ftdir.copy_case("teardown_same_thread")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_teardown_runs_after_test_failure(self, ftdir):
        """Fixture teardown runs even when the test call fails or errors."""
        ftdir.copy_case("teardown_after_test_failure")
        result = ftdir.run_pytest("--threadpool", "3")
        # test_pass + test_verify pass; test_fail + test_raise fail
        # test_verify proves all 3 teardowns ran
        result.assert_outcomes(passed=2, failed=2)

    def test_xunit_teardown_function_in_worker(self, ftdir):
        """xunit teardown_function runs on the same worker thread as setup."""
        ftdir.copy_case("teardown_xunit_function")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)

    def test_xunit_teardown_method_same_thread(self, ftdir):
        """xunit setup_method, test call, and teardown_method all on same thread."""
        ftdir.copy_case("teardown_xunit_method_thread")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=4)
