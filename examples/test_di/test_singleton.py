"""Singleton scope: one Config instance shared across all tests."""

import threading
from typing import ClassVar

import pytest


class TestSingleton:
    """Config is a Singleton — every test must see the exact same instance."""

    _seen_ids: ClassVar[set] = set()
    _lock = threading.Lock()

    @pytest.mark.parametrize("_worker", range(6))
    def test_config_is_shared(self, request_handler, _worker):
        config = request_handler.config
        with self._lock:
            self._seen_ids.add(config.instance_id)
            assert len(self._seen_ids) == 1, f"Singleton produced {len(self._seen_ids)} instances"
