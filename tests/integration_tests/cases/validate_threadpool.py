"""Simple test file used to trigger --threadpool on a faked GIL build."""

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestSimple:
    def test_a(self):
        pass

    def test_b(self):
        pass
