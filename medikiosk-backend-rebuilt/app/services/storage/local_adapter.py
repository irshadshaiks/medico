"""Local disk, for development. Keys are sanitised so they cannot escape the root."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from app.core.config import settings
from app.core.errors import NotFound
from app.services.storage.base import StorageService, StoredObject


class LocalStorageService(StorageService):
    name = "local"

    def __init__(self) -> None:
        self.root = Path(settings.LOCAL_STORAGE_DIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        # Path traversal guard: a crafted key must not write outside the root.
        if not str(target).startswith(str(self.root)):
            raise ValueError("Invalid storage key.")
        return target

    async def put(self, key: str, data: bytes, mime_type: str) -> StoredObject:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return StoredObject(key=key, size_bytes=len(data), mime_type=mime_type, sha256=hashlib.sha256(data).hexdigest())

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise NotFound("That document is no longer available.")
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            await asyncio.to_thread(path.unlink)

    async def presigned_url(self, key: str, ttl_seconds: int | None = None) -> str | None:
        return None  # served through the authenticated proxy route instead
