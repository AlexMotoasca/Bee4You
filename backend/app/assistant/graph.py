"""Voice-entry conversation graph (BackendArchitect.md §8).

    extract -> resolve -> missing? --yes--> ask (interrupt) --answer--> extract
                            |no
                            v
                       confirm (interrupt) --yes--> save
                            |no / correction --> ask / extract
                            |cancel --> end

Nodes get their I/O (LLM, catalog, saving) from VoiceDeps, so the graph itself is pure and
testable with fakes. State holds only JSON-friendly values.
"""

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer, interrupt

from app.assistant.catalog import Catalog
from app.assistant.llm import ExtractionFailed, Extractor, ExtractRequest
from app.assistant.messages import classify_answer, for_locale, summarize
from app.assistant.resolve import Context, resolve
from app.assistant.schemas import ExtractedEntry


class VoiceState(TypedDict, total=False):
    owner_id: str
    locale: str
    now: str  # ISO, device time of the first utterance
    context_colony_id: str | None
    context_apiary_id: str | None
    voice_note_id: str | None
    ids: dict[str, str]  # pre-generated record ids -> saving is idempotent
    messages: list[dict[str, str]]
    entry: dict[str, Any] | None
    resolution: dict[str, Any] | None
    missing: str | None
    question: str | None
    not_understood: bool
    questions_asked: int
    decision: str | None
    status: str  # running | saved | cancelled
    speak: str | None
    record: dict[str, str] | None


@dataclass
class VoiceDeps:
    extract: Extractor
    catalog: Callable[[], Awaitable[Catalog]]
    save: Callable[[VoiceState], Awaitable[dict[str, str]]]  # -> {"table", "id"}
    max_questions: int = 6


def build_graph(deps: VoiceDeps, checkpointer: Checkpointer) -> CompiledStateGraph[Any]:
    def lang(state: VoiceState) -> Any:
        return for_locale(state.get("locale"))

    async def extract(state: VoiceState) -> VoiceState:
        m = lang(state)
        try:
            entry = await deps.extract(
                ExtractRequest(
                    messages=state["messages"],
                    previous=state.get("entry"),
                    catalog=await deps.catalog(),
                    today=datetime.fromisoformat(state["now"]).date(),
                    language=m.lang,
                )
            )
        except ExtractionFailed:
            return {"not_understood": True}
        return {"entry": entry.model_dump(), "not_understood": False}

    async def resolve_node(state: VoiceState) -> VoiceState:
        m = lang(state)
        if state.get("not_understood") and not state.get("entry"):
            return {"missing": "not_understood", "question": m.questions["not_understood"]}
        raw = state.get("entry")
        entry = ExtractedEntry.model_validate(raw) if raw else None
        ctx = Context(
            now=datetime.fromisoformat(state["now"]),
            colony_id=state.get("context_colony_id"),
            apiary_id=state.get("context_apiary_id"),
        )
        res = resolve(entry, await deps.catalog(), ctx, m)
        return {
            "resolution": asdict(res)["fields"] if res.complete else None,
            "missing": res.missing,
            "question": res.question,
        }

    def after_resolve(state: VoiceState) -> Literal["ask", "confirm"]:
        return "ask" if state.get("missing") else "confirm"

    async def ask(state: VoiceState) -> VoiceState:
        m = lang(state)
        if state.get("questions_asked", 0) >= deps.max_questions:
            return {"status": "cancelled", "speak": m.too_many}
        question = state.get("question") or m.questions["not_understood"]
        status = "not_understood" if state.get("missing") == "not_understood" else "question"
        answer: str = interrupt({"status": status, "speak": question})
        if classify_answer(answer) == "cancel":
            return {"status": "cancelled", "speak": m.cancelled}
        return {
            "messages": [
                *state["messages"],
                {"role": "assistant", "text": question},
                {"role": "user", "text": answer},
            ],
            "questions_asked": state.get("questions_asked", 0) + 1,
        }

    def after_ask(state: VoiceState) -> str:
        return END if state.get("status") == "cancelled" else "extract"

    async def confirm(state: VoiceState) -> VoiceState:
        m = lang(state)
        fields = state["resolution"] or {}
        summary = summarize(m, fields, datetime.fromisoformat(state["now"]).date())
        answer: str = interrupt({"status": "confirm", "speak": summary})
        decision = classify_answer(answer)
        if decision == "cancel":
            return {"status": "cancelled", "speak": m.cancelled, "decision": "cancel"}
        if decision == "yes":
            return {"decision": "save"}
        messages = [
            *state["messages"],
            {"role": "assistant", "text": summary},
            {"role": "user", "text": answer},
        ]
        if decision == "no":
            return {
                "decision": "change",
                "messages": messages,
                "missing": "change",
                "question": m.questions["change"],
            }
        return {"decision": "correct", "messages": messages}

    def after_confirm(state: VoiceState) -> str:
        decision = state.get("decision")
        if decision == "save":
            return "save"
        if decision == "cancel":
            return END
        return "ask" if decision == "change" else "extract"

    async def save(state: VoiceState) -> VoiceState:
        record = await deps.save(state)
        return {"status": "saved", "record": record, "speak": lang(state).saved}

    g = StateGraph(VoiceState)
    g.add_node("extract", extract)
    g.add_node("resolve", resolve_node)
    g.add_node("ask", ask)
    g.add_node("confirm", confirm)
    g.add_node("save", save)
    g.add_edge(START, "extract")
    g.add_edge("extract", "resolve")
    g.add_conditional_edges("resolve", after_resolve)
    g.add_conditional_edges("ask", after_ask)
    g.add_conditional_edges("confirm", after_confirm)
    g.add_edge("save", END)
    return g.compile(checkpointer=checkpointer)
