import boto3
import pytest

import app.services.media_service as media_service_module
from app.core.config import get_settings
from app.core.permissions import UserRole
from app.integrations.storage.provider import FileStorageNotConfiguredError
from app.integrations.storage.s3_provider import S3FileStorageProvider
from app.models.media_log import MediaLog
from app.services import media_service
from sqlalchemy import select
from tests.conftest import make_user


def test_s3_provider_requiere_configuracion(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "aws_s3_bucket", None)

    with pytest.raises(FileStorageNotConfiguredError):
        S3FileStorageProvider()


def test_s3_provider_sube_y_devuelve_url(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "aws_s3_bucket", "jacobea-comprobantes")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    monkeypatch.setattr(settings, "aws_access_key_id", None)
    monkeypatch.setattr(settings, "aws_secret_access_key", None)

    class _FakeS3Client:
        def __init__(self) -> None:
            self.calls = []

        def put_object(self, **kwargs):
            self.calls.append(kwargs)

    fake_client = _FakeS3Client()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: fake_client)

    provider = S3FileStorageProvider()
    url = provider.upload("comprobantes/user1/wamid1.jpg", b"contenido", "image/jpeg")

    assert url == "https://jacobea-comprobantes.s3.us-east-1.amazonaws.com/comprobantes/user1/wamid1.jpg"
    assert fake_client.calls[0]["Bucket"] == "jacobea-comprobantes"
    assert fake_client.calls[0]["Key"] == "comprobantes/user1/wamid1.jpg"


def test_media_service_sin_storage_configurado_no_sube_nada(db_session, monkeypatch):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900888001")

    monkeypatch.setattr(
        media_service_module.WhatsAppClient, "download_media",
        lambda self, media_id: (b"image-bytes", "image/jpeg"),
    )

    from app.ai.receipt_extraction import ExtractedReceipt

    monkeypatch.setattr(
        media_service_module, "extract_receipt_data",
        lambda image_bytes, mime_type: ExtractedReceipt(proveedor="X", monto=1000),
    )

    def _raise():
        raise FileStorageNotConfiguredError()

    monkeypatch.setattr(media_service_module, "S3FileStorageProvider", _raise)

    result = media_service.process_image_message(db_session, user=tecnico, wa_media_id="wamid.storage1")

    assert result.comprobante_url is None
    log = db_session.execute(select(MediaLog).where(MediaLog.wa_media_id == "wamid.storage1")).scalars().first()
    assert log.storage_url is None


def test_media_service_con_storage_configurado_guarda_la_url(db_session, monkeypatch):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900888002")

    monkeypatch.setattr(
        media_service_module.WhatsAppClient, "download_media",
        lambda self, media_id: (b"image-bytes", "image/jpeg"),
    )

    from app.ai.receipt_extraction import ExtractedReceipt

    monkeypatch.setattr(
        media_service_module, "extract_receipt_data",
        lambda image_bytes, mime_type: ExtractedReceipt(proveedor="Y", monto=2000),
    )

    class _FakeStorageProvider:
        def upload(self, key, content, content_type):
            return f"https://fake-bucket.s3.amazonaws.com/{key}"

    monkeypatch.setattr(media_service_module, "S3FileStorageProvider", _FakeStorageProvider)

    result = media_service.process_image_message(db_session, user=tecnico, wa_media_id="wamid.storage2")

    assert result.comprobante_url is not None
    assert "wamid.storage2" in result.comprobante_url
    log = db_session.execute(select(MediaLog).where(MediaLog.wa_media_id == "wamid.storage2")).scalars().first()
    assert log.storage_url == result.comprobante_url
