"""Run one voice turn: load the thread, run the graph, save records, store the thread.

Everything happens in the caller's user transaction, so a saved record, the conversation
state and the voice note status commit together (or not at all).
"""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from langgraph.types import Command
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.catalog import Catalog, load_catalog
from app.assistant.graph import VoiceDeps, VoiceState, build_graph
from app.assistant.llm import Extractor
from app.assistant.schemas import SavedRecord, StartVoiceSession, VoiceTurn
from app.assistant.store import ThreadStore
from app.auth.jwt import CurrentUser
from app.config import get_settings
from app.db import service_role
from app.errors import AppError
from app.models.db.tables import VoiceNote, VoiceSession
from app.models.schemas.sync import CrudOp
from app.services.sync import apply_batch

logger = logging.getLogger(__name__)

_NOTE_STATUS = {
    "question": "needs_answer",
    "not_understood": "needs_answer",
    "confirm": "needs_confirmation",
    "saved": "saved",
    "cancelled": "cancelled",
}


class VoiceSessionNotFound(AppError):
    def __init__(self) -> None:
        super().__init__(404, "not_found", "Voice session not found")


class VoiceSaveFailed(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            422, "voice_save_failed", "The entry could not be saved", {"reason": detail}
        )


# ---------------------------------------------------------------- saving records


def _put(table: str, record_id: str, data: dict[str, Any]) -> CrudOp:
    return CrudOp(op="PUT", table=table, id=UUID(record_id), data=data)


def build_ops(state: VoiceState) -> tuple[list[CrudOp], SavedRecord]:
    """Same rows a typed entry would create, written through the same validated path."""
    f = state["resolution"] or {}
    ids = state["ids"]
    kind = f["kind"]
    stamp = {"client_updated_at": datetime.now(UTC).isoformat()}
    voice = {**stamp, "source": "voice"}
    when = f["occurred_at"]

    if kind == "treatment":
        ops = [
            _put(
                "treatments",
                ids["record"],
                {
                    "colony_id": f["colony_id"],
                    "apiary_id": f["apiary_id"],
                    "inventory_item_id": f.get("item_id"),
                    "product_name": f["product_name"],
                    "amount": f["amount"],
                    "unit": f["unit"],
                    "treated_at": when,
                    "notes": f.get("notes"),
                    **voice,
                },
            )
        ]
        # Stock goes down only when units match; we never convert units.
        if f.get("item_id") and f.get("item_unit") == f["unit"]:
            ops.append(
                _put(
                    "inventory_adjustments",
                    ids["adjustment"],
                    {
                        "item_id": f["item_id"],
                        "delta": str(-Decimal(f["amount"])),
                        "unit": f["unit"],
                        "reason": "used",
                        "apiary_id": f["apiary_id"],
                        "adjusted_at": when,
                        "treatment_id": ids["record"],
                        **voice,
                    },
                )
            )
        return ops, SavedRecord(table="treatments", id=UUID(ids["record"]))

    if kind == "harvest":
        op = _put(
            "harvests",
            ids["record"],
            {
                "apiary_id": f["apiary_id"],
                "colony_id": f.get("colony_id"),
                "quantity": f["amount"],
                "unit": f["unit"],
                "harvested_at": when,
                "notes": f.get("notes"),
                **voice,
            },
        )
        return [op], SavedRecord(table="harvests", id=UUID(ids["record"]))

    if kind == "inventory":
        ops = []
        item_id = f.get("item_id") or ids["item"]
        if f.get("item_is_new"):
            ops.append(
                _put(
                    "inventory_items",
                    item_id,
                    {"name": f["product_name"], "category": "other", "unit": f["unit"], **stamp},
                )
            )
        amount = Decimal(f["amount"])
        ops.append(
            _put(
                "inventory_adjustments",
                ids["adjustment"],
                {
                    "item_id": item_id,
                    "delta": str(amount if f["action"] == "purchase" else -amount),
                    "unit": f["unit"],
                    "reason": f["action"],
                    "apiary_id": f.get("apiary_id"),
                    "adjusted_at": when,
                    "notes": f.get("notes"),
                    **voice,
                },
            )
        )
        return ops, SavedRecord(table="inventory_adjustments", id=UUID(ids["adjustment"]))

    op = _put(
        "colony_notes",
        ids["record"],
        {
            "colony_id": f["colony_id"],
            "apiary_id": f["apiary_id"],
            "noted_at": when,
            "queen_seen": f.get("queen_seen"),
            "temperament": f.get("temperament"),
            "text": f.get("text"),
            **voice,
        },
    )
    return [op], SavedRecord(table="colony_notes", id=UUID(ids["record"]))


async def save_records(session: AsyncSession, user: CurrentUser, state: VoiceState) -> SavedRecord:
    ops, record = build_ops(state)
    results = await apply_batch(session, user, ops)
    failed = [r for r in results if r.status != "applied"]
    if failed:
        raise VoiceSaveFailed("; ".join(f"{r.table}: {r.error or r.status}" for r in failed))
    return record


# ---------------------------------------------------------------- running turns


def _haptic(status: str) -> str:
    return {"saved": "saved", "question": "needs_answer", "confirm": "needs_answer"}.get(
        status, "not_understood"
    )


def _turn(thread_id: UUID, values: dict[str, Any], interrupts: list[Any]) -> VoiceTurn:
    draft = values.get("resolution") or values.get("entry")
    if interrupts:
        payload = interrupts[0].value
        return VoiceTurn(
            thread_id=thread_id,
            status=payload["status"],
            speak=payload["speak"],
            haptic=_haptic(payload["status"]),
            draft=draft,
        )
    status = values.get("status", "cancelled")
    if status not in ("saved", "cancelled"):
        status = "cancelled"
    record = values.get("record")
    return VoiceTurn(
        thread_id=thread_id,
        status=status,
        speak=values.get("speak") or "",
        haptic=_haptic(status),
        draft=draft,
        record=SavedRecord.model_validate(record) if record else None,
    )


async def _load_thread(session: AsyncSession, user: CurrentUser, thread_id: UUID) -> VoiceSession:
    async with service_role(session):
        row = await session.scalar(
            select(VoiceSession).where(
                VoiceSession.id == thread_id, VoiceSession.owner_id == user.id
            )
        )
    if row is None:
        raise VoiceSessionNotFound()
    return row


async def _store_thread(
    session: AsyncSession, user: CurrentUser, thread_id: UUID, status: str, state: dict[str, Any]
) -> None:
    ins = pg_insert(VoiceSession).values(id=thread_id, owner_id=user.id, status=status, state=state)
    stmt = ins.on_conflict_do_update(
        index_elements=[VoiceSession.id],
        set_={"status": ins.excluded.status, "state": ins.excluded.state},
        where=VoiceSession.owner_id == user.id,
    )
    async with service_role(session):
        await session.execute(stmt)


async def _update_voice_note(
    session: AsyncSession, user: CurrentUser, note_id: str, thread_id: UUID, turn: VoiceTurn
) -> None:
    await session.execute(
        update(VoiceNote)
        .where(VoiceNote.id == UUID(note_id), VoiceNote.owner_id == user.id)
        .values(
            status=_NOTE_STATUS[turn.status],
            thread_id=thread_id,
            result_record_type=turn.record.table if turn.record else None,
            result_record_id=turn.record.id if turn.record else None,
            error=None,
            client_updated_at=func.now(),
        )
    )


class VoiceAssistant:
    def __init__(self, session: AsyncSession, user: CurrentUser, extractor: Extractor) -> None:
        self.session = session
        self.user = user
        self.extractor = extractor
        self._catalog: Catalog | None = None

    async def _get_catalog(self) -> Catalog:
        if self._catalog is None:
            self._catalog = await load_catalog(self.session, self.user)
        return self._catalog

    async def _save(self, state: VoiceState) -> dict[str, str]:
        record = await save_records(self.session, self.user, state)
        return {"table": record.table, "id": str(record.id)}

    def _graph(self, store: ThreadStore) -> Any:
        deps = VoiceDeps(
            extract=self.extractor,
            catalog=self._get_catalog,
            save=self._save,
            max_questions=get_settings().voice_max_questions,
        )
        return build_graph(deps, store.saver)

    async def _finish(
        self, thread_id: UUID, store: ThreadStore, graph: Any, result: Any
    ) -> VoiceTurn:
        values = dict(result)
        interrupts = values.pop("__interrupt__", [])
        turn = _turn(thread_id, values, interrupts)
        status = "running" if interrupts else turn.status
        await _store_thread(self.session, self.user, thread_id, status, store.dump())
        if values.get("voice_note_id"):
            await _update_voice_note(
                self.session, self.user, values["voice_note_id"], thread_id, turn
            )
        return turn

    async def start(self, body: StartVoiceSession, voice_note_id: UUID | None = None) -> VoiceTurn:
        thread_id = uuid.uuid4()
        state: VoiceState = {
            "owner_id": str(self.user.id),
            "locale": body.locale,
            "now": (body.client_time or datetime.now(UTC)).isoformat(),
            "context_colony_id": str(body.context.colony_id) if body.context.colony_id else None,
            "context_apiary_id": str(body.context.apiary_id) if body.context.apiary_id else None,
            "voice_note_id": str(voice_note_id) if voice_note_id else None,
            "ids": {k: str(uuid.uuid4()) for k in ("record", "adjustment", "item")},
            "messages": [{"role": "user", "text": body.transcript.strip()}],
            "entry": None,
            "questions_asked": 0,
            "status": "running",
        }
        store = ThreadStore(str(thread_id))
        graph = self._graph(store)
        result = await graph.ainvoke(state, store.config)
        return await self._finish(thread_id, store, graph, result)

    async def current(self, thread_id: UUID) -> VoiceTurn:
        """The pending question/confirmation (or the final result) without advancing."""
        row = await _load_thread(self.session, self.user, thread_id)
        store = ThreadStore(str(thread_id))
        store.load(row.state)
        snapshot = await self._graph(store).aget_state(store.config)
        return _turn(thread_id, dict(snapshot.values), list(snapshot.interrupts))

    async def reply(self, thread_id: UUID, text: str) -> VoiceTurn:
        row = await _load_thread(self.session, self.user, thread_id)
        store = ThreadStore(str(thread_id))
        store.load(row.state)
        graph = self._graph(store)
        snapshot = await graph.aget_state(store.config)
        if not snapshot.interrupts:
            # Finished already (e.g. the app retried "yes" after a dropped response).
            return _turn(thread_id, dict(snapshot.values), [])
        result = await graph.ainvoke(Command(resume=text.strip()), store.config)
        return await self._finish(thread_id, store, graph, result)

    async def process_voice_note(self, note_id: UUID) -> VoiceTurn:
        note = await self.session.scalar(
            select(VoiceNote).where(
                VoiceNote.id == note_id,
                VoiceNote.owner_id == self.user.id,
                VoiceNote.deleted_at.is_(None),
            )
        )
        if note is None:
            raise AppError(404, "not_found", "Voice note not found")
        if note.thread_id is not None and note.status in ("needs_answer", "needs_confirmation"):
            return await self.current(note.thread_id)
        if note.status == "saved":
            raise AppError(409, "already_saved", "This voice note was already saved")
        body = StartVoiceSession(
            transcript=note.transcript,
            locale=note.locale,
            context={"colony_id": note.context_colony_id, "apiary_id": note.context_apiary_id},
            client_time=note.created_at,
        )
        return await self.start(body, voice_note_id=note.id)
