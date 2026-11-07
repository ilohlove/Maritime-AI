"""Private originals only. Object keys are generated IDs, never user filenames."""

import os
import re
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.services.document_ai import WorkflowError


class DocumentStorage(Protocol):
    def put(self, key: str, content: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def size(self, key: str) -> int: ...
    def validate(self) -> None: ...


def valid_key(key: str) -> str:
    if not re.fullmatch(r"[0-9a-f-]{36}\.bin", key):
        raise WorkflowError(
            "invalid_object_key", "Invalid document object identifier.", 422
        )
    try:
        if str(UUID(key[:-4])) != key[:-4]:
            raise ValueError
    except ValueError:
        raise WorkflowError(
            "invalid_object_key", "Invalid document object identifier.", 422
        ) from None
    return key


def unavailable():
    return WorkflowError(
        "storage_unavailable",
        "Private document storage is unavailable. Retry after storage recovery.",
    )


class LocalStorage:
    def __init__(self, directory: Path):
        self.directory = directory

    def path(self, key):
        path = self.directory / valid_key(key)
        if path.is_symlink():
            raise unavailable()
        return path

    def put(self, key, content):
        path = self.path(key)
        try:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "wb") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
        except OSError:
            raise unavailable() from None

    def get(self, key):
        try:
            with self.path(key).open("rb") as file:
                value = file.read(10_000_001)
            if len(value) > 10_000_000:
                raise unavailable()
            return value
        except OSError:
            raise unavailable() from None

    def delete(self, key):
        try:
            self.path(key).unlink(missing_ok=True)
        except OSError:
            raise unavailable() from None

    def size(self, key):
        try:
            return self.path(key).stat().st_size
        except OSError:
            raise unavailable() from None

    def validate(self):
        import tempfile

        try:
            with tempfile.TemporaryFile(dir=self.directory):
                pass
        except OSError:
            raise unavailable() from None


class S3Storage:
    def __init__(self, settings, client=None):
        if client is None:
            import boto3
            from botocore.config import Config
            from botocore.session import Session

            # This adapter uses only the explicitly configured S3 credentials.
            # Isolate its SDK session from unrelated operator AWS profiles.
            sdk_session = Session(session_vars={"profile": (None, None, None, None)})
            client = boto3.Session(botocore_session=sdk_session).client(
                "s3",
                endpoint_url=settings.s3_endpoint,
                region_name=settings.s3_region,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=5,
                    read_timeout=10,
                    retries={"total_max_attempts": 1},
                    max_pool_connections=2,
                    s3={"addressing_style": "path"},
                ),
            )
        self.client, self.bucket = client, settings.s3_bucket

    def call(self, method, key=None, **kwargs):
        from botocore.exceptions import BotoCoreError, ClientError

        if key is not None:
            kwargs["Key"] = valid_key(key)
        try:
            return getattr(self.client, method)(Bucket=self.bucket, **kwargs)
        except (BotoCoreError, ClientError, OSError):
            raise unavailable() from None

    def put(self, key, content):
        # No public ACL, URLs, user-controlled metadata or multipart orphan parts.
        self.call(
            "put_object", key, Body=content, ContentType="application/octet-stream"
        )

    def get(self, key):
        from botocore.exceptions import BotoCoreError

        body = self.call("get_object", key)["Body"]
        try:
            content = body.read(3_000_001)
            if len(content) > 3_000_000:
                raise unavailable()
            return content
        except (BotoCoreError, OSError):
            raise unavailable() from None
        finally:
            body.close()

    def delete(self, key):
        self.call("delete_object", key)

    def size(self, key):
        return self.call("head_object", key)["ContentLength"]

    def validate(self):
        self.call("head_bucket")


def create_storage(settings, directory):
    return (
        S3Storage(settings)
        if settings.storage_backend == "s3"
        else LocalStorage(directory)
    )
