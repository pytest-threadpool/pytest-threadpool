"""Tests for class-level parallel execution."""


class TestClassParallel:
    """Verify @parallelizable('children') on classes via isolated subprocess runs."""

    def test_barrier_proves_concurrency(self, ftdir):
        """3-party barrier succeeds only if methods run concurrently."""
        ftdir.copy_case("class_barrier_concurrency")
        result = ftdir.run_pytest("--threadpool", "3")
        result.assert_outcomes(passed=3)

    def test_uses_multiple_threads(self, ftdir):
        """Verify methods actually run on different threads."""
        ftdir.copy_case("class_thread_verification")
        result = ftdir.run_pytest("--threadpool", "3", "-s")
        result.assert_outcomes(passed=3)
        # Worker print() is captured and reported alongside the test
        # result, so look in full stdout (includes captured sections).
        threads = {
            line.split("THREAD:")[1] for line in result.stdout.splitlines() if "THREAD:" in line
        }
        assert len(threads) >= 2, f"expected multiple threads, got {threads}"

    def test_single_method_class(self, ftdir):
        """A class with one test falls back to sequential without error."""
        ftdir.copy_case("class_single_method")
        result = ftdir.run_pytest("--threadpool", "auto")
        result.assert_outcomes(passed=1)
