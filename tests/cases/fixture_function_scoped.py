"""Function-scoped fixtures get fresh values per test."""
import pytest


@pytest.mark.parallelizable("children")
class TestFuncScope:
    call_log = []

    @pytest.fixture(autouse=True)
    def counter(self):
        idx = len(self.call_log)
        self.call_log.append(f"setup_{idx}")
        yield idx

    def test_a(self, counter):
        assert isinstance(counter, int)

    def test_b(self, counter):
        assert isinstance(counter, int)

    def test_c(self, counter):
        assert isinstance(counter, int)


def test_verify():
    setups = [x for x in TestFuncScope.call_log if x.startswith("setup_")]
    assert len(setups) == 3
