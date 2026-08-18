"""Unit tests for the event bus.

These pin the bus's dispatch contract: handlers registered via subscribe()
receive every emitted event, in the order they subscribed.
"""

from planar_bridge.events import EventBus, RunFinished, RunStarted


def test_emit_delivers_the_event_to_a_subscriber() -> None:
    """A subscribed handler receives the exact event that was emitted."""
    received: list[object] = []
    bus = EventBus()
    bus.subscribe(received.append)

    event = RunStarted()
    bus.emit(event)

    assert received == [event]


def test_emit_fans_out_to_all_subscribers_in_order() -> None:
    """Every subscriber is invoked, in the order they subscribed."""
    calls: list[tuple[str, object]] = []
    bus = EventBus()
    bus.subscribe(lambda event: calls.append(("first", event)))
    bus.subscribe(lambda event: calls.append(("second", event)))

    event = RunFinished(low_resolution_set_codes=())
    bus.emit(event)

    assert calls == [("first", event), ("second", event)]


def test_emit_without_subscribers_does_not_raise() -> None:
    """Emitting with no subscribers is a silent no-op."""
    EventBus().emit(RunStarted())
