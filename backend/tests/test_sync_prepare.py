"""Validation of upload ops (no database needed)."""

import uuid
from typing import Any

import pytest

from app.auth.jwt import CurrentUser
from app.models.schemas.sync import CrudOp
from app.services.errors import OpRejected
from app.services.sync import prepare_op

NOW = "2026-11-19T10:00:00Z"


@pytest.fixture
def user() -> CurrentUser:
    return CurrentUser(id=uuid.uuid4(), role="authenticated")


def op(op_type: str, table: str, data: dict[str, Any] | None = None, **kw: Any) -> CrudOp:
    return CrudOp(op=op_type, table=table, id=kw.get("id", uuid.uuid4()), data=data)


def test_unknown_table_rejected(user: CurrentUser) -> None:
    with pytest.raises(OpRejected, match="unknown table"):
        prepare_op(op("PUT", "secrets", {"client_updated_at": NOW}), user)


def test_unknown_column_rejected(user: CurrentUser) -> None:
    data = {"label": "Hive 1", "client_updated_at": NOW, "is_admin": True}
    with pytest.raises(OpRejected, match="is_admin"):
        prepare_op(op("PUT", "colonies", data), user)


def test_server_managed_fields_are_ignored(user: CurrentUser) -> None:
    other = str(uuid.uuid4())
    data = {
        "label": "Hive 12",
        "number": 12,
        "client_updated_at": NOW,
        "owner_id": other,
        "created_at": NOW,
        "updated_at": NOW,
        "id": other,
    }
    p = prepare_op(op("PUT", "colonies", data), user)
    assert "owner_id" not in p.values and "id" not in p.values
    assert p.values["label"] == "Hive 12"
    assert p.values["mode"] == "stationary"  # PUT fills defaults


def test_client_updated_at_required_and_timezone_aware(user: CurrentUser) -> None:
    with pytest.raises(OpRejected, match="client_updated_at"):
        prepare_op(op("PUT", "colonies", {"label": "Hive 1"}), user)
    with pytest.raises(OpRejected, match="client_updated_at"):
        prepare_op(
            op("PUT", "colonies", {"label": "x", "client_updated_at": "2026-11-19T10:00:00"}), user
        )


def test_enum_values_checked(user: CurrentUser) -> None:
    data = {"label": "Hive 1", "status": "on_holiday", "client_updated_at": NOW}
    with pytest.raises(OpRejected, match="status"):
        prepare_op(op("PUT", "colonies", data), user)


def test_patch_only_contains_sent_fields(user: CurrentUser) -> None:
    p = prepare_op(op("PATCH", "colonies", {"status": "dead", "client_updated_at": NOW}), user)
    assert set(p.values) == {"status", "client_updated_at"}


def test_patch_keeps_field_constraints(user: CurrentUser) -> None:
    with pytest.raises(OpRejected, match="label"):
        prepare_op(op("PATCH", "colonies", {"label": "", "client_updated_at": NOW}), user)


def test_apiary_lat_lng_become_location(user: CurrentUser) -> None:
    data = {"name": "Forest edge", "lat": 46.77, "lng": 23.59, "client_updated_at": NOW}
    p = prepare_op(op("PUT", "apiaries", data), user)
    assert "lat" not in p.values and "lng" not in p.values
    assert p.values["location"] is not None
    assert p.client_payload["lat"] == 46.77


def test_apiary_needs_both_coordinates(user: CurrentUser) -> None:
    with pytest.raises(OpRejected, match="lat and lng"):
        prepare_op(
            op("PUT", "apiaries", {"name": "A", "lat": 46.7, "client_updated_at": NOW}), user
        )
    with pytest.raises(OpRejected, match="lat and lng"):
        prepare_op(op("PATCH", "apiaries", {"lng": 23.5, "client_updated_at": NOW}), user)


def test_apiary_without_location(user: CurrentUser) -> None:
    p = prepare_op(op("PUT", "apiaries", {"name": "Home", "client_updated_at": NOW}), user)
    assert p.values["location"] is None


def test_placement_dates_must_be_ordered(user: CurrentUser) -> None:
    data = {
        "colony_id": str(uuid.uuid4()),
        "apiary_id": str(uuid.uuid4()),
        "started_at": "2026-06-10T08:00:00Z",
        "ended_at": "2026-06-01T08:00:00Z",
        "client_updated_at": NOW,
    }
    with pytest.raises(OpRejected, match="ended_at"):
        prepare_op(op("PUT", "colony_placements", data), user)


def test_profile_only_own_and_no_delete(user: CurrentUser) -> None:
    data = {"locale": "ro-RO", "client_updated_at": NOW}
    p = prepare_op(op("PATCH", "profiles", data, id=user.id), user)
    assert p.values["locale"] == "ro-RO"
    with pytest.raises(OpRejected, match="not found"):
        prepare_op(op("PATCH", "profiles", data), user)
    with pytest.raises(OpRejected, match="not allowed"):
        prepare_op(op("DELETE", "profiles", id=user.id), user)


def test_delete_needs_no_data(user: CurrentUser) -> None:
    p = prepare_op(op("DELETE", "colonies"), user)
    assert p.values == {}


def test_treatment_needs_positive_amount_and_known_unit(user: CurrentUser) -> None:
    base = {
        "colony_id": str(uuid.uuid4()),
        "apiary_id": str(uuid.uuid4()),
        "product_name": "Oxalic acid",
        "amount": 5,
        "unit": "ml",
        "treated_at": NOW,
        "client_updated_at": NOW,
    }
    p = prepare_op(op("PUT", "treatments", base), user)
    assert p.values["source"] == "manual"
    with pytest.raises(OpRejected, match="amount"):
        prepare_op(op("PUT", "treatments", {**base, "amount": 0}), user)
    with pytest.raises(OpRejected, match="unit"):
        prepare_op(op("PUT", "treatments", {**base, "unit": "spoons"}), user)


def test_empty_colony_note_rejected(user: CurrentUser) -> None:
    data = {
        "colony_id": str(uuid.uuid4()),
        "apiary_id": str(uuid.uuid4()),
        "noted_at": NOW,
        "client_updated_at": NOW,
    }
    with pytest.raises(OpRejected, match="note needs"):
        prepare_op(op("PUT", "colony_notes", data), user)


def test_voice_note_from_device(user: CurrentUser) -> None:
    data = {"transcript": "Stupul 12, acid oxalic", "locale": "ro-RO", "client_updated_at": NOW}
    p = prepare_op(op("PUT", "voice_notes", data), user)
    assert p.values["status"] == "pending"


def test_accepts_powersync_client_formats(user: CurrentUser) -> None:
    """PowerSync gives the phone timestamptz as 'YYYY-MM-DD hh:mm:ss.sssZ', numeric as text
    and booleans as 0/1; the phone uploads rows in that same shape."""
    data = {
        "colony_id": str(uuid.uuid4()),
        "apiary_id": str(uuid.uuid4()),
        "noted_at": "2026-11-25 09:30:00.000Z",
        "queen_seen": 1,
        "temperament": "calm",
        "text": None,
        "source": "manual",
        "client_updated_at": "2026-11-25 09:30:00.123Z",
        "deleted_at": None,
        "owner_id": str(user.id),
        "created_at": "2026-11-25 09:30:00.000Z",
        "updated_at": "2026-11-25 09:30:00.000Z",
    }
    p = prepare_op(op("PUT", "colony_notes", data), user)
    assert p.values["queen_seen"] is True
    assert p.values["client_updated_at"].microsecond == 123000
    t = {
        "colony_id": str(uuid.uuid4()),
        "apiary_id": str(uuid.uuid4()),
        "product_name": "Acid oxalic",
        "amount": "5.5",
        "unit": "ml",
        "treated_at": "2026-11-25 09:30:00.000Z",
        "client_updated_at": "2026-11-25 09:30:00.000Z",
    }
    assert str(prepare_op(op("PUT", "treatments", t), user).values["amount"]) == "5.5"
