"""File storage for uploaded documents: local disk by default, S3-compatible object storage
(Neon) when S3_BUCKET + AWS_ENDPOINT_URL_S3 are set.

`Document.file_path` holds either a local path or `s3://<key>`, so existing rows keep working
and the database schema doesn't change.
"""
import asyncio
import tempfile
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from app.core.config import settings

S3_PREFIX = "s3://"


def is_s3_path(path: str | None) -> bool:
    return bool(path) and path.startswith(S3_PREFIX)


@lru_cache
def _client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3", endpoint_url=settings.AWS_ENDPOINT_URL_S3, region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(s3={"addressing_style": "path"}),
    )


def _key(path: str) -> str:
    return path[len(S3_PREFIX):]


async def save(name: str, data: bytes, content_type: str | None = None) -> str:
    """Store `data` under `name`; return the value to keep in Document.file_path."""
    if settings.use_s3:
        extra = {"ContentType": content_type} if content_type else {}
        await asyncio.to_thread(_client().put_object, Bucket=settings.S3_BUCKET, Key=f"documents/{name}",
                                Body=data, **extra)
        return f"{S3_PREFIX}documents/{name}"
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = settings.UPLOAD_DIR / name
    dest.write_bytes(data)
    return str(dest)


async def read(path: str) -> bytes | None:
    """File bytes, or None when the file is gone."""
    if is_s3_path(path):
        from botocore.exceptions import ClientError

        try:
            obj = await asyncio.to_thread(_client().get_object, Bucket=settings.S3_BUCKET, Key=_key(path))
            return await asyncio.to_thread(obj["Body"].read)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise
    p = Path(path)
    return p.read_bytes() if p.is_file() else None


async def delete(path: str) -> None:
    if is_s3_path(path):
        await asyncio.to_thread(_client().delete_object, Bucket=settings.S3_BUCKET, Key=_key(path))
    else:
        Path(path).unlink(missing_ok=True)


@asynccontextmanager
async def local_copy(path: str):
    """Yield a local Path for the file, downloading it first if it lives in object storage."""
    if not is_s3_path(path):
        yield Path(path)
        return
    data = await read(path)
    if data is None:
        raise FileNotFoundError(path)
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / Path(_key(path)).name
        local.write_bytes(data)
        yield local
