import pytest

from examples.test_queue.user_pool import UserPool


@pytest.fixture
def test_data():
    """Get a user from the pool for this test, return it on teardown.

    Pool has 4 users but 5 tests run in parallel. The 5th test blocks
    on Queue.get() until one of the first 4 finishes (after 1s sleep)
    and returns its user via teardown.
    """
    user = UserPool.get_user()
    yield user
    UserPool.release_user(user)
