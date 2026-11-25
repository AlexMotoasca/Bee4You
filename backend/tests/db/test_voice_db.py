"""Voice assistant against the real database (LLM faked): records, sessions, voice notes.

Run with: uv run pytest --db
"""

from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.deps import get_current_user
from app.assistant.llm import get_extractor
from app.auth.jwt import CurrentUser
from app.db import user_session
from app.main import create_app
from tests.db.conftest import new_id, ts
from tests.voice_helpers import ScriptedExtractor, entry

pytestmark = pytest.mark.db


async def seed_hive(upload: Any, user: CurrentUser) -> dict[str, str]:
    ids = {"colony": new_id(), "apiary": new_id(), "item": new_id(), "placement": new_id()}
    results = await upload(
        user,
        [
            {
                "op": "PUT",
                "table": "apiaries",
                "id": ids["apiary"],
                "data": {"name": "Pădure", "client_updated_at": ts()},
            },
            {
                "op": "PUT",
                "table": "colonies",
                "id": ids["colony"],
                "data": {"label": "Stup 12", "number": 12, "client_updated_at": ts()},
            },
            {
                "op": "PUT",
                "table": "colony_placements",
                "id": ids["placement"],
                "data": {
                    "colony_id": ids["colony"],
                    "apiary_id": ids["apiary"],
                    "started_at": ts(),
                    "client_updated_at": ts(),
                },
            },
            {
                "op": "PUT",
                "table": "inventory_items",
                "id": ids["item"],
                "data": {
                    "name": "Acid oxalic",
                    "category": "treatment",
                    "unit": "ml",
                    "client_updated_at": ts(),
                },
            },
        ],
    )
    assert [r.status for r in results] == ["applied"] * 4, [r.error for r in results]
    return ids


def client_for(user: CurrentUser, extractor: ScriptedExtractor) -> httpx.AsyncClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_extractor] = lambda: extractor
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_romanian_treatment_end_to_end(make_user, upload, admin) -> None:
    user = await make_user()
    ids = await seed_hive(upload, user)
    extractor = ScriptedExtractor(
        entry(kind="treatment", colony="12", product="acid oxalic"),
        entry(kind="treatment", colony="12", product="acid oxalic", amount=5, unit="ml"),
    )
    async with client_for(user, extractor) as c:
        r1 = await c.post(
            "/v1/voice/sessions", json={"transcript": "Stupul 12, acid oxalic", "locale": "ro-RO"}
        )
        assert r1.status_code == 200, r1.text
        t1 = r1.json()
        assert (t1["status"], t1["speak"], t1["haptic"]) == (
            "question",
            "Cât ai folosit?",
            "needs_answer",
        )
        thread = t1["thread_id"]

        t2 = (await c.post(f"/v1/voice/sessions/{thread}/reply", json={"text": "cinci ml"})).json()
        assert t2["status"] == "confirm"
        assert t2["speak"].startswith("Tratament pentru Stup 12: Acid oxalic, 5 mililitri")

        t3 = (await c.post(f"/v1/voice/sessions/{thread}/reply", json={"text": "da"})).json()
        assert (t3["status"], t3["speak"], t3["haptic"]) == ("saved", "Salvat.", "saved")
        record_id = t3["record"]["id"]

        # The app retries "da" after a dropped response: same answer, no duplicate rows.
        t4 = (await c.post(f"/v1/voice/sessions/{thread}/reply", json={"text": "da"})).json()
        assert t4["status"] == "saved" and t4["record"]["id"] == record_id

    rows = await admin(
        "select colony_id::text, apiary_id::text, inventory_item_id::text, amount, unit, source"
        " from public.treatments where owner_id = :u",
        {"u": user.id},
    )
    assert len(rows) == 1
    colony, apiary, item, amount, unit, source = rows[0]
    assert (colony, apiary, item, unit, source) == (
        ids["colony"],
        ids["apiary"],
        ids["item"],
        "ml",
        "voice",
    )
    assert float(amount) == 5
    stock = await admin(
        "select delta, treatment_id::text from public.inventory_adjustments where owner_id = :u",
        {"u": user.id},
    )
    assert [(float(d), t) for d, t in stock] == [(-5.0, record_id)]
    sessions = await admin("select status from public.voice_sessions where id = :t", {"t": thread})
    assert sessions == [("saved",)]


async def test_sessions_are_private(make_user, upload, admin) -> None:
    alice, bob = await make_user(), await make_user()
    await seed_hive(upload, alice)
    extractor = ScriptedExtractor(entry(kind="note", colony="12", queen_seen=True))
    async with client_for(alice, extractor) as c:
        thread = (
            await c.post("/v1/voice/sessions", json={"transcript": "Stupul 12, matca văzută"})
        ).json()["thread_id"]

    # Bob can't continue Alice's conversation.
    async with client_for(bob, extractor) as c:
        r = await c.post(f"/v1/voice/sessions/{thread}/reply", json={"text": "yes"})
        assert r.status_code == 404

    # Even Alice can't read raw session state through her own role (PostgREST path).
    async with user_session(alice) as session:
        with pytest.raises(DBAPIError):
            await session.execute(text("select * from public.voice_sessions"))


async def test_offline_voice_note_is_processed_with_confirmation(make_user, upload, admin) -> None:
    user = await make_user()
    ids = await seed_hive(upload, user)
    note_id = new_id()
    [r] = await upload(
        user,
        [
            {
                "op": "PUT",
                "table": "voice_notes",
                "id": note_id,
                "data": {
                    "transcript": "Am recoltat 18 kilograme de miere",
                    "locale": "ro-RO",
                    "context_apiary_id": ids["apiary"],
                    "client_updated_at": ts(),
                },
            }
        ],
    )
    assert r.status == "applied", r.error

    extractor = ScriptedExtractor(entry(kind="harvest", amount=18, unit="kg"))
    async with client_for(user, extractor) as c:
        t1 = (await c.post(f"/v1/voice/notes/{note_id}/process")).json()
        assert t1["status"] == "confirm"
        assert t1["speak"].startswith("Recoltă la Pădure: 18 kilograme")
        status = await admin("select status from public.voice_notes where id = :n", {"n": note_id})
        assert status == [("needs_confirmation",)]

        # Processing again re-asks the same question instead of starting over.
        again = (await c.post(f"/v1/voice/notes/{note_id}/process")).json()
        assert again["thread_id"] == t1["thread_id"] and again["status"] == "confirm"

        t2 = (
            await c.post(f"/v1/voice/sessions/{t1['thread_id']}/reply", json={"text": "da"})
        ).json()
        assert t2["status"] == "saved"

    note = await admin(
        "select status, result_record_type, result_record_id::text from public.voice_notes"
        " where id = :n",
        {"n": note_id},
    )
    assert note == [("saved", "harvests", t2["record"]["id"])]
    harvests = await admin(
        "select quantity, unit, apiary_id::text from public.harvests where owner_id = :u",
        {"u": user.id},
    )
    assert [(float(q), u, a) for q, u, a in harvests] == [(18.0, "kg", ids["apiary"])]
