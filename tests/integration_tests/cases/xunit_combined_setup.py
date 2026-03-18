"""Both setup_class and setup_method work together."""

from typing import ClassVar

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestCombined:
    log: ClassVar[list] = []

    @classmethod
    def setup_class(cls):
        cls.log.append("class_setup")

    def setup_method(self, method):
        self.log.append(f"method_setup_{method.__name__}")

    def test_x(self):
        pass

    def test_y(self):
        pass


def test_verify():
    assert TestCombined.log[0] == "class_setup"
    method_setups = [x for x in TestCombined.log if x.startswith("method_setup_")]
    assert len(method_setups) >= 2
