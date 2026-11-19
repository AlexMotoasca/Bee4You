from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import AuthError, CurrentUser, TokenVerifier, get_verifier
from app.db import user_session

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_verifier)],
) -> CurrentUser:
    # Sync on purpose: FastAPI runs it in a threadpool, so a JWKS fetch never blocks the loop.
    if creds is None:
        raise AuthError("Missing bearer token")
    return verifier.verify(creds.credentials)


async def get_db(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AsyncIterator[AsyncSession]:
    async with user_session(user) as session:
        yield session


UserDep = Annotated[CurrentUser, Depends(get_current_user)]
DbDep = Annotated[AsyncSession, Depends(get_db)]
