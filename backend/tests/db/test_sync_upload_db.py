"""Sync upload against the real database: idempotency, last-write-wins, RLS, placements.

Run with: uv run pytest --db
"""

import httpx
import pytest

from app.api.deps import get_current_user
from app.main import create_app
from tests.db.conftest import new_id, ts

pytestmark = pytest.mark.db


def colony_put(cid: str, label: str = "Hive 12", at: int = 0, **extra) -> dict:
    data = {"label": label, "number": 12, "client_updated_at": ts(at), **extra}
    return {"op": "PUT", "table": "colonies", "id": cid, "data": data}


def apiary_put(aid: str, name: str = "Forest edge", at: int = 0, **extra) -> dict:
    data = {"name": name, "client_updated_at": ts(at), **extra}
    return {"op": "PUT", "table": "apiaries", "id": aid, "data": data}


def placement_put(pid: str, cid: str, aid: str, started: int, at: int = 0, **extra) -> dict:
    data = {
        "colony_id": cid,
        "apiary_id": aid,
        "started_at": ts(started),
        "client_updated_at": ts(at),
        **extra,
    }
    return {"op": "PUT", "table": "colony_placements", "id": pid, "data": data}


async def test_profile_created_on_signup_and_patchable(make_user, upload, admin) -> None:
    user = await make_user()
    rows = await admin("select locale from public.profiles where id = :id", {"id": user.id})
    assert rows == [("en-US",)]

    patch = {"locale": "ro-RO", "client_updated_at": ts(1)}
    [r] = await upload(
        user, [{"op": "PATCH", "table": "profiles", "id": str(user.id), "data": patch}]
    )
    assert r.status == "applied", r.error
    rows = await admin("select locale from public.profiles where id = :id", {"id": user.id})
    assert rows == [("ro-RO",)]


async def test_replayed_batch_creates_one_row(make_user, upload, admin) -> None:
    user = await make_user()
    cid = new_id()
    batch = [colony_put(cid)]
    first = await upload(user, batch)
    again = await upload(user, batch)  # dropped connection → device retries
    assert [r.status for r in first + again] == ["applied", "applied"]
    rows = await admin("select count(*) from public.colonies where id = :id", {"id": cid})
    assert rows[0][0] == 1


async def test_owner_comes_from_token_not_payload(make_user, upload, admin) -> None:
    user, other = await make_user(), await make_user()
    cid = new_id()
    [r] = await upload(user, [colony_put(cid, owner_id=str(other.id))])
    assert r.status == "applied", r.error
    rows = await admin("select owner_id from public.colonies where id = :id", {"id": cid})
    assert rows[0][0] == user.id


async def test_older_edit_loses_and_is_logged(make_user, upload, admin) -> None:
    user = await make_user()
    cid = new_id()
    await upload(user, [colony_put(cid, label="Newer", at=10)])

    [put] = await upload(user, [colony_put(cid, label="Older PUT", at=5)])
    older_patch = {"label": "Older PATCH", "client_updated_at": ts(6)}
    [patch] = await upload(
        user, [{"op": "PATCH", "table": "colonies", "id": cid, "data": older_patch}]
    )
    assert put.status == "conflict" and put.conflict_id is not None
    assert patch.status == "conflict" and patch.conflict_id is not None

    rows = await admin("select label from public.colonies where id = :id", {"id": cid})
    assert rows == [("Newer",)]
    conflicts = await admin(
        "select client_payload->>'label', server_payload->>'label' from public.sync_conflicts"
        " where record_id = :id order by created_at",
        {"id": cid},
    )
    assert sorted(conflicts) == [("Older PATCH", "Newer"), ("Older PUT", "Newer")]

    newer_patch = {"label": "Newest", "client_updated_at": ts(20)}
    [ok] = await upload(
        user, [{"op": "PATCH", "table": "colonies", "id": cid, "data": newer_patch}]
    )
    assert ok.status == "applied"
    rows = await admin("select label from public.colonies where id = :id", {"id": cid})
    assert rows == [("Newest",)]


async def test_bad_op_does_not_block_the_batch(make_user, upload, admin) -> None:
    user = await make_user()
    good1, good2 = new_id(), new_id()
    results = await upload(
        user,
        [
            colony_put(good1, label="One"),
            colony_put(new_id(), label=""),  # invalid
            {
                "op": "PATCH",
                "table": "colonies",
                "id": new_id(),
                "data": {"client_updated_at": ts()},
            },
            colony_put(good2, label="Two"),
        ],
    )
    assert [r.status for r in results] == ["applied", "rejected", "rejected", "applied"]
    assert results[2].error == "record not found"
    rows = await admin("select count(*) from public.colonies where owner_id = :u", {"u": user.id})
    assert rows[0][0] == 2


async def test_users_cannot_touch_each_other(make_user, upload, admin) -> None:
    alice, bob = await make_user(), await make_user()
    cid, aid = new_id(), new_id()
    await upload(alice, [colony_put(cid, label="Alice's hive"), apiary_put(aid)])

    # Bob reuses Alice's id: blocked by RLS, not silently overwritten.
    [put] = await upload(bob, [colony_put(cid, label="Bob's takeover", at=99)])
    patch_data = {"label": "Bob's patch", "client_updated_at": ts(99)}
    [patch] = await upload(
        bob, [{"op": "PATCH", "table": "colonies", "id": cid, "data": patch_data}]
    )
    [delete] = await upload(bob, [{"op": "DELETE", "table": "colonies", "id": cid}])
    # Bob links a placement to Alice's colony and apiary.
    [link] = await upload(bob, [placement_put(new_id(), cid, aid, started=0)])

    assert put.status == "rejected"
    assert patch.status == "rejected" and patch.error == "record not found"
    assert delete.status == "applied"  # no-op: Bob can't see the row
    assert link.status == "rejected"

    rows = await admin("select label, deleted_at from public.colonies where id = :id", {"id": cid})
    assert rows == [("Alice's hive", None)]
    bob_rows = await admin(
        "select count(*) from public.colony_placements where owner_id = :u", {"u": bob.id}
    )
    assert bob_rows[0][0] == 0


async def test_apiary_location_round_trip(make_user, upload, admin) -> None:
    user = await make_user()
    aid = new_id()
    [r] = await upload(user, [apiary_put(aid, lat=46.7712, lng=23.6236)])
    assert r.status == "applied", r.error
    rows = await admin(
        "select round(st_y(location::extensions.geometry)::numeric, 4),"
        " round(st_x(location::extensions.geometry)::numeric, 4)"
        " from public.apiaries where id = :id",
        {"id": aid},
    )
    assert [tuple(float(v) for v in row) for row in rows] == [(46.7712, 23.6236)]

    [clear] = await upload(
        user,
        [
            {
                "op": "PATCH",
                "table": "apiaries",
                "id": aid,
                "data": {"lat": None, "lng": None, "client_updated_at": ts(1)},
            }
        ],
    )
    assert clear.status == "applied", clear.error
    rows = await admin("select location is null from public.apiaries where id = :id", {"id": aid})
    assert rows == [(True,)]


async def test_soft_delete_is_idempotent(make_user, upload, admin) -> None:
    user = await make_user()
    cid = new_id()
    await upload(user, [colony_put(cid)])
    delete = {"op": "DELETE", "table": "colonies", "id": cid}
    results = await upload(user, [delete, delete])
    assert [r.status for r in results] == ["applied", "applied"]
    rows = await admin(
        "select deleted_at is not null from public.colonies where id = :id", {"id": cid}
    )
    assert rows == [(True,)]


async def test_move_keeps_history_and_one_open_placement(make_user, upload, admin) -> None:
    user = await make_user()
    cid, home, field, meadow = new_id(), new_id(), new_id(), new_id()
    p_home, p_field, p_meadow = new_id(), new_id(), new_id()
    await upload(user, [colony_put(cid), apiary_put(home), apiary_put(field), apiary_put(meadow)])

    # Device A: colony at home from t=0, moved to the field at t=100 (open placement, no close op).
    results = await upload(
        user,
        [
            placement_put(p_home, cid, home, started=0),
            placement_put(p_field, cid, field, started=100),
        ],
    )
    assert [r.status for r in results] == ["applied", "applied"], [r.error for r in results]

    # Device B was offline and recorded a move to the meadow at t=50: it becomes history.
    [late] = await upload(user, [placement_put(p_meadow, cid, meadow, started=50)])
    assert late.status == "applied", late.error

    rows = await admin(
        "select apiary_id::text, started_at, ended_at from public.colony_placements"
        " where colony_id = :c order by started_at",
        {"c": cid},
    )
    assert [r[0] for r in rows] == [home, meadow, field]
    (_, s_home, e_home), (_, s_meadow, e_meadow), (_, s_field, e_field) = rows
    assert e_home == s_meadow  # late move still cuts the home stay at the right time
    assert e_meadow == s_field  # meadow stay ends when the field placement starts
    assert e_field is None  # field is the current site
    open_count = sum(1 for r in rows if r[2] is None)
    assert open_count == 1


async def test_upload_endpoint_commits(make_user, admin) -> None:
    user = await make_user()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    cid = new_id()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post("/v1/sync/upload", json={"ops": [colony_put(cid)]})
    assert r.status_code == 200
    assert r.json()["results"][0]["status"] == "applied"
    rows = await admin("select count(*) from public.colonies where id = :id", {"id": cid})
    assert rows[0][0] == 1
