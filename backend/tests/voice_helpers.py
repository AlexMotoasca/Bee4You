"""Shared fakes for voice tests: a catalog and a scripted extractor (no Groq calls)."""

from typing import Any

from app.assistant.catalog import ApiaryRef, Catalog, ColonyRef, ItemRef
from app.assistant.llm import ExtractRequest
from app.assistant.schemas import ExtractedEntry

FOREST = "11111111-1111-1111-1111-111111111111"
HOME = "22222222-2222-2222-2222-222222222222"
HIVE12 = "aaaaaaaa-0000-0000-0000-000000000012"
HIVE12_HOME = "aaaaaaaa-0000-0000-0000-000000001012"
HIVE7 = "aaaaaaaa-0000-0000-0000-000000000007"
OXALIC = "bbbbbbbb-0000-0000-0000-000000000001"
APIVAR = "bbbbbbbb-0000-0000-0000-000000000002"

CATALOG = Catalog(
    colonies=[
        ColonyRef(HIVE12, "Hive 12", 12, "active", FOREST, "Pădure"),
        ColonyRef(HIVE12_HOME, "Stup 12", 12, "active", HOME, "Acasă"),
        ColonyRef(HIVE7, "Regina Ana", 7, "active", FOREST, "Pădure"),
    ],
    apiaries=[ApiaryRef(FOREST, "Pădure"), ApiaryRef(HOME, "Acasă")],
    items=[
        ItemRef(OXALIC, "Acid oxalic", "ml", "treatment"),
        ItemRef(APIVAR, "Apivar", "strips", "treatment"),
    ],
)


def entry(**fields: Any) -> ExtractedEntry:
    base: dict[str, Any] = {
        "kind": "unknown",
        "colony": None,
        "apiary": None,
        "product": None,
        "amount": None,
        "unit": None,
        "inventory_action": None,
        "queen_seen": None,
        "temperament": None,
        "note": None,
        "date": None,
    }
    base.update(fields)
    return ExtractedEntry.model_validate(base)


class ScriptedExtractor:
    """Returns the given entries in order (the last one repeats); records every request."""

    def __init__(self, *entries: ExtractedEntry | Exception) -> None:
        self.entries = list(entries)
        self.requests: list[ExtractRequest] = []

    async def __call__(self, request: ExtractRequest) -> ExtractedEntry:
        self.requests.append(request)
        item = self.entries[min(len(self.requests), len(self.entries)) - 1]
        if isinstance(item, Exception):
            raise item
        return item
