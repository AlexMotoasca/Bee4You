"""Database engine and per-request sessions that run under the caller's RLS identity."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.jwt import CurrentUser
from app.config import get_settings


def _async_url(url: str) -> str:
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix) :]
    return url


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if settings.db_serverless:
        # Supabase pooler (transaction mode) does not support prepared statements,
        # and serverless functions must not hold a connection pool.
        kwargs = {
            "poolclass": NullPool,
            "connect_args": {"statement_cache_size": 0, "prepared_statement_cache_size": 0},
        }
    return create_async_engine(_async_url(settings.database_url), **kwargs)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        await get_engine().dispose()


@asynccontextmanager
async def user_session(user: CurrentUser) -> AsyncIterator[AsyncSession]:
    """Open a transaction that runs as the `authenticated` role with the user's JWT claims.

    RLS policies therefore apply to every statement (defense in depth on top of the
    explicit owner_id filters in services). Callers that write must `await session.commit()`.
    Anything not committed is rolled back when the session closes.
    """
    async with get_sessionmaker()() as session:
        await set_user_claims(session, user)
        yield session


async def set_user_claims(session: AsyncSession, user: CurrentUser) -> None:
    claims = json.dumps({"sub": str(user.id), "role": "authenticated"})
    await session.execute(text("set local role authenticated"))
    await session.execute(
        text("select set_config('request.jwt.claims', :claims, true)"), {"claims": claims}
    )


@asynccontextmanager
async def service_role(session: AsyncSession) -> AsyncIterator[None]:
    """Temporarily leave the `authenticated` role inside a user transaction.

    Only for server-only tables (voice_sessions) that users must not read or write.
    Callers MUST still filter by owner_id explicitly.
    """
    await session.execute(text("set local role none"))
    try:
        yield
    finally:
        await session.execute(text("set local role authenticated"))
