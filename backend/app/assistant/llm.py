"""LLM extraction step (Groq). The model only fills ExtractedEntry; it never sees ids,
never writes anything, and never sees other users' data."""

import json
import logging
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import groq
from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq
from pydantic import ValidationError

from app.assistant.catalog import Catalog
from app.assistant.groq_client import AssistantUnavailable, require_groq_key
from app.assistant.numbers import words_to_digits
from app.assistant.schemas import ExtractedEntry
from app.config import get_settings

logger = logging.getLogger(__name__)

_PROMPT = (Path(__file__).parent / "prompts" / "extract_system.txt").read_text(encoding="utf-8")
_MAX_HINTS = 60


class ExtractionFailed(Exception):
    """The model answered but not with a usable entry (treated as 'not understood')."""


@dataclass(frozen=True)
class ExtractRequest:
    messages: list[dict[str, str]]  # {"role": "user"|"assistant", "text": ...}
    previous: dict[str, Any] | None  # last extracted entry, to be updated
    catalog: Catalog
    today: date
    language: str


class Extractor(Protocol):
    async def __call__(self, request: ExtractRequest) -> ExtractedEntry: ...


def _hints(names: list[str]) -> str:
    unique = list(dict.fromkeys(n for n in names if n))[:_MAX_HINTS]
    return ", ".join(unique) if unique else "(none yet)"


def build_messages(req: ExtractRequest) -> list[tuple[str, str]]:
    cat = req.catalog
    colonies = [
        f"{c.label} (number {c.number})" if c.number is not None else c.label for c in cat.colonies
    ]
    system = _PROMPT.format(
        today=req.today.isoformat(),
        language="Romanian" if req.language == "ro" else "English",
        colonies=_hints(colonies),
        apiaries=_hints([a.name for a in cat.apiaries]),
        items=_hints([i.name for i in cat.items]),
    )
    # Number words -> digits in plain code first: the model miscounts words like "optsprezece".
    lines = [
        f"Beekeeper: {words_to_digits(m['text'])}"
        if m["role"] == "user"
        else f"Assistant: {m['text']}"
        for m in req.messages
    ]
    user = "Conversation so far:\n" + "\n".join(lines)
    if req.previous:
        user += "\n\nCurrent draft (update it with the latest answer):\n" + json.dumps(
            req.previous, ensure_ascii=False
        )
    return [("system", system), ("user", user)]


@lru_cache
def _structured_llm() -> Runnable[Any, Any]:
    settings = get_settings()
    llm = ChatGroq(  # type: ignore[call-arg]
        model=settings.groq_model,
        api_key=require_groq_key(),
        temperature=0,
        request_timeout=settings.groq_timeout_seconds,
        max_retries=2,
        reasoning_effort="low" if settings.groq_model.startswith("openai/gpt-oss") else None,
    )
    return llm.with_structured_output(ExtractedEntry, method="json_schema", strict=True)


def recover_failed_generation(exc: groq.BadRequestError) -> ExtractedEntry | None:
    """Groq rejects output that breaks the schema (typically the string "null" in an enum
    field) but returns what the model generated. That text is usually right, so parse it
    leniently instead of failing the whole turn."""
    body = exc.body if isinstance(exc.body, dict) else {}
    error = body.get("error", body)
    if not isinstance(error, dict) or error.get("code") != "json_validate_failed":
        return None
    try:
        return ExtractedEntry.model_validate(json.loads(error.get("failed_generation") or ""))
    except (ValueError, ValidationError):
        return None


async def groq_extract(req: ExtractRequest) -> ExtractedEntry:
    try:
        result = await _structured_llm().ainvoke(build_messages(req))
    except (OutputParserException, ValidationError) as exc:
        raise ExtractionFailed(str(exc)) from exc
    except groq.BadRequestError as exc:
        recovered = recover_failed_generation(exc)
        if recovered is not None:
            logger.info("recovered entry from Groq failed_generation")
            return recovered
        if isinstance(exc.body, dict) and "json_validate_failed" in json.dumps(exc.body):
            raise ExtractionFailed("model output did not match the schema") from exc
        logger.warning("groq extraction failed: %s", type(exc).__name__)
        raise AssistantUnavailable() from exc
    except groq.APIError as exc:
        logger.warning("groq extraction failed: %s", type(exc).__name__)
        raise AssistantUnavailable() from exc
    if not isinstance(result, ExtractedEntry):
        raise ExtractionFailed("unexpected model output")
    return result


def get_extractor() -> Extractor:
    return groq_extract  # type: ignore[return-value]
