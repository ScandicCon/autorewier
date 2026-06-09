"""Транскрипция голосовых сообщений через OpenRouter Whisper API."""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger("autorewier.transcription")

_TRANSCRIPTION_ENDPOINT = "https://openrouter.ai/api/v1/audio/transcriptions"


async def transcribe_voice(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Транскрибирует аудио-файл через OpenRouter Whisper.

    Args:
        audio_bytes: Бинарное содержимое аудио-файла (OGG, MP3, WAV и др.).
        filename: Имя файла с расширением — используется для определения формата.

    Returns:
        Текст транскрипции или пустая строка при ошибке.

    Raises:
        RuntimeError: Если API ключ не настроен.
    """
    if not settings.openrouter_api_key.strip():
        raise RuntimeError(
            "OPENROUTER_API_KEY не настроен. Голосовой ввод недоступен."
        )

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
    }
    if settings.openrouter_site_url.strip():
        headers["HTTP-Referer"] = settings.openrouter_site_url
    if settings.openrouter_app_name.strip():
        headers["X-Title"] = settings.openrouter_app_name

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                _TRANSCRIPTION_ENDPOINT,
                headers=headers,
                files={
                    "file": (filename, audio_bytes, "audio/ogg"),
                },
                data={
                    "model": settings.whisper_model,
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data.get("text", "").strip()
            logger.info(
                "transcription_success",
                extra={"length": len(text), "model": settings.whisper_model},
            )
            return text
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "transcription_api_error",
            extra={"status": exc.response.status_code, "body": exc.response.text[:500]},
        )
        raise RuntimeError(
            f"Ошибка Whisper API ({exc.response.status_code}): {exc.response.text[:200]}"
        ) from exc
    except httpx.RequestError as exc:
        logger.warning("transcription_network_error", extra={"error": str(exc)})
        raise RuntimeError(f"Сетевая ошибка при транскрипции: {exc}") from exc
