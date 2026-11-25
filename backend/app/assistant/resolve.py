"""Plain code (no LLM): turn an extracted entry into ids and values, or one question.

"hive 12" -> colony id, "oxalic" -> inventory item, units and dates normalized. Anything
missing, unknown, or ambiguous becomes exactly one question for the user.
"""

import difflib
import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.assistant.catalog import ApiaryRef, Catalog, ColonyRef, ItemRef
from app.assistant.messages import Messages
from app.assistant.schemas import ExtractedEntry

# Words people put around a hive name/number, in English and Romanian.
_HIVE_WORDS = re.compile(
    r"\b(hive|colony|box|number|no|nr|num|stupul|stup|stupului|colonia|colonie|numarul|"
    r"numărul|familia|familie)\b\.?",
    re.IGNORECASE,
)


@dataclass
class Context:
    now: datetime  # device time when known, else server time (aware)
    colony_id: str | None = None
    apiary_id: str | None = None


@dataclass
class Resolution:
    kind: str | None
    fields: dict[str, Any] = field(default_factory=dict)
    missing: str | None = None
    question: str | None = None

    @property
    def complete(self) -> bool:
        return self.missing is None


def _norm(text: str) -> str:
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.sub(r"[^\w\s]", " ", stripped).split())


def match_names[T](ref: str, options: Sequence[T], key: Callable[[T], str]) -> list[T]:
    """Exact, then single containment, then close fuzzy matches (speech recognition typos)."""
    r = _norm(ref)
    if not r:
        return []
    exact = [o for o in options if _norm(key(o)) == r]
    if exact:
        return exact
    contains = [o for o in options if r in _norm(key(o)) or _norm(key(o)) in r]
    if len(contains) == 1:
        return contains
    # Same words in another order ("oxalic acid" vs Romanian "acid oxalic").
    words = set(r.split())
    same_words = [
        o
        for o in options
        if words <= set(_norm(key(o)).split()) or set(_norm(key(o)).split()) <= words
    ]
    if len(same_words) == 1:
        return same_words
    by_name: dict[str, list[T]] = {}
    for o in options:
        by_name.setdefault(_norm(key(o)), []).append(o)
    close = difflib.get_close_matches(r, list(by_name), n=3, cutoff=0.75)
    if close:
        return [o for name in close for o in by_name[name]]
    return contains


def match_colonies(ref: str, colonies: Sequence[ColonyRef]) -> list[ColonyRef]:
    active = [c for c in colonies if c.status == "active"] or list(colonies)
    digits = re.findall(r"\d+", ref)
    if digits:
        n = int(digits[-1])
        hits = [c for c in active if c.number == n]
        if not hits:
            hits = [c for c in active if re.search(rf"(?<!\d){n}(?!\d)", c.label)]
        return hits
    core = _HIVE_WORDS.sub(" ", ref).strip()
    return match_names(core or ref, active, lambda c: c.label)


def parse_unit(raw: str | None) -> str | None:
    if raw is None:
        return None
    r = _norm(raw)
    table = {
        "ml": (
            "ml",
            "milliliter",
            "millilitre",
            "milliliters",
            "millilitres",
            "mililitru",
            "mililitri",
        ),
        "l": ("l", "liter", "litre", "liters", "litres", "litru", "litri"),
        "g": ("g", "gram", "grams", "gramme", "grame"),
        "kg": ("kg", "kilo", "kilos", "kilogram", "kilograms", "kilogramme", "kilograme"),
        "pcs": ("pcs", "piece", "pieces", "pc", "bucata", "bucati", "buc"),
        "strips": ("strips", "strip", "banda", "benzi", "fasie", "fasii"),
        "frames": ("frames", "frame", "rama", "rame"),
    }
    for unit, names in table.items():
        if r in names:
            return unit
    return None


def to_amount(value: float | None) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(format(Decimal(str(value)).quantize(Decimal("0.0001")).normalize(), "f"))
    except InvalidOperation:
        return None
    return amount if amount > 0 else None


def occurred_at(raw: str | None, now: datetime) -> datetime:
    """The spoken day at the current time of day, or now. Future/garbage/>1 year -> now."""
    if not raw:
        return now
    try:
        day = date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return now
    today = now.date()
    if day >= today or day < today - timedelta(days=366):
        return now
    return datetime.combine(day, time(12, 0), tzinfo=now.tzinfo or UTC)


def _options(m: Messages, names: Sequence[str]) -> str:
    joiner = " sau " if m.lang == "ro" else " or "
    names = list(dict.fromkeys(names))[:3]
    return joiner.join(names) if len(names) <= 2 else ", ".join(names[:-1]) + joiner + names[-1]


def _colony_display(m: Messages, c: ColonyRef) -> str:
    if c.apiary_name:
        return f"{c.label} ({c.apiary_name})"
    return c.label


def resolve(
    entry: ExtractedEntry | None, catalog: Catalog, ctx: Context, m: Messages
) -> Resolution:
    def ask(missing: str, **fmt: str) -> Resolution:
        return Resolution(kind=kind, missing=missing, question=m.questions[missing].format(**fmt))

    kind = entry.kind if entry else None
    if entry is None or entry.kind == "unknown":
        return ask("kind")

    f: dict[str, Any] = {"kind": kind}
    when = occurred_at(entry.date, ctx.now)
    f["occurred_at"] = when.isoformat()

    # Hive
    colony: ColonyRef | None = None
    if entry.colony:
        hits = match_colonies(entry.colony, catalog.colonies)
        if len(hits) > 1 and ctx.apiary_id:
            here = [h for h in hits if h.apiary_id == ctx.apiary_id]
            hits = here or hits
        if not hits:
            return ask("colony_not_found", ref=entry.colony)
        if len(hits) > 1:
            return ask(
                "colony_ambiguous", options=_options(m, [_colony_display(m, h) for h in hits])
            )
        colony = hits[0]
    elif ctx.colony_id:
        colony = catalog.colony(ctx.colony_id)
    if kind in ("treatment", "note") and colony is None:
        return ask("colony")
    if colony:
        f["colony_id"], f["colony_label"] = colony.id, colony.label

    # Apiary: where the work happened
    apiary: ApiaryRef | None = None
    if entry.apiary:
        a_hits = match_names(entry.apiary, catalog.apiaries, lambda a: a.name)
        if not a_hits:
            return ask("apiary_not_found", ref=entry.apiary)
        if len(a_hits) > 1:
            return ask("apiary_ambiguous", options=_options(m, [a.name for a in a_hits]))
        apiary = a_hits[0]
    elif colony and colony.apiary_id:
        apiary = ApiaryRef(id=colony.apiary_id, name=colony.apiary_name or "")
    elif ctx.apiary_id:
        apiary = catalog.apiary(ctx.apiary_id)
    if kind in ("treatment", "note", "harvest") and apiary is None:
        return ask("apiary")
    if apiary:
        f["apiary_id"], f["apiary_name"] = apiary.id, apiary.name

    amount = to_amount(entry.amount)
    unit = parse_unit(entry.unit)

    if kind == "treatment":
        if not entry.product:
            return ask("product")
        items = match_names(entry.product, catalog.items, lambda i: i.name)
        item: ItemRef | None = items[0] if len(items) == 1 else None
        f["product_name"] = item.name if item else entry.product.strip()
        f["item_id"] = item.id if item else None
        f["item_unit"] = item.unit if item else None
        if amount is None:
            return ask("amount_treatment")
        unit = unit or (item.unit if item else None)
        if unit is None:
            return ask("unit")

    elif kind == "harvest":
        if amount is None:
            return ask("amount_harvest")
        if unit is None:
            return ask("unit")

    elif kind == "inventory":
        if not entry.product:
            return ask("product_inventory")
        items = match_names(entry.product, catalog.items, lambda i: i.name)
        if len(items) > 1:
            return ask("item_ambiguous", options=_options(m, [i.name for i in items]))
        inv_item = items[0] if items else None
        f["product_name"] = inv_item.name if inv_item else entry.product.strip()
        f["item_id"] = inv_item.id if inv_item else None
        f["item_is_new"] = inv_item is None
        if entry.inventory_action is None:
            return ask("action")
        f["action"] = entry.inventory_action
        if amount is None:
            return ask("amount_inventory")
        unit = unit or (inv_item.unit if inv_item else None)
        if unit is None:
            return ask("unit")
        if inv_item and unit != inv_item.unit:
            # Stock is a sum per item, so it must stay in the item's unit.
            return ask("unit_mismatch", item=inv_item.name, unit=m.units[inv_item.unit][1])

    elif kind == "note":
        text = (entry.note or "").strip() or None
        if entry.queen_seen is None and entry.temperament is None and not text:
            return ask("note")
        f["queen_seen"], f["temperament"], f["text"] = entry.queen_seen, entry.temperament, text

    if amount is not None and kind != "note":
        f["amount"], f["unit"] = str(amount), unit
    if entry.note and kind != "note":
        f["notes"] = entry.note.strip()
    return Resolution(kind=kind, fields=f)
