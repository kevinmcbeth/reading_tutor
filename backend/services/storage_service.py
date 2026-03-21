"""Dual-mode storage: local filesystem or S3 + CloudFront."""

import logging
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

_s3_client = None


def _get_s3():
    global _s3_client
    if _s3_client is None:
        import boto3
        _s3_client = boto3.client("s3", region_name=settings.AWS_REGION)
    return _s3_client


def save_file(key: str, data: bytes) -> None:
    """Save file to local filesystem or S3.

    key: relative path like "stories/{uuid}/images/sentence_0.png"
    """
    if settings.STORAGE_BACKEND == "s3":
        content_type = "application/octet-stream"
        if key.endswith(".png"):
            content_type = "image/png"
        elif key.endswith(".wav"):
            content_type = "audio/wav"

        _get_s3().put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.info("Uploaded %s to S3", key)
    else:
        path = settings.data_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def get_url(key: str) -> str:
    """Return a URL for the given asset key.

    In S3 mode, returns a CloudFront URL.
    In local mode, returns the local file path as a string.
    """
    if settings.STORAGE_BACKEND == "s3":
        domain = settings.CLOUDFRONT_DOMAIN.rstrip("/")
        return f"https://{domain}/assets/{key}"
    else:
        return str(settings.data_path / key)


def file_exists(key: str) -> bool:
    """Check if a file exists in the configured storage backend."""
    if settings.STORAGE_BACKEND == "s3":
        try:
            _get_s3().head_object(Bucket=settings.S3_BUCKET, Key=key)
            return True
        except Exception:
            return False
    else:
        return (settings.data_path / key).exists()
