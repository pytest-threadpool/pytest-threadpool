"""Per-test file logging — each test writes to its own log file.

When you need persistent debug output that survives the test run
(e.g. for CI artifacts), write to a file in ``tmp_path``.  Each test
gets its own temporary directory, so no coordination is needed.

After the run, inspect logs in the ``tmp_path_factory`` base dir
or configure CI to upload the ``/tmp/pytest-*`` tree as artifacts.
"""

from time import sleep

import pytest


class TestFileLogging:
    """Each test writes debug output to its own temp file."""

    @pytest.mark.parametrize("_worker", range(4))
    def test_per_test_log_file(self, _worker, tmp_path):
        """Write debug data to a file in tmp_path — isolated per test."""
        log_file = tmp_path / "debug.log"

        with log_file.open("w") as f:
            f.write(f"worker {_worker}: starting\n")
            sleep(0.01)
            f.write(f"worker {_worker}: done\n")

        lines = log_file.read_text().splitlines()
        assert lines == [f"worker {_worker}: starting", f"worker {_worker}: done"]
