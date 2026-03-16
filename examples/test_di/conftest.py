"""Fixtures resolving from the static DI container.

- ``request_handler`` injects a fresh RequestHandler per test (Factory).
- ``test_context`` injects a per-test TestContext (ContextLocal, reset per test).
"""

import pytest

from examples.test_di.container import Container


@pytest.fixture
def request_handler():
    """Fresh RequestHandler per test (Factory provider)."""
    return Container.request_handler()


@pytest.fixture
def test_context():
    """Per-test TestContext — ContextLocal + reset = test-local scope.

    ContextLocal uses contextvars, so the instance follows the execution
    context — not the OS thread.  Safe across await boundaries.
    The reset() in teardown gives the next test a fresh instance.
    """
    ctx = Container.test_context()
    yield ctx
    Container.test_context.reset()
