from typing import Optional

import pytest

from starlite import Controller, Request, Response, Router, get
from starlite.handlers.http_handlers import HTTPRouteHandler
from starlite.testing import create_test_client
from starlite.types import BeforeRequestHookHandler


def greet() -> dict:
    return {"hello": "world"}


def sync_before_request_handler_with_return_value(request: Request) -> dict:
    assert isinstance(request, Request)
    return {"hello": "moon"}


async def async_before_request_handler_with_return_value(request: Request) -> dict:
    assert isinstance(request, Request)
    return {"hello": "moon"}


def sync_before_request_handler_without_return_value(request: Request) -> None:
    assert isinstance(request, Request)


async def async_before_request_handler_without_return_value(request: Request) -> None:
    assert isinstance(request, Request)


def sync_after_request_handler(response: Response) -> Response:
    assert isinstance(response, Response)
    response.body = response.render({"hello": "moon"})
    return response


async def async_after_request_handler(response: Response) -> Response:
    assert isinstance(response, Response)
    response.body = response.render({"hello": "moon"})
    return response


@pytest.mark.parametrize(
    "handler, expected",
    (
        (get(path="/")(greet), {"hello": "world"}),
        (get(path="/", before_request=sync_before_request_handler_with_return_value)(greet), {"hello": "moon"}),
        (get(path="/", before_request=async_before_request_handler_with_return_value)(greet), {"hello": "moon"}),
        (get(path="/", before_request=sync_before_request_handler_without_return_value)(greet), {"hello": "world"}),
        (get(path="/", before_request=async_before_request_handler_without_return_value)(greet), {"hello": "world"}),
    ),
)
def test_before_request_handler_called(handler: HTTPRouteHandler, expected: dict) -> None:
    with create_test_client(route_handlers=handler) as client:
        response = client.get("/")
        assert response.json() == expected


@pytest.mark.parametrize(
    "app_before_request_handler, router_before_request_handler, controller_before_request_handler, method_before_request_handler, expected",
    [
        [None, None, None, None, {"hello": "world"}],
        [sync_before_request_handler_with_return_value, None, None, None, {"hello": "moon"}],
        [None, sync_before_request_handler_with_return_value, None, None, {"hello": "moon"}],
        [None, None, sync_before_request_handler_with_return_value, None, {"hello": "moon"}],
        [None, None, None, sync_before_request_handler_with_return_value, {"hello": "moon"}],
        [
            sync_before_request_handler_with_return_value,
            async_before_request_handler_without_return_value,
            None,
            None,
            {"hello": "world"},
        ],
        [
            None,
            sync_before_request_handler_with_return_value,
            async_before_request_handler_without_return_value,
            None,
            {"hello": "world"},
        ],
        [
            None,
            None,
            sync_before_request_handler_with_return_value,
            async_before_request_handler_without_return_value,
            {"hello": "world"},
        ],
        [None, None, None, async_before_request_handler_without_return_value, {"hello": "world"}],
    ],
)
def test_before_request_handler_resolution(
    app_before_request_handler: Optional[BeforeRequestHookHandler],
    router_before_request_handler: Optional[BeforeRequestHookHandler],
    controller_before_request_handler: Optional[BeforeRequestHookHandler],
    method_before_request_handler: Optional[BeforeRequestHookHandler],
    expected: dict,
) -> None:
    class MyController(Controller):
        path = "/hello"

        before_request = controller_before_request_handler

        @get(before_request=method_before_request_handler)
        def hello(self) -> dict:
            return {"hello": "world"}

    router = Router(path="/greetings", route_handlers=[MyController], before_request=router_before_request_handler)

    with create_test_client(route_handlers=router, before_request=app_before_request_handler) as client:
        response = client.get("/greetings/hello")
        assert response.json() == expected
