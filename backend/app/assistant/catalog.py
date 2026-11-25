"""The user's own hives, apiaries and items, loaded once per voice turn for matching."""

from dataclasses import dataclass, field

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import CurrentUser
from app.models.db.tables import Apiary, Colony, ColonyPlacement, InventoryItem


@dataclass(frozen=True)
class ColonyRef:
    id: str
    label: str
    number: int | None
    status: str
    apiary_id: str | None  # current placement
    apiary_name: str | None


@dataclass(frozen=True)
class ApiaryRef:
    id: str
    name: str


@dataclass(frozen=True)
class ItemRef:
    id: str
    name: str
    unit: str
    category: str


@dataclass(frozen=True)
class Catalog:
    colonies: list[ColonyRef] = field(default_factory=list)
    apiaries: list[ApiaryRef] = field(default_factory=list)
    items: list[ItemRef] = field(default_factory=list)

    def colony(self, colony_id: str | None) -> ColonyRef | None:
        return next((c for c in self.colonies if c.id == colony_id), None)

    def apiary(self, apiary_id: str | None) -> ApiaryRef | None:
        return next((a for a in self.apiaries if a.id == apiary_id), None)

    def item(self, item_id: str | None) -> ItemRef | None:
        return next((i for i in self.items if i.id == item_id), None)


async def load_catalog(session: AsyncSession, user: CurrentUser) -> Catalog:
    apiaries = (
        await session.execute(
            select(Apiary.id, Apiary.name)
            .where(Apiary.owner_id == user.id, Apiary.deleted_at.is_(None))
            .order_by(Apiary.name)
        )
    ).all()
    apiary_names = {str(a.id): a.name for a in apiaries}

    colonies = (
        await session.execute(
            select(Colony.id, Colony.label, Colony.number, Colony.status, ColonyPlacement.apiary_id)
            .outerjoin(
                ColonyPlacement,
                and_(
                    ColonyPlacement.colony_id == Colony.id,
                    ColonyPlacement.ended_at.is_(None),
                    ColonyPlacement.deleted_at.is_(None),
                ),
            )
            .where(Colony.owner_id == user.id, Colony.deleted_at.is_(None))
            .order_by(Colony.number, Colony.label)
        )
    ).all()

    items = (
        await session.execute(
            select(InventoryItem.id, InventoryItem.name, InventoryItem.unit, InventoryItem.category)
            .where(InventoryItem.owner_id == user.id, InventoryItem.deleted_at.is_(None))
            .order_by(InventoryItem.name)
        )
    ).all()

    return Catalog(
        colonies=[
            ColonyRef(
                id=str(c.id),
                label=c.label,
                number=c.number,
                status=c.status,
                apiary_id=str(c.apiary_id) if c.apiary_id else None,
                apiary_name=apiary_names.get(str(c.apiary_id)) if c.apiary_id else None,
            )
            for c in colonies
        ],
        apiaries=[ApiaryRef(id=str(a.id), name=a.name) for a in apiaries],
        items=[ItemRef(id=str(i.id), name=i.name, unit=i.unit, category=i.category) for i in items],
    )
