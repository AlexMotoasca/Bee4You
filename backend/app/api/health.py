from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: str = "ok"


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut()
