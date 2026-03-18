"""setup_method runs per method even with parallel children."""

from typing import ClassVar

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestMethodSetup:
    log: ClassVar[list] = []

    def setup_method(self, method):
        self.log.append(f"setup_{method.__name__}")

    def test_a(self):
        assert "setup_test_a" in self.log

    def test_b(self):
        assert "setup_test_b" in self.log

    def test_c(self):
        assert "setup_test_c" in self.log


def test_verify():
    setups = [x for x in TestMethodSetup.log if x.startswith("setup_")]
    assert len(setups) >= 3
