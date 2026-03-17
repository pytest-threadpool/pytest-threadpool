"""In-memory event bus — thread-safe test double.

A minimal pub/sub bus that records all published events. Tests publish
events concurrently, then verify delivery, ordering, and deduplication
against the shared log.

With pytest-xdist this would require an external broker (Redis, RabbitMQ)
or a socket-based mock server since each worker is a separate process.
With pytest-threadpool it's a plain Python object protected by a Lock.
"""

import threading


class EventBus:
    """Thread-safe in-memory event bus for testing.

    Instance-based: each test scope gets its own bus via a fixture,
    with proper setup/teardown handled by pytest's fixture lifecycle.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._events: list[dict] = []
        self._subscribers: dict[str, list] = {}
        self._waiters: list[tuple[str | None, int, threading.Event]] = []

    def publish(self, topic: str, payload: dict) -> None:
        with self._lock:
            event = {"topic": topic, "payload": payload, "thread": threading.current_thread().name}
            self._events.append(event)
            for callback in self._subscribers.get(topic, []):
                callback(event)
            self._check_waiters()

    def subscribe(self, topic: str, callback) -> None:
        with self._lock:
            self._subscribers.setdefault(topic, []).append(callback)

    def events(self, topic: str | None = None) -> list[dict]:
        with self._lock:
            if topic is None:
                return list(self._events)
            return [e for e in self._events if e["topic"] == topic]

    def wait_for(self, count: int, topic: str | None = None, timeout: float = 10) -> list[dict]:
        """Block until at least ``count`` events match, then return them."""
        ready = threading.Event()
        with self._lock:
            matched = self._filter(topic)
            if len(matched) >= count:
                return matched
            self._waiters.append((topic, count, ready))
        if not ready.wait(timeout=timeout):
            actual = len(self.events(topic))
            label = f"topic={topic!r}" if topic else "all topics"
            raise TimeoutError(
                f"EventBus.wait_for: expected {count} events on {label}, "
                f"got {actual} after {timeout}s"
            )
        return self.events(topic)

    def _check_waiters(self) -> None:
        """Signal any waiters whose condition is met. Must hold _lock."""
        remaining = []
        for topic, count, event in self._waiters:
            if len(self._filter(topic)) >= count:
                event.set()
            else:
                remaining.append((topic, count, event))
        self._waiters[:] = remaining

    def _filter(self, topic: str | None) -> list[dict]:
        if topic is None:
            return list(self._events)
        return [e for e in self._events if e["topic"] == topic]
