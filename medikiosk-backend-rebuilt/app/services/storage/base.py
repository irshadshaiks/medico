"""
Storage seam.

Uploaded documents are patient records, so nothing here returns a public URL.
`presigned_url` is short-lived and only ever handed to an already-authorised
caller; `open` streams through the API for the local adapter.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(slots=True)
class StoredObject:
    key: str
    size_bytes: int
    mime_type: str
    sha256: str


class StorageService(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    async def put(self, key: str, data: bytes, mime_type: str) -> StoredObject: ...

    @abc.abstractmethod
    async def get(self, key: str) -> bytes: ...

    @abc.abstractmethod
    async def delete(self, key: str) -> None: ...

    @abc.abstractmethod
    async def presigned_url(self, key: str, ttl_seconds: int | None = None) -> str | None:
        """None means the adapter has no direct-access URL and must be proxied."""
