"""ContextLocal (per-test) scope: same instance within a test, fresh between tests.

Pattern: ContextLocal provider + per-test reset in fixture teardown.

Any function can resolve ``Container.test_context()`` and get the same
instance as the calling test — even across ``await`` boundaries that may
resume on a different thread.  ``ContextLocal`` uses ``contextvars``
under the hood, so the context follows the execution flow, not the OS thread.

Parallel tests each run in their own context, so writes in one test
never leak into another.
"""

import asyncio
import functools
import threading
from typing import ClassVar

import pytest

from examples.test_di.container import Container


def async_test(fn):
    """Run an async test function in its own event loop."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


def _helper_that_reads_from_container() -> dict:
    """Simulate a function deep in the call stack resolving from the container."""
    return Container.test_context().data


def _helper_that_writes_to_container(key: str, value: str) -> None:
    """Simulate a function deep in the call stack writing to the context."""
    Container.test_context().data[key] = value


async def _async_helper_that_reads_from_container() -> dict:
    """Async function that resolves the context — may run on a different thread."""
    await asyncio.sleep(0.01)
    return Container.test_context().data


class TestLocal:
    """Each test gets its own TestContext via ContextLocal + reset."""

    _seen_ids: ClassVar[set] = set()
    _lock = threading.Lock()

    @pytest.mark.parametrize("_worker", range(6))
    def test_write_then_read_from_container(self, test_context, _worker):
        """Test writes to context, a helper resolves the same context from the container."""
        test_context.data["worker"] = str(_worker)

        data = _helper_that_reads_from_container()

        assert data["worker"] == str(_worker)
        assert data is test_context.data

    @pytest.mark.parametrize("_worker", range(6))
    def test_helper_writes_visible_to_test(self, test_context, _worker):
        """A helper writes via the container, the test sees it through its fixture."""
        _helper_that_writes_to_container("source", "helper")

        assert test_context.data["source"] == "helper"

    @pytest.mark.parametrize("_worker", range(6))
    def test_parallel_tests_are_isolated(self, test_context, _worker):
        """Each parallel test starts with an empty context — no cross-test leakage."""
        assert test_context.data == {}, f"Context leaked from another test: {test_context.data}"
        test_context.data["mine"] = str(_worker)

    @pytest.mark.parametrize("_worker", range(6))
    def test_context_is_fresh_per_test(self, test_context, _worker):
        """Each test invocation gets a unique TestContext instance."""
        with self._lock:
            assert test_context.instance_id not in self._seen_ids, (
                "ContextLocal+reset reused an instance across tests"
            )
            self._seen_ids.add(test_context.instance_id)

    @async_test
    @pytest.mark.parametrize("_worker", range(6))
    async def test_context_survives_await(self, test_context, _worker):
        """Context is preserved across await boundaries that may switch threads."""
        test_context.data["before_await"] = str(_worker)

        await asyncio.sleep(0.01)

        data = await _async_helper_that_reads_from_container()

        assert data["before_await"] == str(_worker)
        assert data is test_context.data
