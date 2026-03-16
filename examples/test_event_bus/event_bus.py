"""In-memory event bus — thread-safe test double.

A minimal pub/sub bus that records all published events. Tests publish
events concurrently, then verify delivery, ordering, and deduplication
against the shared log.

With pytest-xdist this would require an external broker (Redis, RabbitMQ)
or a socket-based mock server since each worker is a separate process.
With pytest-threadpool it's a plain Python object protected by a Lock.
"""

import threading
from typing import ClassVar


class EventBus:
    """Thread-safe in-memory event bus for testing."""

    _lock = threading.Lock()
    _events: ClassVar[list[dict]] = []
    _subscribers: ClassVar[dict[str, list]] = {}
    _waiters: ClassVar[list[tuple[str | None, int, threading.Event]]] = []

    @classmethod
    def publish(cls, topic: str, payload: dict) -> None:
        with cls._lock:
            event = {"topic": topic, "payload": payload, "thread": threading.current_thread().name}
            cls._events.append(event)
            for callback in cls._subscribers.get(topic, []):
                callback(event)
            cls._check_waiters()

    @classmethod
    def subscribe(cls, topic: str, callback) -> None:
        with cls._lock:
            cls._subscribers.setdefault(topic, []).append(callback)

    @classmethod
    def events(cls, topic: str | None = None) -> list[dict]:
        with cls._lock:
            if topic is None:
                return list(cls._events)
            return [e for e in cls._events if e["topic"] == topic]

    @classmethod
    def wait_for(cls, count: int, topic: str | None = None, timeout: float = 10) -> list[dict]:
        """Block until at least ``count`` events match, then return them."""
        ready = threading.Event()
        with cls._lock:
            matched = cls._filter(topic)
            if len(matched) >= count:
                return matched
            cls._waiters.append((topic, count, ready))
        if not ready.wait(timeout=timeout):
            actual = len(cls.events(topic))
            label = f"topic={topic!r}" if topic else "all topics"
            raise TimeoutError(
                f"EventBus.wait_for: expected {count} events on {label}, "
                f"got {actual} after {timeout}s"
            )
        return cls.events(topic)

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._events.clear()
            cls._subscribers.clear()
            cls._waiters.clear()

    @classmethod
    def _check_waiters(cls) -> None:
        """Signal any waiters whose condition is met. Must hold _lock."""
        remaining = []
        for topic, count, event in cls._waiters:
            if len(cls._filter(topic)) >= count:
                event.set()
            else:
                remaining.append((topic, count, event))
        cls._waiters[:] = remaining

    @classmethod
    def _filter(cls, topic: str | None) -> list[dict]:
        if topic is None:
            return list(cls._events)
        return [e for e in cls._events if e["topic"] == topic]
