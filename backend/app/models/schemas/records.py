"""What devices may write per table. Field names = DB column names (snake_case)."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, create_model, model_validator

ApiaryKind = Literal["permanent", "temporary"]
ColonyMode = Literal["stationary", "migratory"]
ColonyStatus = Literal["active", "dead", "sold", "merged"]


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
