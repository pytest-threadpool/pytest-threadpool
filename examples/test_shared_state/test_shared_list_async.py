"""Async version of the shared list example.

Each test runs its own asyncio event loop via ``asyncio.run()``.
Inside, ``await asyncio.sleep()`` yields control within the loop,
while pytest-threadpool runs the tests across real OS threads.

The verify test polls the shared state with ``await asyncio.sleep()``
until all writers have finished — no Barrier or other threading
primitives needed.
"""

import asyncio
from typing import ClassVar

import pytest


class TestSharedListAsync:
    results: ClassVar[list] = []

    @pytest.mark.parametrize("value", ["alpha", "beta", "gamma", "delta"])
    def test_append(self, value):
        """Each test appends from its own event loop."""

        async def _append():
            await asyncio.sleep(0.1)
            self.results.append(value)

        asyncio.run(_append())

    def test_verify(self):
        """Poll until all 4 writers are done, then verify."""

        async def _verify():
            async with asyncio.timeout(10):
                while len(self.results) < 4:
                    await asyncio.sleep(0.01)
            assert sorted(self.results) == ["alpha", "beta", "delta", "gamma"]

        asyncio.run(_verify())
