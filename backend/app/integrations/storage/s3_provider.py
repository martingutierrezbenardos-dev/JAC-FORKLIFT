"""Implementación REAL de ``FileStorageProvider`` usando Amazon S3 (boto3).

No es un mock: sube el archivo de verdad al bucket configurado. Si ``AWS_S3_BUCKET`` no está
configurado, el constructor lanza ``FileStorageNotConfiguredError`` en vez de simular una URL.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.integrations.storage.provider import FileStorageNotConfiguredError, FileStorageProvider


class S3FileStorageProvider(FileStorageProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.aws_s3_bucket:
            raise FileStorageNotConfiguredError()

        import boto3

        client_kwargs: dict = {}
        if settings.aws_region:
            client_kwargs["region_name"] = settings.aws_region
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        self._bucket = settings.aws_s3_bucket
        self._region = settings.aws_region
        self._client = boto3.client("s3", **client_kwargs)

    def upload(self, key: str, content: bytes, content_type: str) -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content, ContentType=content_type)
        region_segment = f".s3.{self._region}" if self._region else ".s3"
        return f"https://{self._bucket}{region_segment}.amazonaws.com/{key}"
