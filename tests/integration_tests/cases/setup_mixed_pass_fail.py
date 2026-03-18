"""Mixed setup pass/fail within a single parallel group."""

import pytest

from pytest_threadpool import parallelizable


@pytest.fixture
def maybe_broken(request):
    if "broken" in request.node.name:
        raise RuntimeError("setup explodes")
    return "ok"


@parallelizable("children")
class TestMixedSetup:
    def test_good_a(self, maybe_broken):
        assert maybe_broken == "ok"

    def test_broken_b(self, maybe_broken):
        pass

    def test_good_c(self, maybe_broken):
        assert maybe_broken == "ok"
