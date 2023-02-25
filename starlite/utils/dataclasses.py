import dataclasses
from typing import Any, Iterable


class DataclassSerializerMixin:
    """Mixin providing common methods for serializing dataclasses to dicts."""

    def dict(self, exclude_none: bool = False, exclude: set[str] | None = None) -> dict[str, Any]:
        """Serialize dataclass instance to dict.

        Args:
            exclude_none: whether fields which are equal to ``None`` should be excluded from the returned dictionary.
            exclude: fields to exclude from the returned dictionary.

        Returns:
            A dataclass converted to dict.
        """
        return dict(self._iter(exclude_none=exclude_none, exclude=exclude))

    def _iter(self, *, exclude_none: bool = False, exclude: set[str] | None = None) -> Iterable[tuple[str, Any]]:
        if exclude is None:
            exclude = set()
        for key, value in dataclasses.asdict(self).items():  # pyright: ignore
            if key in exclude:
                continue
            if exclude_none and value is None:
                continue
            yield key, value
