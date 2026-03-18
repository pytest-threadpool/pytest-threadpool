"""Case: worker raises exception outside CallInfo.from_call.

BUG-1: When a worker throws an unexpected exception (e.g., during
pytest_runtest_makereport), the plugin should report it gracefully
instead of crashing with a KeyError.

This uses a conftest hook to inject a RuntimeError during makereport,
simulating an unexpected worker-level exception.
"""

from pytest_threadpool import parallelizable


@parallelizable("children")
class TestWorkerException:
    def test_normal(self):
        pass

    def test_will_explode(self):
        """This test's makereport call will be sabotaged by the conftest."""

    def test_also_normal(self):
        pass
