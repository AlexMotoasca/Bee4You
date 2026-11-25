"""Groq access: the only module that talks to Groq. The API key never leaves the server."""

from functools import lru_cache

from groq import AsyncGroq

from app.config import get_settings
from app.errors import AppError

# Biases Whisper toward beekeeping words it would otherwise mishear.
TRANSCRIPTION_PROMPTS = {
    "en": "Beekeeping log at the hive: hive 12, colony, apiary, oxalic acid, formic acid, "
    "Apivar, Varroa, thymol, queen seen, brood, frames, super, honey harvest, kilograms, "
    "millilitres.",
    "ro": "Jurnal de stupină: stupul 12, familie, stupină, acid oxalic, acid formic, Apivar, "
    "Varroa, timol, matca văzută, puiet, rame, magazie, cules, miere, kilograme, mililitri, "
    "benzi.",
}


def transcription_prompt(language: str | None) -> str:
    if language and language in TRANSCRIPTION_PROMPTS:
        return TRANSCRIPTION_PROMPTS[language]
    return TRANSCRIPTION_PROMPTS["en"] + " " + TRANSCRIPTION_PROMPTS["ro"]


class AssistantUnavailable(AppError):
    def __init__(self, message: str = "Voice assistant is unavailable, try again later") -> None:
        super().__init__(503, "assistant_unavailable", message)


def require_groq_key() -> str:
    key = get_settings().groq_api_key
    if not key:
        raise AssistantUnavailable("Voice assistant is not configured (GROQ_API_KEY missing)")
    return key


@lru_cache
def get_groq() -> AsyncGroq:
    settings = get_settings()
    return AsyncGroq(
        api_key=require_groq_key(), timeout=settings.groq_timeout_seconds, max_retries=2
    )
