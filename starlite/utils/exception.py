from __future__ import annotations

from dataclasses import asdict, dataclass, field
from inspect import getmro
from typing import TYPE_CHECKING, Any, cast

from starlite.status_codes import HTTP_500_INTERNAL_SERVER_ERROR

if TYPE_CHECKING:
    from typing import Type

    from starlite.response import Response
    from starlite.types import ExceptionHandler, ExceptionHandlersMap


def get_exception_handler(exception_handlers: ExceptionHandlersMap, exc: Exception) -> ExceptionHandler | None:
    """Given a dictionary that maps exceptions and status codes to handler functions, and an exception, returns the
    appropriate handler if existing.

    Status codes are given preference over exception type.

    If no status code match exists, each class in the MRO of the exception type is checked and
    the first matching handler is returned.

    Finally, if a ``500`` handler is registered, it will be returned for any exception that isn't a
    subclass of :class:`HTTPException <starlite.exceptions.HTTPException>`.

    Args:
        exception_handlers: Mapping of status codes and exception types to handlers.
        exc: Exception Instance to be resolved to a handler.

    Returns:
        Optional exception handler callable.
    """
    if not exception_handlers:
        return None
    status_code: int | None = getattr(exc, "status_code", None)
    if status_code and (exception_handler := exception_handlers.get(status_code)):
        return exception_handler
    for cls in getmro(type(exc)):
        if cls in exception_handlers:
            return exception_handlers[cast("Type[Exception]", cls)]
    if not hasattr(exc, "status_code") and HTTP_500_INTERNAL_SERVER_ERROR in exception_handlers:
        return exception_handlers[HTTP_500_INTERNAL_SERVER_ERROR]
    return None


@dataclass
class ExceptionResponseContent:
    """Represent the contents of an exception-response."""

    status_code: int
    """Exception status code."""
    detail: str
    """Exception details or message."""
    headers: dict[str, str] | None = field(default=None)
    """Headers to attach to the response."""
    extra: dict[str, Any] | list[Any] | None = field(default=None)
    """An extra mapping to attach to the exception."""

    def to_response(self) -> Response:
        """Create a response from the model attributes.

        Returns:
            A response instance.
        """
        from starlite.response import Response

        return Response(
            content={k: v for k, v in asdict(self).items() if k != "headers" and v is not None},
            headers=self.headers,
            status_code=self.status_code,
        )


def create_exception_response(exc: Exception) -> Response:
    """Construct a response from an exception.

    Notes:
        - For instances of :class:`HTTPException <starlite.exceptions.HTTPException>` or other exception classes that have a
          ``status_code`` attribute (e.g. Starlette exceptions), the status code is drawn from the exception, otherwise
          response status is ``HTTP_500_INTERNAL_SERVER_ERROR``.

    Args:
        exc: An exception.

    Returns:
        Response: HTTP response constructed from exception details.
    """
    content = ExceptionResponseContent(
        status_code=getattr(exc, "status_code", HTTP_500_INTERNAL_SERVER_ERROR),
        detail=getattr(exc, "detail", repr(exc)),
        headers=getattr(exc, "headers", None),
        extra=getattr(exc, "extra", None),
    )
    return content.to_response()
