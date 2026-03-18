"""Parameterized class-scoped fixture expands correctly."""

import pytest

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestParamFixture:
    @pytest.fixture(params=["alpha", "beta"], scope="class", autouse=True)
    def variant(self, request):
        return request.param

    def test_is_str(self, variant):
        assert isinstance(variant, str)

    def test_in_set(self, variant):
        assert variant in {"alpha", "beta"}
