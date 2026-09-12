from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.services.storage.base import StorageService
from app.services.storage.local_adapter import LocalStorageService

log = get_logger(__name__)


@lru_cache
def get_storage_service() -> StorageService:
    if settings.STORAGE_PROVIDER == "s3":
        try:
            from app.services.storage.s3_adapter import S3StorageService

            return S3StorageService()
        except Exception as exc:  # noqa: BLE001
            log.error("S3 unavailable, using local disk", extra={"extra": {"error": str(exc)[:200]}})
    return LocalStorageService()
