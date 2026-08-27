"""S3 access shared by ingest (download) and drafting (upload). Path-style +
v4 signatures, matching the API's storage client: bucket-in-URL works on
MinIO and R2 alike. All functions are sync (boto3) — call via
run_in_executor from async code."""

from functools import lru_cache

import boto3
from botocore.config import Config as BotoConfig

from worker.settings import get_settings

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@lru_cache
def s3_client():
    # Cached — boto3 clients are thread-safe and calls run on executor threads.
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        region_name=settings.storage_region,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def download_file(storage_key: str, dest: str) -> None:
    s3_client().download_file(get_settings().storage_bucket, storage_key, dest)


def upload_bytes(storage_key: str, data: bytes, content_type: str) -> None:
    s3_client().put_object(
        Bucket=get_settings().storage_bucket,
        Key=storage_key,
        Body=data,
        ContentType=content_type,
    )


def upload_file(storage_key: str, path: str, content_type: str) -> None:
    """Large artefacts (workspace archives) — boto3 streams from disk and
    switches to multipart automatically, so a multi-GB file never has to fit
    in memory the way `upload_bytes` requires."""
    s3_client().upload_file(
        path,
        get_settings().storage_bucket,
        storage_key,
        ExtraArgs={"ContentType": content_type},
    )


def list_keys(prefix: str) -> list[str]:
    """Every object key under a prefix, paginated (1000/page)."""
    keys: list[str] = []
    for page in (
        s3_client()
        .get_paginator("list_objects_v2")
        .paginate(Bucket=get_settings().storage_bucket, Prefix=prefix)
    ):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return keys
