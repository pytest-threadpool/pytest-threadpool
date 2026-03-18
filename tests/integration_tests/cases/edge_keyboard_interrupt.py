"""Test body raises KeyboardInterrupt during parallel execution."""

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestKeyboardInterrupt:
    def test_normal(self):
        assert True

    def test_interrupts(self):
        raise KeyboardInterrupt

    def test_also_normal(self):
        assert True
