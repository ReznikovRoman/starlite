from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlite.exceptions import ImproperlyConfiguredException
from starlite.utils import AsyncCallable

__all__ = ("EventListener",)


if TYPE_CHECKING:
    from starlite.types import AnyCallable


class EventListener:
    """Decorator for event listeners"""

    __slots__ = ("event_ids", "fn", "listener_id")

    fn: AsyncCallable[Any, Any]

    def __init__(self, *event_ids: str):
        """Create a decorator for event handlers.

        Args:
            *event_ids: The id of the event to listen to or a list of
                event ids to listen to.
        """
        self.event_ids: list[str] = list(event_ids)

    def __call__(self, fn: AnyCallable) -> EventListener:
        """Decorate a callable by wrapping it inside an instance of EventListener.

        Args:
            fn: Callable to decorate.

        Returns:
            An instance of EventListener
        """
        if not callable(fn):
            raise ImproperlyConfiguredException("EventListener instance should be called as a decorator on a callable")

        self.fn = AsyncCallable(fn)

        return self


listener = EventListener
