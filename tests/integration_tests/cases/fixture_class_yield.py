"""Class-scoped yield fixture: setup before parallel, teardown after."""

from typing import ClassVar

import pytest


@pytest.mark.parallelizable("children")
class TestYield:
    log: ClassVar[list] = []

    @pytest.fixture(autouse=True, scope="class")
    def db(self):
        self.log.append("setup")
        yield "conn"
        self.log.append("teardown")

    def test_a(self):
        assert "setup" in self.log

    def test_b(self):
        assert "setup" in self.log


def test_verify():
    assert "setup" in TestYield.log
