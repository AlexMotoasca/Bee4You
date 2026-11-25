"""Speech to text with Groq Whisper (fallback when the phone's recognizer can't be used)."""

import logging
from typing import Any, Protocol

import groq

from app.assistant.groq_client import AssistantUnavailable, get_groq, transcription_prompt
from app.config import get_settings

logger = logging.getLogger(__name__)


class Transcriber(Protocol):
    async def __call__(
        self, audio: bytes, filename: str, content_type: str, language: str | None
    ) -> str: ...


async def groq_transcribe(
    audio: bytes, filename: str, content_type: str, language: str | None
) -> str:
    """`language` is ISO-639-1 ("en", "ro"); None lets Whisper detect it."""
    extra: dict[str, Any] = {"language": language} if language else {}
    try:
        result = await get_groq().audio.transcriptions.create(
            file=(filename, audio, content_type),
            model=get_settings().groq_transcription_model,
            prompt=transcription_prompt(language),
            response_format="json",
            temperature=0.0,
            **extra,
        )
    except groq.APIError as exc:
        logger.warning("groq transcription failed: %s", type(exc).__name__)
        raise AssistantUnavailable("Speech recognition failed, try again") from exc
    text: str = result.text
    return text.strip()


def get_transcriber() -> Transcriber:
    return groq_transcribe
