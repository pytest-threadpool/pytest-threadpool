"""Package-scoped fixture shared across parallel groups in the same package.

This case provides source strings used by the integration test to
build a temporary package directory.
"""

CONFTEST_SRC = """\
import pytest


class Resource:
    pass


@pytest.fixture(scope="package")
def pkg_resource():
    return Resource()
"""

INIT_SRC = """\
import pytest

pytestmark = pytest.mark.parallelizable("children")
"""

MOD_A_SRC = """\
import threading

lock = threading.Lock()
ids = []


def test_a1(pkg_resource):
    with lock:
        ids.append(id(pkg_resource))


def test_a2(pkg_resource):
    with lock:
        ids.append(id(pkg_resource))
"""

MOD_B_SRC = """\
import threading

lock = threading.Lock()
ids = []


def test_b1(pkg_resource):
    with lock:
        ids.append(id(pkg_resource))


def test_b2(pkg_resource):
    with lock:
        ids.append(id(pkg_resource))
"""

VERIFY_SRC = """\
from mypkg import test_mod_a, test_mod_b


def test_verify():
    all_ids = test_mod_a.ids + test_mod_b.ids
    assert len(all_ids) == 4, f"expected 4 recorded ids, got {len(all_ids)}"
    assert len(set(all_ids)) == 1, (
        f"package fixture created multiple objects: {set(all_ids)}"
    )
"""
