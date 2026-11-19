"""Fixtures for integration tests against the real Supabase database.

Each test user is inserted into auth.users (the sign-up trigger creates its profile) and
deleted afterwards; owner_id foreign keys cascade, so all their rows go with them.
"""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text

from app.auth.jwt import CurrentUser
from app.db import get_engine, user_session
from app.models.schemas.sync import CrudOp, OpResult
from app.services.sync import apply_batch

pytestmark = pytest.mark.db

Upload = Callable[[CurrentUser, list[dict[str, Any]]], Awaitable[list[OpResult]]]
Admin = Callable[[str, dict[str, Any] | None], Awaitable[list[Any]]]


_BASE = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=1)


def ts(minutes: int = 0) -> str:
    """ISO timestamp relative to test start, so tests control which edit is newer.

    Starts after "now" because server-created rows (e.g. the sign-up profile) carry now().
    """
    return (_BASE + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
async def make_user() -> AsyncIterator[Callable[[], Awaitable[CurrentUser]]]:
    created: list[uuid.UUID] = []

    async def _make() -> CurrentUser:
        uid = uuid.uuid4()
        async with get_engine().begin() as conn:
            await conn.execute(
                text(
                    "insert into auth.users"
                    " (id, instance_id, aud, role, email, created_at, updated_at)"
                    " values (:id, '00000000-0000-0000-0000-000000000000', 'authenticated',"
                    " 'authenticated', :email, now(), now())"
                ),
                {"id": uid, "email": f"b4y-test-{uid}@example.com"},
            )
        created.append(uid)
        return CurrentUser(id=uid, role="authenticated")

    yield _make

    if created:
        async with get_engine().begin() as conn:
            await conn.execute(
                text("delete from auth.users where id = any(:ids)"), {"ids": created}
            )


@pytest.fixture
def upload() -> Upload:
    async def _upload(user: CurrentUser, ops: list[dict[str, Any]]) -> list[OpResult]:
        async with user_session(user) as session:
            results = await apply_batch(session, user, [CrudOp(**o) for o in ops])
            await session.commit()
        return results

    return _upload


@pytest.fixture
def admin() -> Admin:
    """Run a query as the DB owner (bypasses RLS) to inspect what really got stored."""

    async def _query(sql: str, params: dict[str, Any] | None = None) -> list[Any]:
        async with get_engine().connect() as conn:
            return list((await conn.execute(text(sql), params or {})).all())

    return _query
