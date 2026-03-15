"""Tests that spawn their own threads during parallel execution."""

import threading

import pytest

results = {}
lock = threading.Lock()


def background_work(name, value):
    computed = value * 2
    with lock:
        results[name] = computed


@pytest.mark.parallelizable("children")
class TestNestedThreads:
    def test_spawns_thread_a(self):
        t = threading.Thread(target=background_work, args=("a", 10))
        t.start()
        t.join(timeout=5)
        assert not t.is_alive()

    def test_spawns_thread_b(self):
        t = threading.Thread(target=background_work, args=("b", 20))
        t.start()
        t.join(timeout=5)
        assert not t.is_alive()

    def test_spawns_thread_c(self):
        t = threading.Thread(target=background_work, args=("c", 30))
        t.start()
        t.join(timeout=5)
        assert not t.is_alive()


def test_verify_nested_results():
    assert results == {"a": 20, "b": 40, "c": 60}
