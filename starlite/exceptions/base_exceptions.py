from typing import Any

__all__ = ("MissingDependencyException", "SerializationException", "StarliteException")


class StarliteException(Exception):
    """Base exception class from which all Starlite exceptions inherit."""

    detail: str

    def __init__(self, *args: Any, detail: str = "") -> None:
        """Initialize ``StarliteException``.

        Args:
            *args: args are converted to :class:`str` before passing to :class:`Exception`
            detail: detail of the exception.
        """
        self.detail = detail
        super().__init__(*(str(arg) for arg in args if arg), detail)

    def __repr__(self) -> str:
        if self.detail:
            return f"{self.__class__.__name__} - {self.detail}"
        return self.__class__.__name__

    def __str__(self) -> str:
        return " ".join(self.args).strip()


class MissingDependencyException(StarliteException):
    """Missing optional dependency.

    This exception is raised only when a module depends on a dependency that has not been installed.
    """


class SerializationException(StarliteException):
    """Encoding or decoding of an object failed."""
