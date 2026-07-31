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
