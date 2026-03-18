"""Single-method class — falls back to sequential without error."""

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestSolo:
    def test_only(self):
        assert True
