"""Real Groq calls: does the model extract Romanian and English entries correctly?

Run with: uv run pytest --groq tests/test_groq_live.py   (needs GROQ_API_KEY in .env)
"""

from datetime import date

import pytest

from app.assistant.llm import ExtractRequest, groq_extract
from tests.voice_helpers import CATALOG

pytestmark = pytest.mark.groq


async def extract(text: str, language: str = "ro"):  # type: ignore[no-untyped-def]
    return await groq_extract(
        ExtractRequest(
            messages=[{"role": "user", "text": text}],
            previous=None,
            catalog=CATALOG,
            today=date(2026, 11, 25),
            language=language,
        )
    )


async def test_romanian_treatment() -> None:
    e = await extract("Stupul 12, acid oxalic, cinci mililitri, matca văzută, calmă")
    assert (e.kind, e.colony, e.amount, e.unit) == ("treatment", "12", 5, "ml")
    assert "oxalic" in (e.product or "").lower()
    assert e.queen_seen is True and e.temperament == "calm"


async def test_romanian_missing_amount_stays_null() -> None:
    e = await extract("Am pus Apivar la stupul 7")
    assert e.kind == "treatment" and e.colony == "7" and e.amount is None


async def test_romanian_harvest_yesterday() -> None:
    e = await extract("Ieri am recoltat optsprezece kilograme de miere la Pădure")
    assert (e.kind, e.amount, e.unit, e.date) == ("harvest", 18, "kg", "2026-11-24")


async def test_romanian_inventory_purchase() -> None:
    e = await extract("Am cumpărat doi litri de acid oxalic")
    assert (e.kind, e.inventory_action, e.amount, e.unit) == ("inventory", "purchase", 2, "l")


async def test_english_note() -> None:
    e = await extract("Hive 7, queen seen, a bit nervous today", language="en")
    assert (e.kind, e.colony, e.queen_seen, e.temperament) == ("note", "7", True, "nervous")
