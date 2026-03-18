"""Class-scoped fixture: same object within a class, different across classes."""

import threading

import pytest

from pytest_threadpool import parallelizable

_ids_a = []
_ids_b = []
lock = threading.Lock()


class Resource:
    """Mutable object whose identity can be checked via id()."""


@pytest.fixture(scope="class")
def class_resource():
    return Resource()


@parallelizable("children")
class TestGroupA:
    def test_a1(self, class_resource):
        with lock:
            _ids_a.append(id(class_resource))

    def test_a2(self, class_resource):
        with lock:
            _ids_a.append(id(class_resource))


@parallelizable("children")
class TestGroupB:
    def test_b1(self, class_resource):
        with lock:
            _ids_b.append(id(class_resource))

    def test_b2(self, class_resource):
        with lock:
            _ids_b.append(id(class_resource))


def test_verify():
    # Within each class, all tests see the same object
    assert len(set(_ids_a)) == 1, f"class A fixture not shared: {set(_ids_a)}"
    assert len(set(_ids_b)) == 1, f"class B fixture not shared: {set(_ids_b)}"
    # Across classes, fixtures are different objects
    assert _ids_a[0] != _ids_b[0], "class-scoped fixture leaked across classes"
