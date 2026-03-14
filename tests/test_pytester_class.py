"""Tests for class-level parallel execution."""

import pytest


class TestClassParallel:
    """Verify @parallelizable('children') on classes via isolated subprocess runs."""

    def test_barrier_proves_concurrency(self, ftdir):
        """3-party barrier succeeds only if methods run concurrently."""
        ftdir.copy_case("class_barrier_concurrency")
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=3)

    def test_uses_multiple_threads(self, ftdir):
        """Verify methods actually run on different threads."""
        ftdir.copy_case("class_thread_verification")
        result = ftdir.run_pytest("--freethreaded", "3", "-s")
        result.assert_outcomes(passed=3)
        threads = {l.split("THREAD:")[1] for l in result.outlines if "THREAD:" in l}
        assert len(threads) >= 2, f"expected multiple threads, got {threads}"

    def test_single_method_class(self, ftdir):
        """A class with one test falls back to sequential without error."""
        ftdir.copy_case("class_single_method")
        result = ftdir.run_pytest("--freethreaded", "auto")
        result.assert_outcomes(passed=1)
