"""Colony placements: keep "one open placement per colony" true when moves arrive from devices."""

from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import CurrentUser
from app.models.db.tables import ColonyPlacement as P

if TYPE_CHECKING:
    from app.services.sync import PreparedOp


async def resolve_placement_overlap(
    session: AsyncSession, user: CurrentUser, op: "PreparedOp"
) -> None:
    """Called before a placement write that leaves the placement open.

    - Any earlier placement still covering this start (open, or ending after it) is cut off
      at this placement's start: the colony left that site when it arrived here.
    - If a later placement already exists (another device moved the colony after this one),
      this placement becomes historical: it ends when the next one started.
    Server-side closes bump client_updated_at to now() so older device edits lose to them.
    """
    if op.op == "PUT":
        row = dict(op.values)
    else:
        current = (
            await session.execute(
                select(P.colony_id, P.started_at, P.ended_at, P.deleted_at).where(
                    P.id == op.id, P.owner_id == user.id
                )
            )
        ).first()
        if current is None:
            return
        row = {**current._asdict(), **op.values}

    if row.get("ended_at") is not None or row.get("deleted_at") is not None:
        return
    colony_id, started_at = row["colony_id"], row["started_at"]

    await session.execute(
        update(P)
        .where(
            P.owner_id == user.id,
            P.colony_id == colony_id,
            P.id != op.id,
            P.deleted_at.is_(None),
            P.started_at <= started_at,
            or_(P.ended_at.is_(None), P.ended_at > started_at),
        )
        .values(ended_at=started_at, client_updated_at=func.now())
    )

    next_start = await session.scalar(
        select(func.min(P.started_at)).where(
            P.owner_id == user.id,
            P.colony_id == colony_id,
            P.id != op.id,
            P.deleted_at.is_(None),
            P.started_at > started_at,
        )
    )
    if next_start is not None:
        op.values["ended_at"] = next_start
