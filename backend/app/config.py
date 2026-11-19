"""Application settings. This is the ONLY module that reads environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    log_level: str = "INFO"

    # Postgres. Use the Supabase pooler URL (port 6543, transaction mode) on serverless hosts.
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"
    # True on serverless (Vercel) or when DATABASE_URL points at the Supabase pooler:
    # no in-process connection pool, no prepared statements.
    db_serverless: bool = False

    # Supabase Auth
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_jwks_url: str | None = None
    supabase_jwt_secret: str | None = None  # legacy HS256 projects only
    jwt_audience: str = "authenticated"

    cors_origins: list[str] = []

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def jwks_url(self) -> str:
        return self.supabase_jwks_url or f"{self.jwt_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
