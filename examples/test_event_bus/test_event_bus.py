"""Shared in-memory test double — concurrent access to a shared event bus.

This pattern is impossible with pytest-xdist: each subprocess has its own
memory space, so a plain Python object can't collect events from multiple
workers. You'd need Redis, a socket server, or a temp file to coordinate.

With pytest-threadpool, all tests share the same process. A class-scoped
fixture creates one EventBus instance, shared by all parallel methods —
proper lifecycle management with no global mutable state.

Patterns demonstrated:
- Class-scoped fixture providing a shared test double to parallel workers
- Concurrent access to a shared in-memory object from parallel threads
- Subscriber callbacks firing synchronously during publish
- Aggregate cross-test visibility via wait_for
"""

import threading

import pytest

from examples.test_event_bus.event_bus import EventBus

_N_PUBLISHERS = 4


@pytest.fixture(scope="class")
def bus():
    return EventBus()


@pytest.mark.parallelizable("children")
class TestEventBus:
    """All tests run in parallel, sharing one bus via a class-scoped fixture."""

    def _publish_own_events(self, bus: EventBus, name: str) -> None:
        """Each test publishes its own uniquely-tagged events."""
        bus.publish("work", {"source": name, "step": "start"})
        bus.publish("work", {"source": name, "step": "done"})

    def test_publish_and_verify_signup(self, bus):
        """Publish signup events and verify only own events are correct."""
        bus.publish("user.created", {"user_id": "u1"})
        bus.publish("email.queued", {"to": "a@test.com", "template": "welcome"})

        own_emails = [e for e in bus.events("email.queued") if e["payload"]["to"] == "a@test.com"]
        assert len(own_emails) == 1
        assert own_emails[0]["payload"]["template"] == "welcome"

    def test_publish_and_verify_purchase(self, bus):
        """Publish purchase events and verify own events landed."""
        bus.publish("order.created", {"order_id": "o1", "user_id": "u2"})
        bus.publish("payment.charged", {"order_id": "o1", "amount": 99})

        own = [e for e in bus.events("payment.charged") if e["payload"]["order_id"] == "o1"]
        assert len(own) == 1
        assert own[0]["payload"]["amount"] == 99

    def test_subscriber_callback_fires_on_publish(self):
        """Subscribe, publish, verify callback fired — all within one test.

        Uses a dedicated EventBus instance so the subscriber doesn't leak
        into the shared class-scoped bus.
        """
        local_bus = EventBus()
        received: list[dict] = []

        def on_event(event):
            received.append(event)

        local_bus.subscribe("audit.log", on_event)
        local_bus.publish("audit.log", {"action": "login", "user": "alice"})
        local_bus.publish("audit.log", {"action": "logout", "user": "alice"})

        actions = [e["payload"]["action"] for e in received]
        assert actions == ["login", "logout"]

    def test_wait_for_own_events(self, bus):
        """Publish from a background thread, wait_for in the test thread."""
        topic = "async.work"

        def background_publisher():
            bus.publish(topic, {"step": 1})
            bus.publish(topic, {"step": 2})

        t = threading.Thread(target=background_publisher)
        t.start()

        events = bus.wait_for(2, topic=topic)
        t.join(timeout=10)

        steps = [e["payload"]["step"] for e in events]
        assert 1 in steps
        assert 2 in steps

    # -- aggregate visibility: each parametrized worker publishes tagged events,
    #    then waits for all N_PUBLISHERS to have contributed --

    @pytest.mark.parametrize("worker", range(_N_PUBLISHERS))
    def test_publish_and_observe_aggregate(self, bus, worker):
        """Each worker publishes its own events, then waits to see all workers' events.

        This proves cross-test visibility: events from parallel threads
        are visible to every other thread via the shared bus.
        """
        self._publish_own_events(bus, f"worker_{worker}")

        all_events = bus.wait_for(_N_PUBLISHERS * 2, topic="work")
        sources = {e["payload"]["source"] for e in all_events}
        assert len(sources) == _N_PUBLISHERS
