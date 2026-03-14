"""conftest that fakes a GIL-enabled Python for testing the validation."""
import sys


def pytest_configure(config):
    # Override _is_gil_enabled to simulate a GIL-enabled build
    sys._is_gil_enabled = lambda: True
