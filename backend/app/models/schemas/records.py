"""What devices may write per table. Field names = DB column names (snake_case)."""

from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, create_model, model_validator

ApiaryKind = Literal["permanent", "temporary"]
ColonyMode = Literal["stationary", "migratory"]
ColonyStatus = Literal["active", "dead", "sold", "merged"]
# Shared with the frontend and the DB domain `measure_unit`.
Unit = Literal["ml", "l", "g", "kg", "pcs", "strips", "frames"]
Source = Literal["manual", "voice"]
ItemCategory = Literal["treatment", "equipment", "consumable", "other"]
AdjustmentReason = Literal["purchase", "used", "moved", "correction"]
Temperament = Literal["calm", "nervous", "aggressive"]
VoiceNoteStatus = Literal[
    "pending", "processing", "needs_answer", "needs_confirmation", "saved", "cancelled", "failed"
]
Amount = Annotated[Decimal, Field(gt=0, le=1_000_000, max_digits=12, decimal_places=4)]


class ClientRow(BaseModel):
    """Base for device writes. Unknown columns are rejected (extra='forbid')."""

    model_config = ConfigDict(extra="forbid")

    client_updated_at: AwareDatetime
    deleted_at: AwareDatetime | None = None


class ProfileWrite(ClientRow):
    display_name: str | None = Field(default=None, max_length=100)
    locale: str = Field(default="en-US", min_length=2, max_length=20)


class ApiaryWrite(ClientRow):
    name: str = Field(min_length=1, max_length=120)
    kind: ApiaryKind = "permanent"
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _coords_together(self) -> "ApiaryWrite":
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat and lng must be given together")
        return self


class ColonyWrite(ClientRow):
    label: str = Field(min_length=1, max_length=60)
    number: int | None = Field(default=None, ge=0)
    mode: ColonyMode = "stationary"
    status: ColonyStatus = "active"
    queen_year: int | None = Field(default=None, ge=1990, le=2100)
    notes: str | None = Field(default=None, max_length=2000)


class ColonyPlacementWrite(ClientRow):
    colony_id: UUID
    apiary_id: UUID
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _dates_ordered(self) -> "ColonyPlacementWrite":
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at must not be before started_at")
        return self


class InventoryItemWrite(ClientRow):
    name: str = Field(min_length=1, max_length=120)
    category: ItemCategory = "other"
    unit: Unit
    apiary_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class TreatmentWrite(ClientRow):
    colony_id: UUID
    apiary_id: UUID
    inventory_item_id: UUID | None = None
    product_name: str = Field(min_length=1, max_length=120)
    amount: Amount
    unit: Unit
    treated_at: AwareDatetime
    notes: str | None = Field(default=None, max_length=2000)
    source: Source = "manual"


class InventoryAdjustmentWrite(ClientRow):
    item_id: UUID
    delta: Annotated[Decimal, Field(ge=-1_000_000, le=1_000_000, max_digits=12, decimal_places=4)]
    unit: Unit
    reason: AdjustmentReason
    apiary_id: UUID | None = None
    adjusted_at: AwareDatetime
    treatment_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    source: Source = "manual"

    @model_validator(mode="after")
    def _non_zero(self) -> "InventoryAdjustmentWrite":
        if self.delta == 0:
            raise ValueError("delta must not be zero")
        return self


class HarvestWrite(ClientRow):
    apiary_id: UUID
    colony_id: UUID | None = None
    quantity: Amount
    unit: Unit
    harvested_at: AwareDatetime
    notes: str | None = Field(default=None, max_length=2000)
    source: Source = "manual"


class ColonyNoteWrite(ClientRow):
    colony_id: UUID
    apiary_id: UUID
    noted_at: AwareDatetime
    queen_seen: bool | None = None
    temperament: Temperament | None = None
    text: str | None = Field(default=None, max_length=4000)
    source: Source = "manual"

    @model_validator(mode="after")
    def _not_empty(self) -> "ColonyNoteWrite":
        if self.queen_seen is None and self.temperament is None and not (self.text or "").strip():
            raise ValueError("a note needs text, queen_seen or temperament")
        return self


class VoiceNoteWrite(ClientRow):
    transcript: str = Field(min_length=1, max_length=4000)
    audio_path: str | None = Field(default=None, max_length=500)
    locale: str = Field(default="en-US", min_length=2, max_length=20)
    context_colony_id: UUID | None = None
    context_apiary_id: UUID | None = None
    status: VoiceNoteStatus = "pending"
    thread_id: UUID | None = None
    result_record_type: str | None = Field(default=None, max_length=40)
    result_record_id: UUID | None = None
    error: str | None = Field(default=None, max_length=1000)


def make_patch_model(model: type[ClientRow]) -> type[ClientRow]:
    """Same fields and constraints as `model`, all optional except client_updated_at.

    Cross-field validators are not carried over; DB check constraints and the table's
    to_db hook cover those for partial updates.
    """
    fields: dict[str, Any] = {}
    for name, info in model.model_fields.items():
        if name in ClientRow.model_fields:
            continue
        annotation: Any = info.annotation
        annotation = annotation | None
        if info.metadata:
            annotation = Annotated[(annotation, *info.metadata)]
        fields[name] = (annotation, None)
    patch: type[ClientRow] = create_model(f"{model.__name__}Patch", __base__=ClientRow, **fields)
    return patch
