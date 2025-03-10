from __future__ import annotations


from typing import Optional

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from msgspec import Struct
from msgspec.msgpack import decode as msgpack_decode
from msgspec.msgpack import encode as msgpack_encode

__all__ = ("Storage", "StorageObject")


class Storage(ABC):  # pragma: no cover
    """Thread and process safe asynchronous key/value store."""

    @abstractmethod
    async def set(self, key: str, value: str | bytes, expires_in: int | timedelta | None = None) -> None:
        """Set a value.

        Args:
            key: Key to associate the value with
            value: Value to store
            expires_in: Time in seconds before the key is considered expired

        Returns:
            ``None``
        """
        raise NotImplementedError

    @abstractmethod
    async def get(self, key: str, renew_for: int | timedelta | None = None) -> bytes | None:
        """Get a value.

        Args:
            key: Key associated with the value
            renew_for: If given and the value had an initial expiry time set, renew the
                expiry time for ``renew_for`` seconds. If the value has not been set
                with an expiry time this is a no-op

        Returns:
            The value associated with ``key`` if it exists and is not expired, else
            ``None``
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a value.

        If no such key exists, this is a no-op.

        Args:
            key: Key of the value to delete
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_all(self) -> None:
        """Delete all stored values."""
        raise NotImplementedError

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a given ``key`` exists."""
        raise NotImplementedError

    @abstractmethod
    async def expires_in(self, key: str) -> int | None:
        """Get the time in seconds ``key`` expires in. If no such ``key`` exists or no
        expiry time was set, return ``None``.
        """
        raise NotImplementedError


class StorageObject(Struct):
    """:class:`msgspec.Struct` to store serialized data alongside with their expiry time."""

    expires_at: Optional[datetime]  # noqa: UP007
    data: bytes

    @classmethod
    def new(cls, data: bytes, expires_in: int | timedelta | None) -> StorageObject:
        """Construct a new :class:`StorageObject` instance."""
        if expires_in is not None and not isinstance(expires_in, timedelta):
            expires_in = timedelta(seconds=expires_in)
        return cls(
            data=data,
            expires_at=(datetime.now(tz=timezone.utc) + expires_in) if expires_in else None,
        )

    @property
    def expired(self) -> bool:
        """Return if the :class:`StorageObject` is expired"""
        return self.expires_at is not None and datetime.now(tz=timezone.utc) >= self.expires_at

    @property
    def expires_in(self) -> int:
        """Return the expiry time of this ``StorageObject`` in seconds. If no expiry time
        was set, return ``-1``.
        """
        if self.expires_at:
            return (self.expires_at - datetime.now(tz=timezone.utc)).seconds
        return -1

    def to_bytes(self) -> bytes:
        """Encode the instance to bytes"""
        return msgpack_encode(self)

    @classmethod
    def from_bytes(cls, raw: bytes) -> StorageObject:
        """Load a previously encoded with :meth:`StorageObject.to_bytes`"""
        return msgpack_decode(raw, type=cls)
