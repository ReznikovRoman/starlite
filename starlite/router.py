from __future__ import annotations

from collections import defaultdict
from copy import copy
from typing import TYPE_CHECKING, Any, DefaultDict, Mapping, Sequence, cast

from starlite._layers.utils import narrow_response_cookies, narrow_response_headers
from starlite.controller import Controller
from starlite.exceptions import ImproperlyConfiguredException
from starlite.handlers.asgi_handlers import ASGIRouteHandler
from starlite.handlers.base import BaseRouteHandler
from starlite.handlers.http_handlers import HTTPRouteHandler
from starlite.handlers.websocket_handlers import WebsocketRouteHandler
from starlite.routes import ASGIRoute, HTTPRoute, WebSocketRoute
from starlite.utils import find_index, is_class_and_subclass, join_paths, normalize_path, unique
from starlite.utils.sync import AsyncCallable

__all__ = ("Router",)


if TYPE_CHECKING:
    from pydantic_openapi_schema.v3_1_0 import SecurityRequirement

    from starlite.datastructures import CacheControlHeader, ETag
    from starlite.di import Provide
    from starlite.routes import BaseRoute
    from starlite.types import (
        AfterRequestHookHandler,
        AfterResponseHookHandler,
        BeforeRequestHookHandler,
        ControllerRouterHandler,
        ExceptionHandlersMap,
        Guard,
        Middleware,
        ParametersMap,
        ResponseCookies,
        ResponseType,
        RouteHandlerMapItem,
        RouteHandlerType,
        TypeEncodersMap,
    )
    from starlite.types.composite_types import ResponseHeaders


class Router:
    """The Starlite Router class.

    A Router instance is used to group controller, routers and route handler functions under a shared path fragment
    """

    __slots__ = (
        "after_request",
        "after_response",
        "before_request",
        "cache_control",
        "dependencies",
        "etag",
        "exception_handlers",
        "guards",
        "middleware",
        "opt",
        "owner",
        "parameters",
        "path",
        "registered_route_handler_ids",
        "response_class",
        "response_cookies",
        "response_headers",
        "routes",
        "security",
        "tags",
        "type_encoders",
    )

    def __init__(
        self,
        path: str,
        *,
        after_request: AfterRequestHookHandler | None = None,
        after_response: AfterResponseHookHandler | None = None,
        before_request: BeforeRequestHookHandler | None = None,
        cache_control: CacheControlHeader | None = None,
        dependencies: Mapping[str, Provide] | None = None,
        etag: ETag | None = None,
        exception_handlers: ExceptionHandlersMap | None = None,
        guards: Sequence[Guard] | None = None,
        middleware: Sequence[Middleware] | None = None,
        opt: Mapping[str, Any] | None = None,
        parameters: ParametersMap | None = None,
        response_class: ResponseType | None = None,
        response_cookies: ResponseCookies | None = None,
        response_headers: ResponseHeaders | None = None,
        route_handlers: Sequence[ControllerRouterHandler],
        security: Sequence[SecurityRequirement] | None = None,
        tags: Sequence[str] | None = None,
        type_encoders: TypeEncodersMap | None = None,
    ) -> None:
        """Initialize a ``Router``.

        Args:
            after_request: A sync or async function executed before a :class:`Request <.connection.Request>` is passed
                to any route handler. If this function returns a value, the request will not reach the route handler,
                and instead this value will be used.
            after_response: A sync or async function called after the response has been awaited. It receives the
                :class:`Request <.connection.Request>` object and should not return any values.
            before_request: A sync or async function called immediately before calling the route handler. Receives
                the :class:`starlite.connection.Request` instance and any non-``None`` return value is used for the
                response, bypassing the route handler.
            cache_control: A ``cache-control`` header of type
                :class:`CacheControlHeader <.datastructures.CacheControlHeader>` to add to route handlers of
                this router. Can be overridden by route handlers.
            dependencies: A string keyed mapping of dependency :class:`Provide <.di.Provide>` instances.
            etag: An ``etag`` header of type :class:`ETag <.datastructures.ETag>` to add to route handlers of this app.
            exception_handlers: A mapping of status codes and/or exception types to handler functions.
            guards: A sequence of :data:`Guard <.types.Guard>` callables.
            middleware: A sequence of :data:`Middleware <.types.Middleware>`.
            opt: A string keyed mapping of arbitrary values that can be accessed in :data:`Guards <.types.Guard>` or
                wherever you have access to :class:`Request <.connection.Request>` or
                :data:`ASGI Scope <.types.Scope>`.
            parameters: A mapping of :func:`Parameter <.params.Parameter>` definitions available to all application
                paths.
            path: A path fragment that is prefixed to all route handlers, controllers and other routers associated
                with the router instance.
            response_class: A custom subclass of :class:`Response <.response.Response>` to be used as the default for
                all route handlers, controllers and other routers associated with the router instance.
            response_cookies: A sequence of :class:`Cookie <.datastructures.Cookie>` instances.
            response_headers: A string keyed mapping of :class:`ResponseHeader <.datastructures.ResponseHeader>`
                instances.
            route_handlers: A required sequence of route handlers, which can include instances of
                :class:`Router <.router.Router>`, subclasses of :class:`Controller <.controller.Controller>` or any
                function decorated by the route handler decorators.
            security: A sequence of dicts that will be added to the schema of all route handlers in the application.
                See :data:`SecurityRequirement <pydantic_openapi_schema.v3_1_0.security_requirement.SecurityRequirement>`
                for details.
            tags: A sequence of string tags that will be appended to the schema of all route handlers under the
                application.
            type_encoders: A mapping of types to callables that transform them into types supported for serialization.
        """

        self.after_request = AsyncCallable(after_request) if after_request else None  # type: ignore[arg-type]
        self.after_response = AsyncCallable(after_response) if after_response else None
        self.before_request = AsyncCallable(before_request) if before_request else None
        self.cache_control = cache_control
        self.etag = etag
        self.dependencies = dict(dependencies or {})
        self.exception_handlers = dict(exception_handlers or {})
        self.guards = list(guards or [])
        self.middleware = list(middleware or [])
        self.opt = dict(opt or {})
        self.owner: Router | None = None
        self.parameters = dict(parameters or {})
        self.path = normalize_path(path)
        self.response_class = response_class
        self.response_cookies = narrow_response_cookies(response_cookies)
        self.response_headers = narrow_response_headers(response_headers)
        self.routes: list[HTTPRoute | ASGIRoute | WebSocketRoute] = []
        self.security = list(security or [])
        self.tags = list(tags or [])
        self.registered_route_handler_ids: set[int] = set()
        self.type_encoders = dict(type_encoders) if type_encoders is not None else None

        for route_handler in route_handlers or []:
            self.register(value=route_handler)

    def register(self, value: ControllerRouterHandler) -> list[BaseRoute]:
        """Register a Controller, Route instance or RouteHandler on the router.

        Args:
            value: a subclass or instance of Controller, an instance of :class:`Router` or a function/method that has
                been decorated by any of the routing decorators, e.g. :class:`get <.handlers.get>`,
                :class:`post <.handlers.post>`.

        Returns:
            Collection of handlers added to the router.
        """
        validated_value = self._validate_registration_value(value)

        routes: list[BaseRoute] = []

        for route_path, handlers_map in self.get_route_handler_map(value=validated_value).items():
            path = join_paths([self.path, route_path])
            if http_handlers := unique(
                [handler for handler in handlers_map.values() if isinstance(handler, HTTPRouteHandler)]
            ):
                if existing_handlers := unique(
                    [
                        handler
                        for handler in self.route_handler_method_map.get(path, {}).values()
                        if isinstance(handler, HTTPRouteHandler)
                    ]
                ):
                    http_handlers.extend(existing_handlers)
                    existing_route_index = find_index(self.routes, lambda x: x.path == path)  # noqa: B023

                    if existing_route_index == -1:  # pragma: no cover
                        raise ImproperlyConfiguredException("unable to find_index existing route index")

                    route: WebSocketRoute | ASGIRoute | HTTPRoute = HTTPRoute(
                        path=path,
                        route_handlers=http_handlers,
                    )
                    self.routes[existing_route_index] = route
                else:
                    route = HTTPRoute(path=path, route_handlers=http_handlers)
                    self.routes.append(route)
                routes.append(route)

            if websocket_handler := handlers_map.get("websocket"):
                route = WebSocketRoute(path=path, route_handler=cast("WebsocketRouteHandler", websocket_handler))
                self.routes.append(route)
                routes.append(route)

            if asgi_handler := handlers_map.get("asgi"):
                route = ASGIRoute(path=path, route_handler=cast("ASGIRouteHandler", asgi_handler))
                self.routes.append(route)
                routes.append(route)

        return routes

    @property
    def route_handler_method_map(self) -> dict[str, RouteHandlerMapItem]:
        """Map route paths to :class:`RouteHandlerMapItem <starlite.types.internal_typ es.RouteHandlerMapItem>`

        Returns:
             A dictionary mapping paths to route handlers
        """
        route_map: dict[str, RouteHandlerMapItem] = defaultdict(dict)
        for route in self.routes:
            if isinstance(route, HTTPRoute):
                for route_handler in route.route_handlers:
                    for method in route_handler.http_methods:
                        route_map[route.path][method] = route_handler
            else:
                route_map[route.path][
                    "websocket" if isinstance(route, WebSocketRoute) else "asgi"
                ] = route.route_handler
        return route_map

    @classmethod
    def get_route_handler_map(
        cls,
        value: Controller | RouteHandlerType | Router,
    ) -> dict[str, RouteHandlerMapItem]:
        """Map route handlers to HTTP methods."""
        if isinstance(value, Router):
            return value.route_handler_method_map

        if isinstance(value, (HTTPRouteHandler, ASGIRouteHandler, WebsocketRouteHandler)):
            copied_value = copy(value)
            if isinstance(value, HTTPRouteHandler):
                return {path: {http_method: copied_value for http_method in value.http_methods} for path in value.paths}

            return {
                path: {"websocket" if isinstance(value, WebsocketRouteHandler) else "asgi": copied_value}
                for path in value.paths
            }

        handlers_map: DefaultDict[str, RouteHandlerMapItem] = defaultdict(dict)
        for route_handler in value.get_route_handlers():
            for handler_path in route_handler.paths:
                path = join_paths([value.path, handler_path]) if handler_path else value.path
                if isinstance(route_handler, HTTPRouteHandler):
                    for http_method in route_handler.http_methods:
                        handlers_map[path][http_method] = route_handler
                else:
                    handlers_map[path][
                        "websocket" if isinstance(route_handler, WebsocketRouteHandler) else "asgi"
                    ] = cast("WebsocketRouteHandler | ASGIRouteHandler", route_handler)

        return handlers_map

    def _validate_registration_value(self, value: ControllerRouterHandler) -> Controller | RouteHandlerType | Router:
        """Ensure values passed to the register method are supported."""
        if is_class_and_subclass(value, Controller):
            return value(owner=self)

        if isinstance(value, Router):
            if value.owner:
                raise ImproperlyConfiguredException(f"Router with path {value.path} has already been registered")
            if value is self:
                raise ImproperlyConfiguredException("Cannot register a router on itself")

            value.owner = self
            return value

        if isinstance(value, BaseRouteHandler):
            value.owner = self
            return value

        raise ImproperlyConfiguredException(
            "Unsupported value passed to `Router.register`. "
            "If you passed in a function or method, "
            "make sure to decorate it first with one of the routing decorators"
        )
