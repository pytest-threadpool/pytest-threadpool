"""Built-in tmp_path fixture works correctly in parallel (function-scoped)."""

import threading
from typing import ClassVar

import pytest


@pytest.mark.parallelizable("children")
class TestTmpPath:
    barrier = threading.Barrier(3, timeout=10)
    paths: ClassVar[list] = []
    lock: ClassVar[threading.Lock] = threading.Lock()

    def test_a(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("hello from a")
        with self.lock:
            self.paths.append(str(tmp_path))
        self.barrier.wait()
        assert f.read_text() == "hello from a"

    def test_b(self, tmp_path):
        f = tmp_path / "b.txt"
        f.write_text("hello from b")
        with self.lock:
            self.paths.append(str(tmp_path))
        self.barrier.wait()
        assert f.read_text() == "hello from b"

    def test_c(self, tmp_path):
        f = tmp_path / "c.txt"
        f.write_text("hello from c")
        with self.lock:
            self.paths.append(str(tmp_path))
        self.barrier.wait()
        assert f.read_text() == "hello from c"


def test_verify():
    # Each test must have received a unique tmp_path directory
    assert len(TestTmpPath.paths) == 3
    assert len(set(TestTmpPath.paths)) == 3, (
        f"tmp_path directories must be unique: {TestTmpPath.paths}"
    )
