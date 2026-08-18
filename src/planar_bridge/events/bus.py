"""A minimal synchronous event bus.

Publishers call :meth:`EventBus.emit`; every handler registered through
:meth:`EventBus.subscribe` receives each event in subscription order. The bus
is deliberately synchronous: the download pipeline is synchronous today and a
single in-process reporter needs nothing more. The publisher-facing contract
(emit returns nothing and promises only "handlers see events in emit order")
is chosen so an async reporter can be added later, by handing events to an
asyncio queue from inside a handler, without touching any publisher.
"""

from collections.abc import Callable

from .types import Event

EventHandler = Callable[[Event], None]


class EventBus:
    """Dispatches emitted events to every registered handler."""

    def __init__(self) -> None:

        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        """Register a handler to receive every subsequently emitted event.

        Args:
            handler (EventHandler): A callable invoked with each emitted event.
        """
        self._handlers.append(handler)

    def emit(self, event: Event) -> None:
        """Deliver one event to every registered handler, in order.

        Args:
            event (Event): The event to deliver to all handlers.
        """
        for handler in self._handlers:
            handler(event)
