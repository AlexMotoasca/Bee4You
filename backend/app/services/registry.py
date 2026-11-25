"""Which tables devices may write, and how. Adding a synced table = adding an entry here."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import CurrentUser
from app.models.db.tables import (
    Apiary,
    Base,
    Colony,
    ColonyNote,
    ColonyPlacement,
    Harvest,
    InventoryAdjustment,
    InventoryItem,
    Profile,
    Treatment,
    VoiceNote,
)
from app.models.schemas.records import (
    ApiaryWrite,
    ClientRow,
    ColonyNoteWrite,
    ColonyPlacementWrite,
    ColonyWrite,
    HarvestWrite,
    InventoryAdjustmentWrite,
    InventoryItemWrite,
    ProfileWrite,
    TreatmentWrite,
    VoiceNoteWrite,
    make_patch_model,
)
from app.models.schemas.sync import OpType
from app.services.apiaries import apiary_to_db
from app.services.colonies import resolve_placement_overlap

if TYPE_CHECKING:
    from app.services.sync import PreparedOp

BeforeWrite = Callable[[AsyncSession, CurrentUser, "PreparedOp"], Awaitable[None]]


def _identity(values: dict[str, Any]) -> dict[str, Any]:
    return values


@dataclass(frozen=True)
class TableSpec:
    name: str
    model: type[Base]
    write_model: type[ClientRow]
    allowed_ops: frozenset[OpType] = frozenset({"PUT", "PATCH", "DELETE"})
    owner_is_id: bool = False  # profiles: the row id IS the user id
    to_db: Callable[[dict[str, Any]], dict[str, Any]] = _identity
    before_write: BeforeWrite | None = None
    patch_model: type[ClientRow] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "patch_model", make_patch_model(self.write_model))


REGISTRY: dict[str, TableSpec] = {
    spec.name: spec
    for spec in (
        TableSpec(
            "profiles",
            Profile,
            ProfileWrite,
            allowed_ops=frozenset({"PUT", "PATCH"}),
            owner_is_id=True,
        ),
        TableSpec("apiaries", Apiary, ApiaryWrite, to_db=apiary_to_db),
        TableSpec("colonies", Colony, ColonyWrite),
        TableSpec(
            "colony_placements",
            ColonyPlacement,
            ColonyPlacementWrite,
            before_write=resolve_placement_overlap,
        ),
        TableSpec("inventory_items", InventoryItem, InventoryItemWrite),
        # Order matters inside one upload batch: a treatment before its stock adjustment.
        TableSpec("treatments", Treatment, TreatmentWrite),
        TableSpec("inventory_adjustments", InventoryAdjustment, InventoryAdjustmentWrite),
        TableSpec("harvests", Harvest, HarvestWrite),
        TableSpec("colony_notes", ColonyNote, ColonyNoteWrite),
        TableSpec("voice_notes", VoiceNote, VoiceNoteWrite),
    )
}
