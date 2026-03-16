"""Shared in-memory test double — concurrent access to a shared event bus.

This pattern is impossible with pytest-xdist: each subprocess has its own
memory space, so a plain Python object can't collect events from multiple
workers. You'd need Redis, a socket server, or a temp file to coordinate.

With pytest-threadpool, all tests share the same process. The EventBus
is a regular class with a Lock — all tests publish and verify their own
events concurrently, and the shared bus proves cross-test visibility.

Patterns demonstrated:
- Each test is self-contained: publishes, subscribes, and verifies its own data
- Concurrent access to a shared in-memory object from parallel threads
- Subscriber callbacks firing synchronously during publish
- Aggregate cross-test visibility via wait_for (without depending on other tests)
"""

import threading
from typing import ClassVar

import pytest

from examples.test_event_bus.event_bus import EventBus


@pytest.mark.parallelizable("children")
class TestEventBus:
    """All tests run in parallel, each self-contained but sharing one bus."""

    _N_PUBLISHERS = 4

    def _publish_own_events(self, name: str) -> None:
        """Each test publishes its own uniquely-tagged events."""
        EventBus.publish("work", {"source": name, "step": "start"})
        EventBus.publish("work", {"source": name, "step": "done"})

    def test_publish_and_verify_signup(self):
        """Publish signup events and verify only own events are correct."""
        EventBus.publish("user.created", {"user_id": "u1"})
        EventBus.publish("email.queued", {"to": "a@test.com", "template": "welcome"})

        own_emails = [
            e for e in EventBus.events("email.queued") if e["payload"]["to"] == "a@test.com"
        ]
        assert len(own_emails) == 1
        assert own_emails[0]["payload"]["template"] == "welcome"

    def test_publish_and_verify_purchase(self):
        """Publish purchase events and verify own events landed."""
        EventBus.publish("order.created", {"order_id": "o1", "user_id": "u2"})
        EventBus.publish("payment.charged", {"order_id": "o1", "amount": 99})

        own = [e for e in EventBus.events("payment.charged") if e["payload"]["order_id"] == "o1"]
        assert len(own) == 1
        assert own[0]["payload"]["amount"] == 99

    def test_subscriber_callback_fires_on_publish(self):
        """Subscribe, publish, verify callback fired — all within one test."""
        received: list[dict] = []
        lock = threading.Lock()

        def on_event(event):
            with lock:
                received.append(event)

        EventBus.subscribe("audit.log", on_event)
        EventBus.publish("audit.log", {"action": "login", "user": "alice"})
        EventBus.publish("audit.log", {"action": "logout", "user": "alice"})

        with lock:
            actions = [e["payload"]["action"] for e in received]
        assert actions == ["login", "logout"]

    def test_wait_for_own_events(self):
        """Publish from a background thread, wait_for in the test thread."""
        topic = "async.work"

        def background_publisher():
            EventBus.publish(topic, {"step": 1})
            EventBus.publish(topic, {"step": 2})

        t = threading.Thread(target=background_publisher)
        t.start()

        events = EventBus.wait_for(2, topic=topic)
        t.join(timeout=10)

        steps = [e["payload"]["step"] for e in events]
        assert 1 in steps
        assert 2 in steps

    # -- aggregate visibility: each test publishes tagged events,
    #    then waits for all N_PUBLISHERS to have contributed --

    _seen_threads: ClassVar[set] = set()
    _thread_lock = threading.Lock()

    @pytest.mark.parametrize("worker", range(_N_PUBLISHERS))
    def test_publish_and_observe_aggregate(self, worker):
        """Each worker publishes its own events, then waits to see all workers' events.

        This proves cross-test visibility: events from parallel threads
        are visible to every other thread via the shared bus.
        """
        self._publish_own_events(f"worker_{worker}")

        with self._thread_lock:
            self._seen_threads.add(threading.current_thread().name)

        all_events = EventBus.wait_for(self._N_PUBLISHERS * 2, topic="work")
        sources = {e["payload"]["source"] for e in all_events}
        assert len(sources) == self._N_PUBLISHERS
