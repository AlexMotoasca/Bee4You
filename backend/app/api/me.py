from fastapi import APIRouter

from app.api.deps import UserDep
from app.auth.jwt import CurrentUser

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=CurrentUser)
async def me(user: UserDep) -> CurrentUser:
    """Verify the Supabase token and return its user. The profile row syncs via PowerSync."""
    return user
