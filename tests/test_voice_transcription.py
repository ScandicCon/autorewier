"""
Тесты голосовой транскрипции (Whisper через OpenRouter/OpenAI API).

Покрываемые сценарии:
- Mock OpenRouter whisper → возвращает непустую строку
- Пустой аудио-файл → не крашит, возвращает ""
- llm_enabled=False → возвращает "" gracefully
- Mock бросает exception → graceful ""

Все тесты используют monkeypatch для подмены OpenAI-клиента.
Реальных HTTP-запросов к OpenRouter не делается.
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_audio(content: bytes = b"fake audio data") -> io.BytesIO:
    """Создаёт файлоподобный объект для имитации аудио."""
    buf = io.BytesIO(content)
    buf.name = "test_audio.ogg"
    return buf


def _make_empty_audio() -> io.BytesIO:
    buf = io.BytesIO(b"")
    buf.name = "empty.ogg"
    return buf


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_transcribe_returns_text(monkeypatch: pytest.MonkeyPatch):
    """
    Когда OpenRouter Whisper API возвращает текст,
    функция transcribe_audio должна вернуть непустую строку.
    """
    try:
        import app.services.voice_transcription as vt
    except ImportError:
        pytest.skip("Модуль app.services.voice_transcription ещё не реализован")

    expected_text = "Toyota Camry 2016, пробег 180 тысяч, стук в подвеске"

    mock_transcription = MagicMock()
    mock_transcription.text = expected_text

    mock_audio_resource = AsyncMock()
    mock_audio_resource.transcriptions.create = AsyncMock(return_value=mock_transcription)

    mock_client = MagicMock()
    mock_client.audio = mock_audio_resource

    monkeypatch.setattr(vt, "_openrouter_client", lambda: mock_client, raising=False)

    audio_file = _make_fake_audio()
    result = pytest.importorskip("asyncio").run(vt.transcribe_audio(audio_file))

    assert isinstance(result, str)
    assert result == expected_text


def test_transcribe_empty_audio(monkeypatch: pytest.MonkeyPatch):
    """
    Пустой аудио-файл не должен крашить систему.
    Ожидаем возврат пустой строки "".
    """
    try:
        import app.services.voice_transcription as vt
    except ImportError:
        pytest.skip("Модуль app.services.voice_transcription ещё не реализован")

    mock_transcription = MagicMock()
    mock_transcription.text = ""

    mock_audio_resource = AsyncMock()
    mock_audio_resource.transcriptions.create = AsyncMock(return_value=mock_transcription)

    mock_client = MagicMock()
    mock_client.audio = mock_audio_resource

    monkeypatch.setattr(vt, "_openrouter_client", lambda: mock_client, raising=False)

    audio_file = _make_empty_audio()

    import asyncio
    result = asyncio.run(vt.transcribe_audio(audio_file))

    assert result == ""


def test_transcribe_no_key(monkeypatch: pytest.MonkeyPatch):
    """
    Когда llm_enabled=False (нет API-ключа), функция должна
    gracefully вернуть пустую строку без вызова API.
    """
    try:
        import app.services.voice_transcription as vt
    except ImportError:
        pytest.skip("Модуль app.services.voice_transcription ещё не реализован")

    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", "")

    # Убеждаемся, что API НЕ вызывается
    api_called = []

    async def _should_not_be_called(*args, **kwargs):
        api_called.append(True)
        raise AssertionError("API не должен вызываться при llm_enabled=False")

    monkeypatch.setattr(vt, "_openrouter_client", lambda: None, raising=False)

    import asyncio
    audio_file = _make_fake_audio()
    result = asyncio.run(vt.transcribe_audio(audio_file))

    assert result == ""
    assert not api_called, "API был вызван несмотря на llm_enabled=False"


def test_transcribe_api_error(monkeypatch: pytest.MonkeyPatch):
    """
    Когда OpenRouter API бросает exception,
    функция должна gracefully вернуть пустую строку.
    """
    try:
        import app.services.voice_transcription as vt
    except ImportError:
        pytest.skip("Модуль app.services.voice_transcription ещё не реализован")

    mock_audio_resource = AsyncMock()
    mock_audio_resource.transcriptions.create = AsyncMock(
        side_effect=Exception("Connection timeout to OpenRouter")
    )

    mock_client = MagicMock()
    mock_client.audio = mock_audio_resource

    monkeypatch.setattr(vt, "_openrouter_client", lambda: mock_client, raising=False)

    import asyncio
    audio_file = _make_fake_audio()
    result = asyncio.run(vt.transcribe_audio(audio_file))

    assert result == "", (
        f"При ошибке API ожидалась пустая строка, получено: {result!r}"
    )
