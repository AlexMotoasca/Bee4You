"""Everything the assistant says, per language. Templated (not LLM-written) so read-backs
are predictable. Add a language by adding a `Messages` instance to LANGUAGES."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Messages:
    lang: str
    questions: dict[str, str]
    units: dict[str, tuple[str, str]]  # unit -> (singular, plural)
    months: tuple[str, ...]
    today: str
    yesterday: str
    on_date: str  # "{day} {month}"
    decimal_sep: str
    saved: str
    cancelled: str
    too_many: str
    save_question: str
    summary: dict[str, str]
    queen_seen: str
    queen_not_seen: str
    temperaments: dict[str, str]
    new_item: str
    from_colony: str
    actions: dict[str, str]
    yes_words: frozenset[str] = field(default_factory=frozenset)
    no_words: frozenset[str] = field(default_factory=frozenset)
    cancel_words: frozenset[str] = field(default_factory=frozenset)


EN = Messages(
    lang="en",
    questions={
        "not_understood": "Sorry, I didn't catch that. Please say it again.",
        "kind": "What would you like to record: a treatment, a harvest, an inventory change, "
        "or a note?",
        "colony": "Which hive?",
        "colony_not_found": "I can't find hive {ref}. Which hive?",
        "colony_ambiguous": "Which one: {options}?",
        "apiary": "Which apiary?",
        "apiary_not_found": "I can't find the apiary {ref}. Which apiary?",
        "apiary_ambiguous": "Which apiary: {options}?",
        "product": "Which product did you use?",
        "product_inventory": "Which item?",
        "item_ambiguous": "Which item: {options}?",
        "amount_treatment": "How much did you use?",
        "amount_harvest": "How much did you harvest?",
        "amount_inventory": "How much?",
        "unit": "In what unit? For example millilitres, grams, or strips.",
        "action": "Did you buy it, or use it up?",
        "note": "What would you like to note?",
        "change": "What should I change?",
        "unit_mismatch": "{item} is counted in {unit}. How much is that in {unit}?",
    },
    units={
        "ml": ("millilitre", "millilitres"),
        "l": ("litre", "litres"),
        "g": ("gram", "grams"),
        "kg": ("kilogram", "kilograms"),
        "pcs": ("piece", "pieces"),
        "strips": ("strip", "strips"),
        "frames": ("frame", "frames"),
    },
    months=(
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
    today="today",
    yesterday="yesterday",
    on_date="on {day} {month}",
    decimal_sep=".",
    saved="Saved.",
    cancelled="Cancelled. Nothing was saved.",
    too_many="Let's start over. Nothing was saved.",
    save_question="Save it?",
    summary={
        "treatment": "Treatment for {colony}: {product}, {amount}, {when}.",
        "harvest": "Harvest at {apiary}{colony_part}: {amount}, {when}.",
        "inventory": "{action} {amount} of {product}{new}, {when}.",
        "note": "Note for {colony}: {details}, {when}.",
    },
    queen_seen="queen seen",
    queen_not_seen="queen not seen",
    temperaments={"calm": "calm", "nervous": "nervous", "aggressive": "aggressive"},
    new_item=" (new item)",
    from_colony=", from {colony}",
    actions={"purchase": "Bought", "used": "Used"},
    yes_words=frozenset(
        {
            "yes",
            "yeah",
            "yep",
            "yup",
            "correct",
            "right",
            "ok",
            "okay",
            "sure",
            "save",
            "save it",
            "confirm",
            "yes please",
            "that's right",
            "thats right",
            "yes save",
        }
    ),
    no_words=frozenset({"no", "nope", "wrong", "incorrect", "not right", "no it's not"}),
    cancel_words=frozenset(
        {
            "cancel",
            "stop",
            "forget it",
            "never mind",
            "nevermind",
            "cancel it",
            "abort",
        }
    ),
)

RO = Messages(
    lang="ro",
    questions={
        "not_understood": "Scuze, nu am înțeles. Te rog să repeți.",
        "kind": "Ce vrei să înregistrezi: un tratament, o recoltă, o modificare de stoc "
        "sau o notă?",
        "colony": "Care stup?",
        "colony_not_found": "Nu găsesc stupul {ref}. Care stup?",
        "colony_ambiguous": "Care dintre ele: {options}?",
        "apiary": "Care stupină?",
        "apiary_not_found": "Nu găsesc stupina {ref}. Care stupină?",
        "apiary_ambiguous": "Care stupină: {options}?",
        "product": "Ce produs ai folosit?",
        "product_inventory": "Ce articol?",
        "item_ambiguous": "Care articol: {options}?",
        "amount_treatment": "Cât ai folosit?",
        "amount_harvest": "Cât ai recoltat?",
        "amount_inventory": "Ce cantitate?",
        "unit": "În ce unitate? De exemplu mililitri, grame sau benzi.",
        "action": "L-ai cumpărat sau l-ai folosit?",
        "note": "Ce vrei să notezi?",
        "change": "Ce să modific?",
        "unit_mismatch": "{item} se numără în {unit}. Cât înseamnă asta în {unit}?",
    },
    units={
        "ml": ("mililitru", "mililitri"),
        "l": ("litru", "litri"),
        "g": ("gram", "grame"),
        "kg": ("kilogram", "kilograme"),
        "pcs": ("bucată", "bucăți"),
        "strips": ("bandă", "benzi"),
        "frames": ("ramă", "rame"),
    },
    months=(
        "ianuarie",
        "februarie",
        "martie",
        "aprilie",
        "mai",
        "iunie",
        "iulie",
        "august",
        "septembrie",
        "octombrie",
        "noiembrie",
        "decembrie",
    ),
    today="azi",
    yesterday="ieri",
    on_date="pe {day} {month}",
    decimal_sep=",",
    saved="Salvat.",
    cancelled="Anulat. Nu am salvat nimic.",
    too_many="Hai s-o luăm de la capăt. Nu am salvat nimic.",
    save_question="Salvez?",
    summary={
        "treatment": "Tratament pentru {colony}: {product}, {amount}, {when}.",
        "harvest": "Recoltă la {apiary}{colony_part}: {amount}, {when}.",
        "inventory": "{action} {amount} de {product}{new}, {when}.",
        "note": "Notă pentru {colony}: {details}, {when}.",
    },
    queen_seen="matca văzută",
    queen_not_seen="matca nevăzută",
    temperaments={"calm": "calmă", "nervous": "agitată", "aggressive": "agresivă"},
    new_item=" (articol nou)",
    from_colony=", din {colony}",
    actions={"purchase": "Cumpărat", "used": "Folosit"},
    yes_words=frozenset(
        {
            "da",
            "corect",
            "salveaza",
            "salvează",
            "sigur",
            "ok",
            "bine",
            "confirm",
            "da salveaza",
            "da salvează",
            "e corect",
            "este corect",
            "exact",
            "da te rog",
        }
    ),
    no_words=frozenset({"nu", "gresit", "greșit", "nu e corect", "nu este corect", "incorect"}),
    cancel_words=frozenset(
        {
            "anuleaza",
            "anulează",
            "renunta",
            "renunță",
            "stop",
            "lasa",
            "lasă",
            "las-o",
            "lasa baltă",
            "lasă baltă",
        }
    ),
)

LANGUAGES = {m.lang: m for m in (EN, RO)}


def for_locale(locale: str | None) -> Messages:
    lang = (locale or "en").split("-")[0].split("_")[0].lower()
    return LANGUAGES.get(lang, EN)


def format_amount(m: Messages, amount: Decimal, unit: str) -> str:
    normalized = amount.normalize()
    text = format(normalized, "f").replace(".", m.decimal_sep)
    singular, plural = m.units.get(unit, (unit, unit))
    word = singular if normalized == 1 else plural
    if m.lang == "ro" and normalized == normalized.to_integral_value():
        n = int(normalized)
        if n % 100 >= 20 or (n >= 100 and n % 100 == 0):
            return f"{text} de {word}"  # "25 de mililitri"
    return f"{text} {word}"


def format_day(m: Messages, day: date, today: date) -> str:
    if day == today:
        return m.today
    if (today - day).days == 1:
        return m.yesterday
    return m.on_date.format(day=day.day, month=m.months[day.month - 1])


_PUNCT = re.compile(r"[^\w\s']", re.UNICODE)


def normalize_answer(text: str) -> str:
    return " ".join(_PUNCT.sub(" ", text.casefold()).split())


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def classify_answer(text: str) -> str:
    """Return 'yes', 'no', 'cancel', or 'correction' for a reply to the confirmation.

    Words from every language are accepted, so a Romanian speaker saying "ok" or an English
    UI with "da" both work. Anything longer than a short yes/no is treated as a correction.
    """
    norm = normalize_answer(text)
    plain = _strip_accents(norm)
    words = plain.split()

    def in_any(attr: str) -> bool:
        return any(
            norm in getattr(m, attr) or plain in {_strip_accents(w) for w in getattr(m, attr)}
            for m in LANGUAGES.values()
        )

    if not words:
        return "correction"
    if in_any("cancel_words"):
        return "cancel"
    if in_any("yes_words"):
        return "yes"
    if in_any("no_words"):
        return "no"
    if (
        len(words) <= 3
        and words[0] in {"yes", "da", "ok", "okay", "yeah", "yep"}
        and not any(w in {"no", "nu", "not", "but", "dar"} for w in words)
    ):
        return "yes"
    return "correction"


def is_cancel(text: str) -> bool:
    return classify_answer(text) == "cancel"


def summarize(m: Messages, f: dict[str, Any], today: date) -> str:
    """Spoken read-back of a complete entry. Amounts and units are always included."""
    kind = f["kind"]
    when = format_day(m, datetime.fromisoformat(f["occurred_at"]).date(), today)
    amount = format_amount(m, Decimal(f["amount"]), f["unit"]) if "amount" in f else ""
    if kind == "treatment":
        text = m.summary["treatment"].format(
            colony=f["colony_label"], product=f["product_name"], amount=amount, when=when
        )
    elif kind == "harvest":
        colony_part = m.from_colony.format(colony=f["colony_label"]) if f.get("colony_id") else ""
        text = m.summary["harvest"].format(
            apiary=f["apiary_name"], colony_part=colony_part, amount=amount, when=when
        )
    elif kind == "inventory":
        text = m.summary["inventory"].format(
            action=m.actions[f["action"]],
            amount=amount,
            product=f["product_name"],
            new=m.new_item if f.get("item_is_new") else "",
            when=when,
        )
    else:
        details = []
        if f.get("queen_seen") is not None:
            details.append(m.queen_seen if f["queen_seen"] else m.queen_not_seen)
        if f.get("temperament"):
            details.append(m.temperaments[f["temperament"]])
        if f.get("text"):
            details.append(f["text"])
        text = m.summary["note"].format(
            colony=f["colony_label"], details=", ".join(details), when=when
        )
    return f"{text} {m.save_question}"
