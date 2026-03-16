"""Async version of the shared dict example.

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


class TestSharedDictAsync:
    results: ClassVar[dict] = {}

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("host", "localhost"),
            ("port", 8080),
            ("env", "test"),
            ("debug", True),
        ],
    )
    def test_write(self, key, value):
        """Each test writes a different key from its own event loop."""

        async def _write():
            await asyncio.sleep(0.1)
            self.results[key] = value

        asyncio.run(_write())

    def test_verify(self):
        """Poll until all 4 writers are done, then verify."""

        async def _verify():
            async with asyncio.timeout(10):
                while len(self.results) < 4:
                    await asyncio.sleep(0.01)
            assert self.results == {
                "host": "localhost",
                "port": 8080,
                "env": "test",
                "debug": True,
            }

        asyncio.run(_verify())
