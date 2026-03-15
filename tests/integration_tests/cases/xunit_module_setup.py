"""Module-level setup_module / teardown_module."""

from typing import ClassVar


class _State:
    log: ClassVar[list] = []


def setup_module(module):
    _State.log.append("setup_module")


def teardown_module(module):
    _State.log.append("teardown_module")


def test_setup_ran():
    assert "setup_module" in _State.log
