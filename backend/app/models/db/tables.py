"""SQLAlchemy models mirroring backend/supabase/migrations. They never create or alter tables."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Computed, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import UserDefinedType


class Geography(UserDefinedType[Any]):
    cache_ok = True

    def get_col_spec(self, **_: Any) -> str:
        return "extensions.geography(Point,4326)"


class Base(DeclarativeBase):
    pass


class ClientRecordMixin:
    """Columns every device-synced table has (see BackendArchitect.md §4.2)."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    client_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Profile(ClientRecordMixin, Base):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(Computed("id"))
    display_name: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text)


class Apiary(ClientRecordMixin, Base):
    __tablename__ = "apiaries"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    location: Mapped[Any] = mapped_column(Geography, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)


class Colony(ClientRecordMixin, Base):
    __tablename__ = "colonies"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    label: Mapped[str] = mapped_column(Text)
    number: Mapped[int | None] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    queen_year: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)


class ColonyPlacement(ClientRecordMixin, Base):
    __tablename__ = "colony_placements"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    colony_id: Mapped[UUID] = mapped_column(ForeignKey("colonies.id"))
    apiary_id: Mapped[UUID] = mapped_column(ForeignKey("apiaries.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncConflict(Base):
    __tablename__ = "sync_conflicts"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    table_name: Mapped[str] = mapped_column(Text)
    record_id: Mapped[UUID]
    client_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    server_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InventoryItem(ClientRecordMixin, Base):
    __tablename__ = "inventory_items"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    apiary_id: Mapped[UUID | None] = mapped_column(ForeignKey("apiaries.id"))
    notes: Mapped[str | None] = mapped_column(Text)


class Treatment(ClientRecordMixin, Base):
    __tablename__ = "treatments"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    colony_id: Mapped[UUID] = mapped_column(ForeignKey("colonies.id"))
    apiary_id: Mapped[UUID] = mapped_column(ForeignKey("apiaries.id"))
    inventory_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("inventory_items.id"))
    product_name: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric)
    unit: Mapped[str] = mapped_column(Text)
    treated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)


class InventoryAdjustment(ClientRecordMixin, Base):
    __tablename__ = "inventory_adjustments"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    item_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_items.id"))
    delta: Mapped[Decimal] = mapped_column(Numeric)
    unit: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    apiary_id: Mapped[UUID | None] = mapped_column(ForeignKey("apiaries.id"))
    adjusted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    treatment_id: Mapped[UUID | None] = mapped_column(ForeignKey("treatments.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)


class Harvest(ClientRecordMixin, Base):
    __tablename__ = "harvests"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    apiary_id: Mapped[UUID] = mapped_column(ForeignKey("apiaries.id"))
    colony_id: Mapped[UUID | None] = mapped_column(ForeignKey("colonies.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric)
    unit: Mapped[str] = mapped_column(Text)
    harvested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)


class ColonyNote(ClientRecordMixin, Base):
    __tablename__ = "colony_notes"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    colony_id: Mapped[UUID] = mapped_column(ForeignKey("colonies.id"))
    apiary_id: Mapped[UUID] = mapped_column(ForeignKey("apiaries.id"))
    noted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    queen_seen: Mapped[bool | None] = mapped_column(Boolean)
    temperament: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)


class VoiceNote(ClientRecordMixin, Base):
    __tablename__ = "voice_notes"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    transcript: Mapped[str] = mapped_column(Text)
    audio_path: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text)
    context_colony_id: Mapped[UUID | None] = mapped_column(ForeignKey("colonies.id"))
    context_apiary_id: Mapped[UUID | None] = mapped_column(ForeignKey("apiaries.id"))
    status: Mapped[str] = mapped_column(Text)
    thread_id: Mapped[UUID | None]
    result_record_type: Mapped[str | None] = mapped_column(Text)
    result_record_id: Mapped[UUID | None]
    error: Mapped[str | None] = mapped_column(Text)


class VoiceSession(Base):
    """LangGraph thread state. Server-only table: read/written under `service_role()`."""

    __tablename__ = "voice_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    status: Mapped[str] = mapped_column(Text)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
