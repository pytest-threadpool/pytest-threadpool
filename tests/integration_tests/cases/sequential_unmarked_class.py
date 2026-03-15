"""No marker — class tests run sequentially even with --freethreaded."""

import time
from typing import ClassVar


class TestUnmarked:
    order: ClassVar[list] = []

    def test_first(self):
        time.sleep(0.05)
        self.order.append("first")

    def test_second(self):
        self.order.append("second")

    def test_third(self):
        self.order.append("third")


def test_verify():
    assert TestUnmarked.order == ["first", "second", "third"]
