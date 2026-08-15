"""Object storage — S3-compatible client covering MinIO (dev) and R2 (prod).

Presigning is local crypto (no network), so it runs inline; head/delete hit
the network and are pushed to a thread so they never block the event loop.
When storage_endpoint is unset (unit tests, CI) the vault endpoints 503.
"""

from functools import lru_cache

import anyio
import boto3
from botocore.config import Config as BotoConfig

from app.config import get_settings
from app.errors import ApiError

PRESIGNED_PUT_TTL_S = 15 * 60
# Spec §9.3: short-lived GET links.
PRESIGNED_GET_TTL_S = 5 * 60
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

ALLOWED_MIMES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/csv": "csv",
    # Meeting transcripts (Teams, Meet, Zoom, Fathom all export WebVTT). The
    # worker parses these itself, speaker-aware — never Docling.
    "text/vtt": "vtt",
}


@lru_cache
def _s3():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        region_name=settings.storage_region,
        # Path-style: bucket-in-URL works on MinIO and R2 alike.
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


class Storage:
    @property
    def enabled(self) -> bool:
        return bool(get_settings().storage_endpoint)

    def _require(self) -> None:
        if not self.enabled:
            raise ApiError(503, "storage_unavailable", "File storage is not configured")

    def presign_put(self, key: str, mime: str) -> str:
        self._require()
        return _s3().generate_presigned_url(
            "put_object",
            Params={"Bucket": get_settings().storage_bucket, "Key": key, "ContentType": mime},
            ExpiresIn=PRESIGNED_PUT_TTL_S,
        )

    def presign_get(self, key: str) -> str:
        self._require()
        return _s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": get_settings().storage_bucket, "Key": key},
            ExpiresIn=PRESIGNED_GET_TTL_S,
        )

    async def object_size(self, key: str) -> int | None:
        """Size in bytes, or None if the object doesn't exist."""
        self._require()

        def _head() -> int | None:
            client = _s3()
            try:
                return client.head_object(Bucket=get_settings().storage_bucket, Key=key)[
                    "ContentLength"
                ]
            except client.exceptions.ClientError as exc:
                if exc.response["ResponseMetadata"]["HTTPStatusCode"] == 404:
                    return None
                raise

        return await anyio.to_thread.run_sync(_head)

    async def delete_object(self, key: str) -> None:
        self._require()
        await anyio.to_thread.run_sync(
            lambda: _s3().delete_object(Bucket=get_settings().storage_bucket, Key=key)
        )

    async def delete_prefix(self, prefix: str) -> int:
        """Everything under one tenant's prefix, for workspace purge.

        Batched (S3 caps delete_objects at 1000 keys); returns how many
        objects went, because "purged" should come with a number.
        """
        self._require()

        def _sweep() -> int:
            client = _s3()
            bucket = get_settings().storage_bucket
            deleted = 0
            for page in client.get_paginator("list_objects_v2").paginate(
                Bucket=bucket, Prefix=prefix
            ):
                keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if not keys:
                    continue
                client.delete_objects(Bucket=bucket, Delete={"Objects": keys, "Quiet": True})
                deleted += len(keys)
            return deleted

        return await anyio.to_thread.run_sync(_sweep)

    async def upload_bytes(self, key: str, data: bytes, mime: str) -> None:
        """Server-generated artefacts (slide exports). User uploads still go
        browser → storage via presigned PUT; this is not for file ingest."""
        self._require()
        await anyio.to_thread.run_sync(
            lambda: _s3().put_object(
                Bucket=get_settings().storage_bucket, Key=key, Body=data, ContentType=mime
            )
        )

    async def download_bytes(self, key: str) -> bytes | None:
        """Small objects only (brand logos); None if the object is missing."""
        self._require()

        def _get() -> bytes | None:
            client = _s3()
            try:
                obj = client.get_object(Bucket=get_settings().storage_bucket, Key=key)
                return obj["Body"].read()
            except client.exceptions.NoSuchKey:
                return None

        return await anyio.to_thread.run_sync(_get)


storage = Storage()
