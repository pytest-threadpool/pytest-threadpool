"""Function-level setup_function / teardown_function."""

from typing import ClassVar


class _State:
    log: ClassVar[list] = []


def setup_function(function):
    _State.log.append(f"setup_{function.__name__}")


def teardown_function(function):
    _State.log.append(f"teardown_{function.__name__}")


def test_alpha():
    assert "setup_test_alpha" in _State.log


def test_beta():
    assert "setup_test_beta" in _State.log


def test_verify():
    assert "teardown_test_alpha" in _State.log
