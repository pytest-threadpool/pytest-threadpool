"""Simple test file used to trigger --threadpool on a faked GIL build."""

import pytest


@pytest.mark.parallelizable("children")
class TestSimple:
    def test_a(self):
        pass

    def test_b(self):
        pass
