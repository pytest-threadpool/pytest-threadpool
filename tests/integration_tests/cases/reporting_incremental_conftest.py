"""Conftest plugin that records report timestamps to a JSON file.

Placed alongside the test case as conftest.py by the outer test.
Writes all entries to report_log.json in the same directory as this conftest.
"""

import json
import threading
import time
from pathlib import Path

_lock = threading.Lock()
_log_path = Path(__file__).parent / "report_log.json"


def pytest_runtest_logreport(report):
    if report.when != "call":
        return
    entry = {
        "nodeid": report.nodeid,
        "timestamp": time.monotonic(),
        "outcome": report.outcome,
    }
    with _lock:
        entries = []
        if _log_path.exists():
            entries = json.loads(_log_path.read_text())
        entries.append(entry)
        _log_path.write_text(json.dumps(entries))
