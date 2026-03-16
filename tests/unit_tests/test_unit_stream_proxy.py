"""Unit tests for _ThreadLocalStream proxy."""

import io
import threading

from pytest_threadpool._runner import _ThreadLocalStream


class TestThreadLocalStream:
    """Verify stream proxy routes writes correctly per-thread."""

    def test_passthrough_when_not_activated(self):
        """Writes pass through to real stream when proxy is not activated."""
        real = io.StringIO()
        proxy = _ThreadLocalStream(real)
        proxy.write("hello")
        assert real.getvalue() == "hello"

    def test_buffered_when_activated(self):
        """Writes go to buffer after activate(), not to real stream."""
        real = io.StringIO()
        proxy = _ThreadLocalStream(real)
        proxy.activate()
        proxy.write("buffered")
        assert real.getvalue() == ""

    def test_passthrough_after_deactivate(self):
        """Writes pass through again after deactivate()."""
        real = io.StringIO()
        proxy = _ThreadLocalStream(real)
        proxy.activate()
        proxy.write("buffered")
        proxy.deactivate()
        proxy.write("visible")
        assert real.getvalue() == "visible"

    def test_flush_passthrough(self):
        """flush() calls real stream flush when not activated."""
        real = io.StringIO()
        proxy = _ThreadLocalStream(real)
        proxy.flush()  # should not raise

    def test_flush_activated(self):
        """flush() does not flush real stream when activated."""
        real = io.StringIO()
        flushed = []
        real.flush = lambda: flushed.append(True)
        proxy = _ThreadLocalStream(real)
        proxy.activate()
        proxy.flush()
        assert not flushed

    def test_getattr_delegation(self):
        """Attributes not on proxy are delegated to real stream."""
        real = io.StringIO()
        proxy = _ThreadLocalStream(real)
        assert proxy.readable() == real.readable()

    def test_per_thread_isolation(self):
        """Each thread has independent activation state."""
        real = io.StringIO()
        proxy = _ThreadLocalStream(real)
        results = {}

        def worker(name, activate):
            if activate:
                proxy.activate()
            proxy.write(f"{name}")
            if activate:
                proxy.deactivate()
            results[name] = True

        t1 = threading.Thread(target=worker, args=("t1", True))
        t2 = threading.Thread(target=worker, args=("t2", False))
        t1.start()
        t1.join()
        t2.start()
        t2.join()

        # t1 was activated so its write went to buffer, t2 passed through
        assert "t2" in real.getvalue()
        assert "t1" not in real.getvalue()

    def test_concurrent_isolation(self):
        """Multiple threads activated concurrently don't cross-contaminate."""
        real = io.StringIO()
        proxy = _ThreadLocalStream(real)
        barrier = threading.Barrier(3)
        buffers = {}

        def worker(name):
            proxy.activate()
            barrier.wait()
            proxy.write(f"data_{name}")
            barrier.wait()
            # Read back from the thread-local buffer
            buf = proxy._local.buf
            buffers[name] = buf.getvalue() if buf else ""
            proxy.deactivate()

        threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread should only see its own data
        for i in range(3):
            assert buffers[f"w{i}"] == f"data_w{i}"

        # Nothing should have leaked to real stream
        assert real.getvalue() == ""

    def test_write_returns_length(self):
        """write() returns the number of characters written."""
        real = io.StringIO()
        proxy = _ThreadLocalStream(real)
        assert proxy.write("hello") == 5

        proxy.activate()
        assert proxy.write("world") == 5
        proxy.deactivate()
