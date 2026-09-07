"""Interfaz abstracta de almacenamiento permanente de archivos (Fase 4).

Cierra el riesgo documentado en Fases 2/3: hasta ahora, las fotos de comprobantes y los
audios de WhatsApp se procesaban al vuelo (transcripción/extracción) y se descartaban. Con un
proveedor configurado, la imagen del comprobante se sube y su URL queda en
``expenses.comprobante_url`` / ``media_logs``, permitiendo volver a mirarla después
(auditoría, contabilidad).

Implementación real: ``S3FileStorageProvider`` (Amazon S3, vía boto3). Sin
``AWS_S3_BUCKET`` configurado, se sigue sin guardar el archivo — no se simula una URL falsa.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class FileStorageProvider(ABC):
    @abstractmethod
    def upload(self, key: str, content: bytes, content_type: str) -> str:
        """Sube el archivo y devuelve una URL utilizable para acceder a él después."""


class FileStorageNotConfiguredError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "El almacenamiento permanente de archivos no está configurado (falta "
            "AWS_S3_BUCKET). El archivo se procesó pero no se guardó — ver docs/architecture.md."
        )
