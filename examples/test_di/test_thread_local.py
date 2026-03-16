"""ThreadLocal scope: one DbConnection per worker thread.

ThreadLocal binds to the OS thread.  This means it does NOT survive
``await`` boundaries — if the event loop resumes a coroutine on a
different thread, a new instance is created.  Use ContextLocal
(see test_local.py) when you need context that follows the execution
flow across awaits.
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


class TestThreadLocal:
    """DbConnection is ThreadLocal — same instance within a thread,
    different instances across threads.
    """

    _ids_by_thread: ClassVar[dict] = {}
    _lock = threading.Lock()

    @pytest.mark.parametrize("_worker", range(6))
    def test_db_is_per_thread(self, request_handler, _worker):
        db = request_handler.db
        tid = threading.current_thread().ident
        with self._lock:
            if tid in self._ids_by_thread:
                assert self._ids_by_thread[tid] == db.instance_id, (
                    "ThreadLocal returned different instance on same thread"
                )
            else:
                self._ids_by_thread[tid] = db.instance_id

    @async_test
    @pytest.mark.parametrize("_worker", range(6))
    async def test_thread_local_does_not_survive_await(self, _worker):
        """ThreadLocal may return a different instance after an await.

        If ``asyncio.run()`` uses a thread pool internally, an ``await``
        can resume on a different OS thread — and ThreadLocal is keyed
        by thread, so it produces a new instance.  This is the key
        difference from ContextLocal.
        """
        before = Container.db_connection()
        before_tid = threading.current_thread().ident

        results: dict = {}

        async def resolve_after_await():
            await asyncio.sleep(0.01)
            results["db"] = Container.db_connection()
            results["tid"] = threading.current_thread().ident

        await resolve_after_await()

        if before_tid != results["tid"]:
            assert before.instance_id != results["db"].instance_id, (
                "ThreadLocal returned same instance on different thread"
            )
        else:
            assert before.instance_id == results["db"].instance_id
