"""Supabase JWT verification (JWKS for asymmetric keys, HS256 secret for legacy projects)."""

from functools import lru_cache
from uuid import UUID

import jwt
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.errors import AppError

ASYMMETRIC_ALGS = ("RS256", "ES256")


class CurrentUser(BaseModel):
    id: UUID
    email: str | None = None
    role: str


class AuthError(AppError):
    def __init__(self, message: str = "Invalid or expired token") -> None:
        super().__init__(401, "unauthorized", message)


class TokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jwks = jwt.PyJWKClient(settings.jwks_url, cache_keys=True, lifespan=3600)

    def verify(self, token: str) -> CurrentUser:
        """Blocking (JWKS fetch on cache miss): call from a sync dependency / threadpool."""
        s = self._settings
        try:
            alg = jwt.get_unverified_header(token).get("alg")
            key: object
            if alg == "HS256":
                if not s.supabase_jwt_secret:
                    raise AuthError("HS256 tokens are not accepted")
                key = s.supabase_jwt_secret
            elif alg in ASYMMETRIC_ALGS:
                key = self._jwks.get_signing_key_from_jwt(token).key
            else:
                raise AuthError("Unsupported token algorithm")
            claims = jwt.decode(
                token,
                key,  # type: ignore[arg-type]
                algorithms=[alg],
                audience=s.jwt_audience,
                issuer=s.jwt_issuer,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthError() from exc

        if claims.get("role") != "authenticated":
            raise AuthError("Token is not for a signed-in user")
        try:
            user_id = UUID(claims["sub"])
        except ValueError as exc:
            raise AuthError() from exc
        return CurrentUser(id=user_id, email=claims.get("email"), role=claims["role"])


@lru_cache
def get_verifier() -> TokenVerifier:
    return TokenVerifier(get_settings())
