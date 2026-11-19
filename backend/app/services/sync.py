"""Apply the PowerSync upload queue: idempotent upserts, last-write-wins, conflict log.

See BackendArchitect.md §6.2 for the rules this implements.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Table, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import ReturningInsert, ReturningUpdate

from app.auth.jwt import CurrentUser
from app.models.db.tables import SyncConflict
from app.models.schemas.sync import CrudOp, OpResult, OpType
from app.services.errors import OpRejected
from app.services.registry import REGISTRY, TableSpec

logger = logging.getLogger(__name__)

# Set by the server, never taken from the device payload.
SERVER_MANAGED = frozenset({"id", "owner_id", "created_at", "updated_at"})

# SQLSTATE classes that mean "this op can never succeed" (vs. transient failures).
_PERMANENT_SQLSTATE_PREFIXES = ("22", "23", "42501", "P0001")


@dataclass
class PreparedOp:
    op: OpType
    spec: TableSpec
    id: UUID
    values: dict[str, Any]  # DB column values, excluding id/owner_id
    client_payload: dict[str, Any]  # validated payload as JSON, for the conflict log


class _StaleWrite(Exception):
    """The stored row has a newer client_updated_at; the incoming write lost."""


def _format_validation(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "data"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)


def prepare_op(op: CrudOp, user: CurrentUser) -> PreparedOp:
    """Validate one op without touching the database. Raises OpRejected."""
    spec = REGISTRY.get(op.table)
    if spec is None:
        raise OpRejected(f"unknown table '{op.table}'")
    if op.op not in spec.allowed_ops:
        raise OpRejected(f"{op.op} is not allowed on {op.table}")
    if spec.owner_is_id and op.id != user.id:
        raise OpRejected("record not found")
    if op.op == "DELETE":
        return PreparedOp(op.op, spec, op.id, {}, {})

    data = {k: v for k, v in (op.data or {}).items() if k not in SERVER_MANAGED}
    model = spec.write_model if op.op == "PUT" else spec.patch_model
    try:
        parsed = model.model_validate(data)
    except ValidationError as exc:
        raise OpRejected(_format_validation(exc)) from exc

    partial = op.op == "PATCH"
    payload = parsed.model_dump(mode="json", exclude_unset=partial)
    values = spec.to_db(parsed.model_dump(exclude_unset=partial))
    return PreparedOp(op.op, spec, op.id, values, payload)


async def _write(session: AsyncSession, user: CurrentUser, p: PreparedOp) -> None:
    table: Table = p.spec.model.__table__  # type: ignore[assignment]

    if p.op == "DELETE":
        # Soft delete; deleting something unknown or already deleted is a no-op.
        await session.execute(
            update(table)
            .where(table.c.id == p.id, table.c.deleted_at.is_(None))
            .values(
                deleted_at=func.now(),
                client_updated_at=func.greatest(table.c.client_updated_at, func.now()),
            )
        )
        return

    if p.spec.before_write is not None:
        await p.spec.before_write(session, user, p)

    stmt: ReturningInsert[Any] | ReturningUpdate[Any]
    if p.op == "PUT":
        row = {**p.values, "id": p.id}
        if not p.spec.owner_is_id:
            row["owner_id"] = user.id
        ins = pg_insert(table).values(row)
        stmt = ins.on_conflict_do_update(
            index_elements=[table.c.id],
            set_={k: ins.excluded[k] for k in p.values},
            where=table.c.client_updated_at <= ins.excluded.client_updated_at,
        ).returning(table.c.id)
    else:
        stmt = (
            update(table)
            .where(table.c.id == p.id, table.c.client_updated_at <= p.values["client_updated_at"])
            .values(**p.values)
            .returning(table.c.id)
        )

    if (await session.execute(stmt)).first() is not None:
        return
    exists = await session.scalar(select(table.c.id).where(table.c.id == p.id))
    if exists is None:
        raise OpRejected("record not found")
    raise _StaleWrite


async def _log_conflict(session: AsyncSession, user: CurrentUser, p: PreparedOp) -> UUID:
    server_payload = await session.scalar(
        text(f"select to_jsonb(t) from public.{p.spec.name} t where t.id = :id"), {"id": p.id}
    )
    conflict = SyncConflict(
        id=uuid.uuid4(),
        owner_id=user.id,
        table_name=p.spec.name,
        record_id=p.id,
        client_payload=p.client_payload,
        server_payload=server_payload,
    )
    session.add(conflict)
    await session.flush()
    return conflict.id


async def execute_op(session: AsyncSession, user: CurrentUser, p: PreparedOp) -> OpResult:
    try:
        async with session.begin_nested():
            await _write(session, user, p)
    except _StaleWrite:
        conflict_id = await _log_conflict(session, user, p)
        return OpResult(id=p.id, table=p.spec.name, status="conflict", conflict_id=conflict_id)
    return OpResult(id=p.id, table=p.spec.name, status="applied")


def _sqlstate(exc: DBAPIError) -> str | None:
    orig = exc.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def _is_permanent(exc: DBAPIError) -> bool:
    state = _sqlstate(exc)
    return state is not None and state.startswith(_PERMANENT_SQLSTATE_PREFIXES)


async def apply_batch(
    session: AsyncSession, user: CurrentUser, ops: list[CrudOp]
) -> list[OpResult]:
    """Apply ops in order, each in its own savepoint. Transient DB errors propagate (→ retry)."""
    results: list[OpResult] = []
    for op in ops:
        try:
            prepared = prepare_op(op, user)
            async with session.begin_nested():
                result = await execute_op(session, user, prepared)
        except OpRejected as exc:
            result = OpResult(id=op.id, table=op.table, status="rejected", error=exc.message)
        except DBAPIError as exc:
            if not _is_permanent(exc):
                raise
            message = str(exc.orig).splitlines()[0][:300]
            result = OpResult(id=op.id, table=op.table, status="rejected", error=message)
        if result.status == "rejected":
            logger.warning(
                "sync op rejected",
                extra={"user_id": str(user.id), "table": op.table, "error": result.error},
            )
        results.append(result)
    return results
