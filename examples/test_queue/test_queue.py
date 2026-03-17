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

from queue import LifoQueue
from time import sleep

import pytest


class TestQueue:
    @pytest.fixture(scope="class")
    def user_pool(self):
        """Imitating a resource pool, putting it into a queue."""
        user_pool = LifoQueue(4)
        for i in ["John", "Peter", "Jane", "Maxwell"]:
            user_pool.put(i)
        return user_pool

    @pytest.fixture
    def test_data(self, user_pool):
        """Get a user from the pool for this test, return it on teardown.

        Pool has 4 users but 5 tests run in parallel. The 5th test blocks
        on Queue.get() until one of the first 4 finishes (after 1s sleep)
        and returns its user via teardown.
        """
        user = user_pool.get(timeout=5)
        yield user
        user_pool.put(user, timeout=5)

    @pytest.mark.parametrize("tc_id", range(5))
    def test(self, test_data, tc_id):
        """4 users in the pool, 5 tests in parallel.

        The first 4 tests each grab a user instantly. The 5th test
        blocks on Queue.get() until one of the others finishes this
        1s sleep and its teardown returns the user to the pool.
        """
        sleep(1)
