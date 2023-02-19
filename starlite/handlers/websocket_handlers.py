from __future__ import annotations

from inspect import Signature
from typing import TYPE_CHECKING, Any

from starlite.exceptions import ImproperlyConfiguredException
from starlite.handlers.base import BaseRouteHandler
from starlite.utils import Ref, is_async_callable

if TYPE_CHECKING:
    from starlite.types import MaybePartial  # nopycln: import # noqa: F401
    from starlite.types import (
        AsyncAnyCallable,
        Dependencies,
        ExceptionHandler,
        Guard,
        Middleware,
    )


class WebsocketRouteHandler(BaseRouteHandler["WebsocketRouteHandler"]):
    """Websocket route handler decorator.

    Use this decorator to decorate websocket handler functions.
    """

    def __init__(
        self,
        path: str | None | list[str] | None = None,
        *,
        dependencies: Dependencies | None = None,
        exception_handlers: dict[int | type[Exception], ExceptionHandler] | None = None,
        guards: list[Guard] | None = None,
        middleware: list[Middleware] | None = None,
        name: str | None = None,
        opt: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize ``WebsocketRouteHandler``

        Args:
            path: A path fragment for the route handler function or a sequence of path fragments. If not given defaults to '/'
            dependencies: A string keyed mapping of dependency :class:`Provider <starlite.datastructures.Provide>` instances.
            exception_handlers: A mapping of status codes and/or exception types to handler functions.
            guards: A sequence of :class:`Guard <starlite.types.Guard>` callables.
            middleware: A sequence of :class:`Middleware <starlite.types.Middleware>`.
            name: A string identifying the route handler.
            opt: A string keyed mapping of arbitrary values that can be accessed in :class:`Guards <starlite.types.Guard>` or
                wherever you have access to :class:`Request <starlite.connection.request.Request>` or :class:`ASGI Scope <starlite.types.Scope>`.
            type_encoders: A mapping of types to callables that transform them into types supported for serialization.
            **kwargs: Any additional kwarg - will be set in the opt dictionary.
        """
        super().__init__(
            path,
            dependencies=dependencies,
            exception_handlers=exception_handlers,
            guards=guards,
            middleware=middleware,
            name=name,
            opt=opt,
            **kwargs,
        )

    def __call__(self, fn: AsyncAnyCallable) -> WebsocketRouteHandler:
        """Replace a function with itself."""
        self.fn = Ref["MaybePartial[AsyncAnyCallable]"](fn)
        self.signature = Signature.from_callable(fn)
        self._validate_handler_function()
        return self

    def _validate_handler_function(self) -> None:
        """Validate the route handler function once it's set by inspecting its return annotations."""
        super()._validate_handler_function()

        if self.signature.return_annotation not in {None, "None"}:
            raise ImproperlyConfiguredException("Websocket handler functions should return 'None'")
        if "socket" not in self.signature.parameters:
            raise ImproperlyConfiguredException("Websocket handlers must set a 'socket' kwarg")
        for param in ("request", "body", "data"):
            if param in self.signature.parameters:
                raise ImproperlyConfiguredException(f"The {param} kwarg is not supported with websocket handlers")
        if not is_async_callable(self.fn.value):
            raise ImproperlyConfiguredException("Functions decorated with 'websocket' must be async functions")


websocket = WebsocketRouteHandler
