"""All items marked not_parallelizable — verify sequential execution."""

import threading

from pytest_threadpool import not_parallelizable, parallelizable

execution_threads = []
lock = threading.Lock()


@parallelizable("children")
class TestAllNotParallelizable:
    @not_parallelizable
    def test_a(self):
        with lock:
            execution_threads.append(threading.current_thread().name)

    @not_parallelizable
    def test_b(self):
        with lock:
            execution_threads.append(threading.current_thread().name)

    @not_parallelizable
    def test_c(self):
        with lock:
            execution_threads.append(threading.current_thread().name)


def test_verify_sequential():
    """All tests should have run on the main thread (no thread pool)."""
    assert len(execution_threads) == 3
    assert all(t == "MainThread" for t in execution_threads), (
        f"Expected all MainThread, got {execution_threads}"
    )
