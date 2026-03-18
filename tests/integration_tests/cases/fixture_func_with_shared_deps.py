"""Function-scoped fixtures that depend on session/module/class fixtures."""

import threading
from typing import ClassVar

import pytest

from pytest_threadpool import parallelizable


class TestState:
    log: ClassVar[list] = []
    log_lock: ClassVar[threading.Lock] = threading.Lock()


@pytest.fixture(scope="session")
def session_id():
    return "sess_001"


@pytest.fixture(scope="module")
def module_id():
    return "mod_001"


@pytest.fixture(scope="class")
def class_id():
    return "cls_001"


@pytest.fixture
def composite(request, session_id, module_id, class_id):
    """Function-scoped fixture depending on all three shared scopes."""
    value = f"{session_id}/{module_id}/{class_id}/{request.node.name}"
    with TestState.log_lock:
        TestState.log.append(value)
    return value


@parallelizable("children")
class TestFuncWithSharedDeps:
    barrier = threading.Barrier(3, timeout=10)

    def test_a(self, composite):
        assert composite == "sess_001/mod_001/cls_001/test_a"
        self.barrier.wait()

    def test_b(self, composite):
        assert composite == "sess_001/mod_001/cls_001/test_b"
        self.barrier.wait()

    def test_c(self, composite):
        assert composite == "sess_001/mod_001/cls_001/test_c"
        self.barrier.wait()


def test_verify():
    assert len(TestState.log) == 3
    names = {v.split("/")[-1] for v in TestState.log}
    assert names == {"test_a", "test_b", "test_c"}
    # All share the same session/module/class prefixes
    prefixes = {"/".join(v.split("/")[:3]) for v in TestState.log}
    assert prefixes == {"sess_001/mod_001/cls_001"}
