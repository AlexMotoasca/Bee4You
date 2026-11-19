"""Contract for POST /v1/sync/upload (PowerSync upload queue)."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

OpType = Literal["PUT", "PATCH", "DELETE"]
OpStatus = Literal["applied", "conflict", "rejected"]


class CrudOp(BaseModel):
    op: OpType
    table: str
    id: UUID
    data: dict[str, Any] | None = None


class UploadRequest(BaseModel):
    ops: list[CrudOp] = Field(max_length=1000)


class OpResult(BaseModel):
    id: UUID
    table: str
    status: OpStatus
    error: str | None = None
    conflict_id: UUID | None = None


class UploadResponse(BaseModel):
    results: list[OpResult]
