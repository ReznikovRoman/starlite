from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, Literal, cast, overload

from starlite.connection.base import (
    ASGIConnection,
    AuthT,
    StateT,
    UserT,
    empty_receive,
    empty_send,
)
from starlite.datastructures.headers import Headers
from starlite.exceptions import WebSocketDisconnect, WebSocketException
from starlite.serialization import decode_json, default_serializer, encode_json
from starlite.status_codes import WS_1000_NORMAL_CLOSURE

__all__ = ("WebSocket",)


if TYPE_CHECKING:
    from starlite.handlers.websocket_handlers import WebsocketRouteHandler  # noqa: F401
    from starlite.types import Message, Serializer, WebSocketScope
    from starlite.types.asgi_types import WebSocketDisconnectEvent
    from starlite.types.asgi_types import WebSocketReceiveEvent
    from starlite.types.asgi_types import (
        Receive,
        ReceiveMessage,
        Scope,
        Send,
        WebSocketAcceptEvent,
        WebSocketCloseEvent,
        WebSocketSendEvent,
    )

DISCONNECT_MESSAGE = "connection is disconnected"


class WebSocket(Generic[UserT, AuthT, StateT], ASGIConnection["WebsocketRouteHandler", UserT, AuthT, StateT]):
    """The Starlite WebSocket class."""

    __slots__ = ("connection_state",)

    scope: WebSocketScope
    """The ASGI scope attached to the connection."""
    receive: Receive
    """The ASGI receive function."""
    send: Send
    """The ASGI send function."""

    def __init__(self, scope: Scope, receive: Receive = empty_receive, send: Send = empty_send) -> None:
        """Initialize ``WebSocket``.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive function.
            send: The ASGI send function.
        """
        super().__init__(scope, self.receive_wrapper(receive), self.send_wrapper(send))
        self.connection_state: Literal["init", "connect", "receive", "disconnect"] = "init"

    def receive_wrapper(self, receive: Receive) -> Receive:
        """Wrap ``receive`` to set 'self.connection_state' and validate events.

        Args:
            receive: The ASGI receive function.

        Returns:
            An ASGI receive function.
        """

        async def wrapped_receive() -> "ReceiveMessage":
            if self.connection_state == "disconnect":
                raise WebSocketException(detail=DISCONNECT_MESSAGE)
            message = await receive()
            if message["type"] == "websocket.connect":
                self.connection_state = "connect"
            elif message["type"] == "websocket.receive":
                self.connection_state = "receive"
            else:
                self.connection_state = "disconnect"
            return message

        return wrapped_receive

    def send_wrapper(self, send: Send) -> Send:
        """Wrap ``send`` to ensure that state is not disconnected.

        Args:
            send: The ASGI send function.

        Returns:
            An ASGI send function.
        """

        async def wrapped_send(message: "Message") -> None:
            if self.connection_state == "disconnect":
                raise WebSocketDisconnect(detail=DISCONNECT_MESSAGE)  # pragma: no cover
            await send(message)

        return wrapped_send

    async def accept(
        self,
        subprotocols: str | None = None,
        headers: Headers | dict[str, Any] | list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        """Accept the incoming connection. This method should be called before receiving data.

        Args:
            subprotocols: Websocket sub-protocol to use.
            headers: Headers to set on the data sent.

        Returns:
            None
        """
        if self.connection_state == "init":
            await self.receive()
            _headers: list[tuple[bytes, bytes]] = headers if isinstance(headers, list) else []

            if isinstance(headers, dict):
                _headers = Headers(headers=headers).to_header_list()

            if isinstance(headers, Headers):
                _headers = headers.to_header_list()

            event: WebSocketAcceptEvent = {
                "type": "websocket.accept",
                "subprotocol": subprotocols,
                "headers": _headers,
            }
            await self.send(event)

    async def close(self, code: int = WS_1000_NORMAL_CLOSURE, reason: str | None = None) -> None:
        """Send an 'websocket.close' event.

        Args:
            code: Status code.
            reason: Reason for closing the connection

        Returns:
            None
        """
        event: WebSocketCloseEvent = {"type": "websocket.close", "code": code, "reason": reason or ""}
        await self.send(event)

    @overload
    async def receive_data(self, mode: Literal["text"]) -> str:
        ...

    @overload
    async def receive_data(self, mode: Literal["binary"]) -> bytes:
        ...

    async def receive_data(self, mode: Literal["binary", "text"]) -> str | bytes:
        """Receive an 'websocket.receive' event and returns the data stored on it.

        Args:
            mode: The respective event key to use.

        Returns:
            The event's data.
        """
        if self.connection_state == "init":
            await self.accept()
        event = cast("WebSocketReceiveEvent | WebSocketDisconnectEvent", await self.receive())
        if event["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(detail="disconnect event", code=event["code"])
        if self.connection_state == "disconnect":
            raise WebSocketDisconnect(detail=DISCONNECT_MESSAGE)  # pragma: no cover
        return event.get("text") or "" if mode == "text" else event.get("bytes") or b""

    async def receive_text(self) -> str:
        """Receive data as text.

        Returns:
            A string.
        """
        return await self.receive_data(mode="text")

    async def receive_bytes(self) -> bytes:
        """Receive data as bytes.

        Returns:
            A byte-string.
        """
        return await self.receive_data(mode="binary")

    async def receive_json(
        self,
        mode: Literal["text", "binary"] = "text",
    ) -> Any:
        """Receive data and loads it into JSON using orson.

        Args:
            mode: Either ``text`` or ``binary``.

        Returns:
            An arbitrary value
        """
        data = await self.receive_data(mode=mode)
        return decode_json(data)

    async def send_data(
        self, data: str | bytes, mode: Literal["text", "binary"] = "text", encoding: str = "utf-8"
    ) -> None:
        """Send a 'websocket.send' event.

        Args:
            data: Data to send.
            mode: The respective event key to use.
            encoding: Encoding to use when converting bytes / str.

        Returns:
            None
        """
        if self.connection_state == "init":  # pragma: no cover
            await self.accept()
        event: WebSocketSendEvent = {"type": "websocket.send", "bytes": None, "text": None}
        if mode == "binary":
            event["bytes"] = data if isinstance(data, bytes) else data.encode(encoding)
        else:
            event["text"] = data if isinstance(data, str) else data.decode(encoding)
        await self.send(event)

    @overload
    async def send_text(self, data: bytes, encoding: str = "utf-8") -> None:
        ...

    @overload
    async def send_text(self, data: str) -> None:
        ...

    async def send_text(self, data: str | bytes, encoding: str = "utf-8") -> None:
        """Send data using the ``text`` key of the send event.

        Args:
            data: Data to send
            encoding: Encoding to use for binary data.

        Returns:
            None
        """
        await self.send_data(data=data, encoding=encoding)

    @overload
    async def send_bytes(self, data: bytes) -> None:
        ...

    @overload
    async def send_bytes(self, data: str, encoding: str = "utf-8") -> None:
        ...

    async def send_bytes(self, data: str | bytes, encoding: str = "utf-8") -> None:
        """Send data using the ``bytes`` key of the send event.

        Args:
            data: Data to send
            encoding: Encoding to use for binary data.

        Returns:
            None
        """
        await self.send_data(data=data, mode="binary", encoding=encoding)

    async def send_json(
        self,
        data: Any,
        mode: Literal["text", "binary"] = "text",
        encoding: str = "utf-8",
        serializer: "Serializer" = default_serializer,
    ) -> None:
        """Send data as JSON.

        Args:
            data: A value to serialize.
            mode: Either ``text`` or ``binary``.
            encoding: Encoding to use for binary data.
            serializer: A serializer function.

        Returns:
            None
        """
        await self.send_data(
            data=encode_json(data, serializer),
            mode=mode,
            encoding=encoding,
        )
