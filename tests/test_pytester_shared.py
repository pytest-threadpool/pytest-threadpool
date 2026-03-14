"""Tests for thread-safe shared state under parallel execution."""


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

    def test_non_pickleable_objects(self, ftdir):
        """Non-pickleable thread-safe objects (Lock, Condition, etc.) work in parallel groups."""
        ftdir.copy_case("shared_non_pickleable")
        result = ftdir.run_pytest("--freethreaded", "4")
        result.assert_outcomes(passed=5)

    def test_cross_group_non_pickleable_objects(self, ftdir):
        """Non-pickleable objects shared across different parallel groups stay consistent."""
        ftdir.copy_case("shared_cross_group_non_pickleable")
        result = ftdir.run_pytest("--freethreaded", "2")
        result.assert_outcomes(passed=5)
