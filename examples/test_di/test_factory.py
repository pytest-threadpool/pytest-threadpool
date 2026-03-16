"""Factory scope: fresh RequestHandler for every injection."""

import threading
from typing import ClassVar

import pytest


class TestFactory:
    """RequestHandler is a Factory — every injection must be a fresh instance."""

    _seen_ids: ClassVar[set] = set()
    _lock = threading.Lock()

    @pytest.mark.parametrize("_worker", range(6))
    def test_handler_is_fresh(self, request_handler, _worker):
        with self._lock:
            assert request_handler.instance_id not in self._seen_ids, "Factory reused an instance"
            self._seen_ids.add(request_handler.instance_id)
