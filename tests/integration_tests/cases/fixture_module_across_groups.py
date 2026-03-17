"""Module-scoped fixture must be the same object across parallel groups and sequential tests."""

import threading

import pytest

_ids = []
lock = threading.Lock()


class Resource:
    """Mutable object whose identity can be checked via id()."""


@pytest.fixture(scope="module")
def module_resource():
    return Resource()


@pytest.mark.parallelizable("children")
class TestGroupA:
    def test_a1(self, module_resource):
        with lock:
            _ids.append(id(module_resource))

    def test_a2(self, module_resource):
        with lock:
            _ids.append(id(module_resource))


@pytest.mark.not_parallelizable
def test_sequential_between(module_resource):
    with lock:
        _ids.append(id(module_resource))


@pytest.mark.parallelizable("children")
class TestGroupB:
    def test_b1(self, module_resource):
        with lock:
            _ids.append(id(module_resource))

    def test_b2(self, module_resource):
        with lock:
            _ids.append(id(module_resource))


def test_verify():
    assert len(_ids) == 5, f"expected 5 recorded ids, got {len(_ids)}"
    assert len(set(_ids)) == 1, f"module fixture created multiple objects: {set(_ids)}"
