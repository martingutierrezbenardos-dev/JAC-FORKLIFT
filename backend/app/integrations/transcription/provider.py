"""Transcripción de audio (sección 8 del brief).

Claude (Anthropic) no acepta audio como entrada, así que se necesita un proveedor externo de
transcripción. Se usa la API de Whisper de OpenAI porque es el estándar más simple y mejor
documentado para esto — es una integración REAL (no un mock): requiere ``OPENAI_API_KEY``. Si
no está configurada, se falla explícitamente (``TranscriptionNotConfiguredError``) en vez de
simular una transcripción falsa.

La interfaz queda abstracta (``TranscriptionProvider``) para poder reemplazar el proveedor
(Google Speech-to-Text, AssemblyAI, un modelo local) sin tocar el resto del sistema.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import get_settings


class TranscriptionNotConfiguredError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "La transcripción de audio no está configurada (falta OPENAI_API_KEY). "
            "Ver docs/whatsapp.md."
        )


class TranscriptionProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        """Devuelve la transcripción en texto plano del audio entregado."""


_MIME_TO_EXTENSION = {
    "audio/ogg": "ogg",
    "audio/ogg; codecs=opus": "ogg",
    "audio/opus": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp4": "mp4",
    "audio/amr": "amr",
    "audio/aac": "aac",
}


class OpenAIWhisperTranscriptionProvider(TranscriptionProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise TranscriptionNotConfiguredError()

        import openai  # import diferido: no requerido si no se usa este proveedor

        self._client = openai.OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_transcription_model

    def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        extension = _MIME_TO_EXTENSION.get(mime_type.split(";")[0].strip(), "ogg")
        # La API de OpenAI identifica el formato por el nombre del archivo, no solo el mime.
        file_tuple = (f"audio.{extension}", audio_bytes, mime_type)
        transcription = self._client.audio.transcriptions.create(model=self._model, file=file_tuple)
        return transcription.text.strip()
