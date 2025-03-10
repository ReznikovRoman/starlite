from typing import Any, Dict, Optional

from pydantic import validator
from pydantic_openapi_schema.v3_1_0 import Header

__all__ = ("ResponseHeader",)


class ResponseHeader(Header):
    """Container type for a response header."""

    name: str  # type: ignore[assignment]
    """Header name"""
    documentation_only: bool = False
    """Defines the ResponseHeader instance as for OpenAPI documentation purpose only."""
    value: Optional[str] = None
    """Value to set for the response header."""

    @validator("value", always=True)
    def validate_value(cls, value: Any, values: Dict[str, Any]) -> Any:
        """Ensure that either value is set or the instance is for documentation_only."""
        if values.get("documentation_only") or value is not None:
            return value
        raise ValueError("value must be set if documentation_only is false")

    def __hash__(self) -> int:
        return hash(self.name)
