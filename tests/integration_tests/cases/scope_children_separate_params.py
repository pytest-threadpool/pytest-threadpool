"""'children' keeps parametrized variants in separate groups."""

from typing import ClassVar

import pytest


@pytest.mark.parallelizable("children")
class TestChildren:
    results: ClassVar[dict] = {}

    @pytest.mark.parametrize("val", ["a", "b"])
    def test_item(self, val):
        self.results[val] = True


def test_verify():
    assert set(TestChildren.results.keys()) == {"a", "b"}
