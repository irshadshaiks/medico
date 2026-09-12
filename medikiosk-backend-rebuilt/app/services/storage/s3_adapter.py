"""
S3 adapter.

Credentials are deliberately optional: on ECS, App Runner or EC2 the task role
supplies them, and hardcoding keys into the environment there is the worse
option. Falls back to explicit keys only for local testing against S3.
"""

from __future__ import annotations

import asyncio
import hashlib

from app.core.config import settings
from app.core.errors import NotFound
from app.services.storage.base import StorageService, StoredObject


class S3StorageService(StorageService):
    name = "s3"

    def __init__(self) -> None:
        import boto3

        if not settings.S3_BUCKET:
            raise ValueError("S3_BUCKET is required when STORAGE_PROVIDER=s3.")
        kwargs: dict = {"region_name": settings.S3_REGION}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        self._client = boto3.client("s3", **kwargs)
        self._bucket = settings.S3_BUCKET

    async def put(self, key: str, data: bytes, mime_type: str) -> StoredObject:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=mime_type,
            ServerSideEncryption="AES256",
        )
        return StoredObject(key=key, size_bytes=len(data), mime_type=mime_type, sha256=hashlib.sha256(data).hexdigest())

    async def get(self, key: str) -> bytes:
        try:
            obj = await asyncio.to_thread(self._client.get_object, Bucket=self._bucket, Key=key)
            return await asyncio.to_thread(obj["Body"].read)
        except self._client.exceptions.NoSuchKey as exc:
            raise NotFound("That document is no longer available.") from exc

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)

    async def presigned_url(self, key: str, ttl_seconds: int | None = None) -> str | None:
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl_seconds or settings.S3_SIGNED_URL_TTL_SECONDS,
        )
