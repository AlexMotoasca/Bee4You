import os
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import jwt
import pytest

TEST_SECRET = "test-secret-at-least-32-bytes-long-for-hs256"
TEST_SUPABASE_URL = "https://test-project.supabase.co"

os.environ["SUPABASE_URL"] = TEST_SUPABASE_URL
os.environ["SUPABASE_JWT_SECRET"] = TEST_SECRET
# DATABASE_URL comes from backend/.env; only tests marked `db` (run with --db) connect to it.
os.environ["DB_SERVERLESS"] = "true"  # NullPool: no connections shared across test event loops

import httpx  # noqa: E402

from app.main import create_app  # noqa: E402


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--db",
        action="store_true",
        help="run integration tests against DATABASE_URL (creates and deletes test users)",
    )
    parser.addoption(
        "--groq",
        action="store_true",
        help="call the real Groq API with GROQ_API_KEY (uses free-tier quota)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "db: needs a real Supabase database (run with --db)")
    config.addinivalue_line("markers", "groq: calls the real Groq API (run with --groq)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for flag in ("db", "groq"):
        if config.getoption(f"--{flag}"):
            continue
        skip = pytest.mark.skip(reason=f"needs --{flag}")
        for item in items:
            if flag in item.keywords:
                item.add_marker(skip)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def make_token(user_id: uuid.UUID) -> Callable[..., str]:
    def _make(**overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": str(user_id),
            "aud": "authenticated",
            "iss": f"{TEST_SUPABASE_URL}/auth/v1",
            "role": "authenticated",
            "email": "beekeeper@example.com",
            "iat": now,
            "exp": now + 3600,
        }
        claims.update(overrides)
        return jwt.encode({k: v for k, v in claims.items() if v is not None}, TEST_SECRET, "HS256")

    return _make


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
