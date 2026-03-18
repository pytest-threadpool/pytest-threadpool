"""Unit tests for ScreenBuffer."""

import threading

from pytest_threadpool._live_view import ScreenBuffer


class TestScreenBuffer:
    """ScreenBuffer is a growable in-memory line buffer."""

    def test_add_lines_and_set(self):
        """add_lines reserves rows; set_line updates them."""
        buf = ScreenBuffer()
        start = buf.add_lines(3)
        assert start == 0
        buf.set_line(0, "aaa")
        buf.set_line(1, "bbb")
        buf.set_line(2, "ccc")
        assert buf.snapshot() == ["aaa", "bbb", "ccc"]

    def test_add_lines_grows(self):
        """Multiple add_lines calls grow the buffer."""
        buf = ScreenBuffer()
        s1 = buf.add_lines(2)
        s2 = buf.add_lines(3)
        assert s1 == 0
        assert s2 == 2
        assert buf.nlines == 5

    def test_snapshot_is_a_copy(self):
        """Mutating the snapshot doesn't affect the buffer."""
        buf = ScreenBuffer()
        buf.add_lines(1)
        buf.set_line(0, "hello")
        snap = buf.snapshot()
        snap[0] = "CHANGED"
        assert buf.snapshot()[0] == "hello"

    def test_concurrent_set_line(self):
        """set_line from multiple threads doesn't crash."""
        buf = ScreenBuffer()
        buf.add_lines(10)
        barrier = threading.Barrier(4)

        def writer(tid):
            barrier.wait()
            for _ in range(100):
                for row in range(10):
                    buf.set_line(row, f"t{tid}-r{row}")

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        snap = buf.snapshot()
        assert len(snap) == 10
