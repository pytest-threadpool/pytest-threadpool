"""Tests for thread-safe shared state under parallel execution."""

import pytest


class TestSharedStateUnderParallel:
    """Verify thread-safe dict/counter operations with parallel children."""

    def test_thread_safe_dict_mutation(self, ftdir):
        """Concurrent dict writes from parallel methods are consistent."""
        ftdir.copy_case("shared_dict_mutation")
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=4)

    def test_lock_free_counter(self, ftdir):
        """Each thread counts independently, results are correct."""
        ftdir.copy_case("shared_counter")
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=4)

    def test_barrier_sync_proves_concurrency(self, ftdir):
        """Two-phase barrier proves tests truly run concurrently."""
        ftdir.copy_case("shared_two_phase_barrier")
        result = ftdir.run_pytest("--freethreaded", "3")
        result.assert_outcomes(passed=3)
