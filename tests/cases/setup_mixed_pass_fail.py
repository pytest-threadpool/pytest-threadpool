"""Mixed setup pass/fail within a single parallel group."""

import pytest


@pytest.fixture
def maybe_broken(request):
    if "broken" in request.node.name:
        raise RuntimeError("setup explodes")
    return "ok"


@pytest.mark.parallelizable("children")
class TestMixedSetup:
    def test_good_a(self, maybe_broken):
        assert maybe_broken == "ok"

    def test_broken_b(self, maybe_broken):
        pass

    def test_good_c(self, maybe_broken):
        assert maybe_broken == "ok"
