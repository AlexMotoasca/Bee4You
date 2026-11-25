"""The conversation graph across simulated requests: state is dumped to JSON and reloaded
between turns, exactly like voice_sessions rows."""

import json
from typing import Any

from langgraph.types import Command

from app.assistant.catalog import Catalog
from app.assistant.graph import VoiceDeps, VoiceState, build_graph
from app.assistant.llm import ExtractionFailed
from app.assistant.store import ThreadStore
from tests.voice_helpers import CATALOG, HIVE7, OXALIC, ScriptedExtractor, entry

THREAD = "thread-1"


class Harness:
    def __init__(self, extractor: ScriptedExtractor, max_questions: int = 6) -> None:
        self.extractor = extractor
        self.saved: list[VoiceState] = []
        self.data: dict[str, Any] | None = None
        self.max_questions = max_questions

    async def _catalog(self) -> Catalog:
        return CATALOG

    async def _save(self, state: VoiceState) -> dict[str, str]:
        self.saved.append(state)
        return {"table": "treatments", "id": state["ids"]["record"]}

    async def turn(self, graph_input: Any) -> dict[str, Any]:
        store = ThreadStore(THREAD)
        if self.data is not None:
            store.load(self.data)
        deps = VoiceDeps(self.extractor, self._catalog, self._save, self.max_questions)
        result = await build_graph(deps, store.saver).ainvoke(graph_input, store.config)
        self.data = json.loads(json.dumps(store.dump()))  # must survive a JSON round trip
        out = dict(result)
        interrupts = out.pop("__interrupt__", [])
        return {"pending": interrupts[0].value if interrupts else None, "state": out}

    async def start(self, text: str, locale: str = "ro-RO", **ctx: str) -> dict[str, Any]:
        return await self.turn(
            {
                "owner_id": "user-1",
                "locale": locale,
                "now": "2026-11-25T09:30:00+00:00",
                "context_colony_id": ctx.get("colony"),
                "context_apiary_id": ctx.get("apiary"),
                "ids": {"record": "r-1", "adjustment": "a-1", "item": "i-1"},
                "messages": [{"role": "user", "text": text}],
                "entry": None,
                "questions_asked": 0,
                "status": "running",
            }
        )

    async def reply(self, text: str) -> dict[str, Any]:
        return await self.turn(Command(resume=text))


async def test_romanian_follow_up_question_then_confirm_and_save() -> None:
    extractor = ScriptedExtractor(
        entry(kind="treatment", colony="7", product="acid oxalic"),
        entry(kind="treatment", colony="7", product="acid oxalic", amount=5, unit="ml"),
    )
    h = Harness(extractor)

    t1 = await h.start("Stupul 7, acid oxalic")
    assert t1["pending"] == {"status": "question", "speak": "Cât ai folosit?"}

    t2 = await h.reply("cinci mililitri")
    assert t2["pending"] == {
        "status": "confirm",
        "speak": "Tratament pentru Regina Ana: Acid oxalic, 5 mililitri, azi. Salvez?",
    }
    # The model saw the question and the answer in the second call.
    texts = [m["text"] for m in extractor.requests[1].messages]
    assert texts == ["Stupul 7, acid oxalic", "Cât ai folosit?", "cinci mililitri"]
    assert extractor.requests[1].language == "ro"

    t3 = await h.reply("Da")
    assert t3["pending"] is None
    assert t3["state"]["status"] == "saved" and t3["state"]["speak"] == "Salvat."
    [saved] = h.saved
    f = saved["resolution"]
    assert (f["colony_id"], f["item_id"], f["amount"], f["unit"]) == (HIVE7, OXALIC, "5", "ml")


async def test_nothing_saved_without_yes_and_correction_goes_back_to_extract() -> None:
    extractor = ScriptedExtractor(
        entry(kind="treatment", colony="7", product="acid oxalic", amount=15, unit="ml"),
        entry(kind="treatment", colony="7", product="acid oxalic", amount=50, unit="ml"),
    )
    h = Harness(extractor)
    t1 = await h.start("Stupul 7, acid oxalic, 15 ml")
    assert "15 mililitri" in t1["pending"]["speak"]

    t2 = await h.reply("nu, 50 de mililitri")  # correction
    assert t2["pending"]["status"] == "confirm"
    assert "50 de mililitri" in t2["pending"]["speak"]
    assert h.saved == []

    await h.reply("da")
    assert h.saved[0]["resolution"]["amount"] == "50"


async def test_plain_no_asks_what_to_change() -> None:
    extractor = ScriptedExtractor(
        entry(kind="note", colony="7", queen_seen=True),
        entry(kind="note", colony="7", queen_seen=False),
    )
    h = Harness(extractor)
    await h.start("Stupul 7, matca văzută")
    t2 = await h.reply("nu")
    assert t2["pending"] == {"status": "question", "speak": "Ce să modific?"}
    t3 = await h.reply("matca nu a fost văzută")
    assert "matca nevăzută" in t3["pending"]["speak"]


async def test_cancel_at_any_point() -> None:
    h = Harness(ScriptedExtractor(entry(kind="treatment", colony="7", product="Apivar")))
    await h.start("Stupul 7, Apivar")  # asks how much
    t2 = await h.reply("anulează")
    assert t2["pending"] is None
    assert t2["state"]["status"] == "cancelled"
    assert t2["state"]["speak"] == "Anulat. Nu am salvat nimic."
    assert h.saved == []


async def test_not_understood_then_recovers() -> None:
    extractor = ScriptedExtractor(
        ExtractionFailed("garbage"),
        entry(kind="note", colony="7", temperament="calm"),
    )
    h = Harness(extractor)
    t1 = await h.start("mmm", locale="en-US")
    assert t1["pending"] == {
        "status": "not_understood",
        "speak": "Sorry, I didn't catch that. Please say it again.",
    }
    t2 = await h.reply("hive 7 is calm")
    assert t2["pending"]["status"] == "confirm"


async def test_gives_up_after_too_many_questions() -> None:
    h = Harness(ScriptedExtractor(entry(kind="unknown")), max_questions=2)
    await h.start("bla", locale="en-US")
    await h.reply("bla")
    t3 = await h.reply("bla")
    assert t3["pending"] is None
    assert t3["state"]["status"] == "cancelled"
    assert h.saved == []


async def test_context_colony_from_screen_skips_question() -> None:
    h = Harness(ScriptedExtractor(entry(kind="treatment", product="Apivar", amount=2)))
    t1 = await h.start("două benzi de Apivar", colony=HIVE7)
    assert t1["pending"]["status"] == "confirm"
    assert "2 benzi" in t1["pending"]["speak"]
