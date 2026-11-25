from datetime import UTC, datetime

from app.assistant.messages import EN, RO
from app.assistant.resolve import Context, match_colonies, parse_unit, resolve
from tests.voice_helpers import (
    APIVAR,
    CATALOG,
    FOREST,
    HIVE7,
    HIVE12,
    HIVE12_HOME,
    HOME,
    OXALIC,
    entry,
)

NOW = datetime(2026, 11, 25, 9, 30, tzinfo=UTC)


def ctx(**kw: str) -> Context:
    return Context(now=NOW, **kw)


def test_colony_by_number_and_romanian_words() -> None:
    assert {c.id for c in match_colonies("12", CATALOG.colonies)} == {HIVE12, HIVE12_HOME}
    assert [c.id for c in match_colonies("stupul 7", CATALOG.colonies)] == [HIVE7]
    assert [c.id for c in match_colonies("regina ana", CATALOG.colonies)] == [HIVE7]
    assert [c.id for c in match_colonies("Regina Anna", CATALOG.colonies)] == [HIVE7]  # fuzzy


def test_two_hives_numbered_12_ask_which() -> None:
    res = resolve(entry(kind="treatment", colony="12", product="oxalic"), CATALOG, ctx(), RO)
    assert res.missing == "colony_ambiguous"
    assert res.question == "Care dintre ele: Hive 12 (Pădure) sau Stup 12 (Acasă)?"


def test_ambiguity_settled_by_the_apiary_screen() -> None:
    e = entry(kind="treatment", colony="12", product="acid oxalic", amount=5, unit="ml")
    res = resolve(e, CATALOG, ctx(apiary_id=HOME), RO)
    assert res.complete
    assert res.fields["colony_id"] == HIVE12_HOME
    assert res.fields["apiary_id"] == HOME


def test_colony_from_screen_context_and_item_unit() -> None:
    e = entry(kind="treatment", product="Apivar", amount=2)  # no hive, no unit spoken
    res = resolve(e, CATALOG, ctx(colony_id=HIVE7), EN)
    assert res.complete
    f = res.fields
    assert (f["colony_id"], f["apiary_id"]) == (HIVE7, FOREST)
    assert (f["item_id"], f["unit"], f["amount"]) == (APIVAR, "strips", "2")


def test_missing_amount_is_asked_never_guessed() -> None:
    e = entry(kind="treatment", colony="7", product="acid oxalic")
    res = resolve(e, CATALOG, ctx(), RO)
    assert (res.missing, res.question) == ("amount_treatment", "Cât ai folosit?")


def test_unknown_hive() -> None:
    res = resolve(entry(kind="note", colony="99", queen_seen=True), CATALOG, ctx(), EN)
    assert res.question == "I can't find hive 99. Which hive?"


def test_unknown_product_still_saved_as_text() -> None:
    e = entry(kind="treatment", colony="7", product="thymol", amount=10, unit="g")
    res = resolve(e, CATALOG, ctx(), EN)
    assert res.complete
    assert res.fields["item_id"] is None and res.fields["product_name"] == "thymol"


def test_harvest_needs_apiary_and_uses_spoken_one() -> None:
    res = resolve(entry(kind="harvest", amount=18, unit="kg"), CATALOG, ctx(), RO)
    assert (res.missing, res.question) == ("apiary", "Care stupină?")
    res = resolve(entry(kind="harvest", apiary="padure", amount=18, unit="kg"), CATALOG, ctx(), RO)
    assert res.complete and res.fields["apiary_id"] == FOREST


def test_inventory_new_item_and_unit_mismatch() -> None:
    e = entry(kind="inventory", product="zahăr", inventory_action="purchase", amount=10, unit="kg")
    res = resolve(e, CATALOG, ctx(), RO)
    assert res.complete and res.fields["item_is_new"] is True

    e = entry(
        kind="inventory", product="acid oxalic", inventory_action="purchase", amount=2, unit="l"
    )
    res = resolve(e, CATALOG, ctx(), RO)
    assert res.missing == "unit_mismatch"
    assert res.question == "Acid oxalic se numără în mililitri. Cât înseamnă asta în mililitri?"

    e = entry(kind="inventory", product="acid oxalic", amount=500, unit="ml")
    assert resolve(e, CATALOG, ctx(), EN).missing == "action"


def test_note_needs_content() -> None:
    assert resolve(entry(kind="note", colony="7"), CATALOG, ctx(), EN).missing == "note"


def test_dates() -> None:
    e = entry(kind="note", colony="7", queen_seen=True, date="2026-11-24")
    assert resolve(e, CATALOG, ctx(), EN).fields["occurred_at"].startswith("2026-11-24T12:00")
    for bad in ("2026-12-01", "garbage", "2024-01-01"):  # future, junk, >1 year ago -> now
        e = entry(kind="note", colony="7", queen_seen=True, date=bad)
        assert resolve(e, CATALOG, ctx(), EN).fields["occurred_at"] == NOW.isoformat()


def test_unknown_kind_asks_what_to_record() -> None:
    assert resolve(entry(kind="unknown"), CATALOG, ctx(), RO).question.startswith("Ce vrei")
    assert resolve(None, CATALOG, ctx(), EN).missing == "kind"


def test_parse_unit_words() -> None:
    assert parse_unit("mililitri") == "ml"
    assert parse_unit("Benzi") == "strips"
    assert parse_unit("ml") == "ml"
    assert parse_unit("bushels") is None


def test_oxalic_matches_known_item() -> None:
    e = entry(kind="treatment", colony="7", product="oxalic acid", amount=5, unit="ml")
    res = resolve(e, CATALOG, ctx(), EN)
    assert res.fields["item_id"] == OXALIC
