"""Conftest that injects a RuntimeError during makereport for a specific test.

This simulates an unexpected exception in worker code outside CallInfo.from_call,
which is the scenario that triggers BUG-1.
"""

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    if "test_will_explode" in item.nodeid and call.when == "setup":
        raise RuntimeError("Simulated worker-level explosion")
    yield
