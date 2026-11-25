"""Transcription endpoint (Groq faked) and voice-built rows vs. the sync validation."""

import uuid
from typing import Any

import httpx
import pytest

from app.assistant.service import build_ops
from app.assistant.transcribe import get_transcriber
from app.auth.jwt import CurrentUser
from app.main import create_app
from app.services.sync import prepare_op
from tests.voice_helpers import FOREST, HIVE7, OXALIC

# ---------------------------------------------------------------- /v1/voice/transcribe


@pytest.fixture
async def voice_client() -> Any:
    calls: list[dict[str, Any]] = []

    async def fake_transcriber(
        audio: bytes, filename: str, content_type: str, language: str | None
    ) -> str:
        calls.append({"size": len(audio), "filename": filename, "language": language})
        return " Stupul 12, acid oxalic, cinci mililitri. "

    app = create_app()
    app.dependency_overrides[get_transcriber] = lambda: fake_transcriber
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, calls


async def test_transcribe_romanian(voice_client: Any, make_token: Any) -> None:
    client, calls = voice_client
    r = await client.post(
        "/v1/voice/transcribe",
        headers={"Authorization": f"Bearer {make_token()}"},
        files={"audio": ("clip.m4a", b"\x00" * 2048, "audio/m4a")},
        data={"language": "ro"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"text": "Stupul 12, acid oxalic, cinci mililitri."}
    assert calls == [{"size": 2048, "filename": "clip.m4a", "language": "ro"}]


async def test_transcribe_requires_login(voice_client: Any) -> None:
    client, _ = voice_client
    files = {"audio": ("clip.m4a", b"\x00", "audio/m4a")}
    r = await client.post("/v1/voice/transcribe", files=files)
    assert r.status_code == 401


async def test_transcribe_rejects_empty_and_bad_language(
    voice_client: Any, make_token: Any
) -> None:
    client, _ = voice_client
    auth = {"Authorization": f"Bearer {make_token()}"}
    r = await client.post(
        "/v1/voice/transcribe", headers=auth, files={"audio": ("a.m4a", b"", "audio/m4a")}
    )
    assert r.status_code == 400
    r = await client.post(
        "/v1/voice/transcribe",
        headers=auth,
        files={"audio": ("a.m4a", b"\x00", "audio/m4a")},
        data={"language": "romanian"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------- voice rows == typed rows


def state_for(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "ids": {k: str(uuid.uuid4()) for k in ("record", "adjustment", "item")},
        "resolution": {"occurred_at": "2026-11-25T09:30:00+00:00", **fields},
    }


def validate_all(state: dict[str, Any]) -> list[Any]:
    user = CurrentUser(id=uuid.uuid4(), role="authenticated")
    ops, _ = build_ops(state)  # type: ignore[arg-type]
    return [prepare_op(op, user) for op in ops]  # raises OpRejected if anything is invalid


def test_treatment_with_stock_item_builds_treatment_and_adjustment() -> None:
    state = state_for(
        {
            "kind": "treatment",
            "colony_id": HIVE7,
            "apiary_id": FOREST,
            "product_name": "Acid oxalic",
            "item_id": OXALIC,
            "item_unit": "ml",
            "amount": "5",
            "unit": "ml",
        }
    )
    treatment, adjustment = validate_all(state)
    assert treatment.spec.name == "treatments" and treatment.values["source"] == "voice"
    assert adjustment.spec.name == "inventory_adjustments"
    assert str(adjustment.values["delta"]) == "-5"
    assert str(adjustment.values["treatment_id"]) == state["ids"]["record"]


def test_treatment_unit_mismatch_does_not_touch_stock() -> None:
    state = state_for(
        {
            "kind": "treatment",
            "colony_id": HIVE7,
            "apiary_id": FOREST,
            "product_name": "Acid oxalic",
            "item_id": OXALIC,
            "item_unit": "ml",
            "amount": "1",
            "unit": "l",
        }
    )
    [only] = validate_all(state)
    assert only.spec.name == "treatments"


def test_inventory_purchase_of_new_item() -> None:
    state = state_for(
        {
            "kind": "inventory",
            "product_name": "zahăr",
            "item_id": None,
            "item_is_new": True,
            "action": "purchase",
            "amount": "10",
            "unit": "kg",
        }
    )
    item, adjustment = validate_all(state)
    assert item.spec.name == "inventory_items" and item.values["name"] == "zahăr"
    assert str(adjustment.values["item_id"]) == state["ids"]["item"]
    assert str(adjustment.values["delta"]) == "10"


def test_harvest_and_note() -> None:
    [harvest] = validate_all(
        state_for({"kind": "harvest", "apiary_id": FOREST, "amount": "18", "unit": "kg"})
    )
    assert harvest.spec.name == "harvests"
    [note] = validate_all(
        state_for(
            {
                "kind": "note",
                "colony_id": HIVE7,
                "apiary_id": FOREST,
                "queen_seen": True,
                "temperament": "calm",
                "text": None,
            }
        )
    )
    assert note.spec.name == "colony_notes" and note.values["queen_seen"] is True


# ---------------------------------------------------------------- Groq output quirks


def test_null_strings_become_null() -> None:
    from app.assistant.schemas import ExtractedEntry

    e = ExtractedEntry.model_validate(
        {
            "kind": "harvest",
            "colony": "null",
            "apiary": "Pădure",
            "product": "None",
            "amount": 18,
            "unit": "kg",
            "inventory_action": "null",
            "queen_seen": None,
            "temperament": None,
            "note": "",
            "date": "2026-11-24",
        }
    )
    assert (e.colony, e.product, e.inventory_action, e.note) == (None, None, None, None)
    assert (e.kind, e.apiary, e.amount) == ("harvest", "Pădure", 18)


def test_recover_entry_from_groq_schema_rejection() -> None:
    import groq
    import httpx as hx

    from app.assistant.llm import recover_failed_generation

    generated = (
        '{"kind":"harvest","colony":"null","apiary":"Pădure","product":"null","amount":18,'
        '"unit":"kg","inventory_action":"null","queen_seen":null,"temperament":null,'
        '"note":null,"date":"2026-11-24"}'
    )
    body = {"error": {"code": "json_validate_failed", "failed_generation": generated}}
    request = hx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    exc = groq.BadRequestError("schema", response=hx.Response(400, request=request), body=body)
    e = recover_failed_generation(exc)
    assert e is not None and (e.kind, e.amount, e.unit, e.date) == (
        "harvest",
        18,
        "kg",
        "2026-11-24",
    )

    other = groq.BadRequestError(
        "bad", response=hx.Response(400, request=request), body={"error": {"code": "other"}}
    )
    assert recover_failed_generation(other) is None


def test_model_sees_digits_not_number_words() -> None:
    from datetime import date

    from app.assistant.llm import ExtractRequest, build_messages
    from tests.voice_helpers import CATALOG

    req = ExtractRequest(
        messages=[{"role": "user", "text": "Ieri am recoltat optsprezece kilograme"}],
        previous=None,
        catalog=CATALOG,
        today=date(2026, 11, 25),
        language="ro",
    )
    _, user = build_messages(req)
    assert "Beekeeper: Ieri am recoltat 18 kilograme" in user[1]
