from datetime import date
from decimal import Decimal

import pytest

from app.assistant.messages import EN, RO, classify_answer, for_locale, format_amount, summarize


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("yes", "yes"),
        ("Yes, save it.", "yes"),
        ("da", "yes"),
        ("Da!", "yes"),
        ("Da, salvează", "yes"),
        ("corect", "yes"),
        ("ok", "yes"),
        ("no", "no"),
        ("Nu.", "no"),
        ("greșit", "no"),
        ("gresit", "no"),
        ("cancel", "cancel"),
        ("anulează", "cancel"),
        ("anuleaza", "cancel"),
        ("renunță", "cancel"),
        ("no, 15 ml", "correction"),
        ("nu, 50 de mililitri", "correction"),
        ("da dar stupul 7", "correction"),
        ("it was hive 7", "correction"),
    ],
)
def test_classify_answer(text: str, expected: str) -> None:
    assert classify_answer(text) == expected


def test_locale_picks_language() -> None:
    assert for_locale("ro-RO") is RO
    assert for_locale("ro") is RO
    assert for_locale("en-GB") is EN
    assert for_locale("de-DE") is EN  # fallback
    assert for_locale(None) is EN


@pytest.mark.parametrize(
    ("amount", "unit", "ro", "en"),
    [
        ("5", "ml", "5 mililitri", "5 millilitres"),
        ("1", "strips", "1 bandă", "1 strip"),
        ("2.5", "l", "2,5 litri", "2.5 litres"),
        ("25", "ml", "25 de mililitri", "25 millilitres"),
        ("18", "kg", "18 kilograme", "18 kilograms"),
        ("100", "g", "100 de grame", "100 grams"),
        ("101", "g", "101 grame", "101 grams"),
    ],
)
def test_format_amount(amount: str, unit: str, ro: str, en: str) -> None:
    assert format_amount(RO, Decimal(amount), unit) == ro
    assert format_amount(EN, Decimal(amount), unit) == en


def test_summary_reads_back_amount_in_romanian() -> None:
    fields = {
        "kind": "treatment",
        "colony_label": "Hive 12",
        "product_name": "Acid oxalic",
        "amount": "5",
        "unit": "ml",
        "occurred_at": "2026-11-24T09:00:00+00:00",
    }
    text = summarize(RO, fields, today=date(2026, 11, 25))
    assert text == "Tratament pentru Hive 12: Acid oxalic, 5 mililitri, ieri. Salvez?"


def test_note_summary_english() -> None:
    fields = {
        "kind": "note",
        "colony_label": "Hive 12",
        "queen_seen": True,
        "temperament": "calm",
        "text": None,
        "occurred_at": "2026-06-03T12:00:00+00:00",
    }
    text = summarize(EN, fields, today=date(2026, 11, 25))
    assert text == "Note for Hive 12: queen seen, calm, on 3 June. Save it?"
