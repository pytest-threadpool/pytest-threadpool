"""
Thread-safe resource pool shared across parallel tests.

This pattern is impossible with pytest-xdist — each xdist worker is a
separate process, so in-memory objects like Queue, Lock, or connection
pools can't be shared. You'd need external coordination (Redis, a
database, file locks) to achieve the same thing.

With pytest-threadpool, all tests run in the same process. A standard
Queue acts as a thread-safe resource pool with zero overhead:
- 4 users in the pool, 5 tests in parallel
- First 4 tests each grab a user instantly
- 5th test blocks on Queue.get() until one finishes and returns its user
"""

from time import sleep

import pytest


class TestCase1:
    @pytest.mark.parametrize("tc_id", [1, 2, 3, 4, 5])
    def test(self, test_data, tc_id):
        """4 users in the pool, 5 tests in parallel.

        The first 4 tests each grab a user instantly. The 5th test
        blocks on Queue.get() until one of the others finishes this
        1s sleep and its teardown returns the user to the pool.
        """
        sleep(1)
