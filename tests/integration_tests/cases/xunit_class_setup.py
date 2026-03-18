"""setup_class runs once before parallel methods."""

from typing import ClassVar

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestClassSetup:
    log: ClassVar[list] = []

    @classmethod
    def setup_class(cls):
        cls.log.append("setup_class")

    @classmethod
    def teardown_class(cls):
        cls.log.append("teardown_class")

    def test_a(self):
        assert "setup_class" in self.log

    def test_b(self):
        count = self.log.count("setup_class")
        assert count == 1


def test_verify():
    assert TestClassSetup.log[0] == "setup_class"
