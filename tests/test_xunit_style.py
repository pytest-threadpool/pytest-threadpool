"""xunit-style setup/teardown at every level."""

import threading
import time

import pytest

from tests.markers import parallelizable


# -- module-level xunit setup/teardown --

class _ModuleState:
    log = []


def setup_module(module):
    _ModuleState.log.append("setup_module")


def teardown_module(module):
    _ModuleState.log.append("teardown_module")


def test_module_setup_ran():
    assert "setup_module" in _ModuleState.log


# -- function-level xunit setup/teardown --

class _FuncState:
    log = []


def setup_function(function):
    _FuncState.log.append(f"setup_{function.__name__}")


def teardown_function(function):
    _FuncState.log.append(f"teardown_{function.__name__}")


def test_func_alpha():
    assert "setup_test_func_alpha" in _FuncState.log


def test_func_beta():
    assert "setup_test_func_beta" in _FuncState.log


def test_function_level_teardowns_ran():
    """Verify teardowns ran for previous functions."""
    assert "teardown_test_func_alpha" in _FuncState.log
    assert "teardown_test_func_beta" in _FuncState.log


# -- class with setup_class / teardown_class --
@parallelizable("children")
class TestXunitClassLevel:

    _class_log = []

    @classmethod
    def setup_class(cls):
        cls._class_log.append("setup_class")

    @classmethod
    def teardown_class(cls):
        cls._class_log.append("teardown_class")

    def test_class_setup_ran(self):
        assert "setup_class" in self._class_log

    def test_class_setup_ran_once(self):
        count = self._class_log.count("setup_class")
        assert count == 1, f"setup_class ran {count} times"


# -- class with setup_method / teardown_method --
@parallelizable("children")
class TestXunitMethodLevel:

    _method_log = []

    def setup_method(self, method):
        self._method_log.append(f"setup_{method.__name__}")

    def teardown_method(self, method):
        self._method_log.append(f"teardown_{method.__name__}")

    def test_method_a(self):
        time.sleep(0.1)
        assert "setup_test_method_a" in self._method_log

    def test_method_b(self):
        time.sleep(0.1)
        assert "setup_test_method_b" in self._method_log

    def test_method_c(self):
        time.sleep(0.1)
        assert "setup_test_method_c" in self._method_log


def test_xunit_method_setups_all_ran():
    """Runs after TestXunitMethodLevel (sequential bare function)."""
    setups = [x for x in TestXunitMethodLevel._method_log if x.startswith("setup_")]
    assert len(setups) >= 3, f"expected >= 3 setups, got {setups}"


# -- combined: setup_class + setup_method --
@parallelizable("children")
class TestXunitCombined:

    _combined_log = []

    @classmethod
    def setup_class(cls):
        cls._combined_log.append("class_setup")

    @classmethod
    def teardown_class(cls):
        cls._combined_log.append("class_teardown")

    def setup_method(self, method):
        self._combined_log.append(f"method_setup_{method.__name__}")

    def teardown_method(self, method):
        self._combined_log.append(f"method_teardown_{method.__name__}")

    def test_x(self):
        time.sleep(0.1)

    def test_y(self):
        time.sleep(0.1)

    def test_z(self):
        time.sleep(0.1)


def test_xunit_combined_verify():
    """Runs after TestXunitCombined (sequential bare function)."""
    log = TestXunitCombined._combined_log
    assert log[0] == "class_setup"
    method_setups = [x for x in log if x.startswith("method_setup_")]
    assert len(method_setups) >= 3, f"expected 3 method setups, got {method_setups}"
