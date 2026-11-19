from fastapi import APIRouter

from app.api.deps import DbDep, UserDep
from app.models.schemas.sync import UploadRequest, UploadResponse
from app.services import sync as sync_service

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/upload", response_model=UploadResponse)
async def upload(body: UploadRequest, user: UserDep, session: DbDep) -> UploadResponse:
    """Apply a batch from the PowerSync upload queue.

    Always 200 when the batch was processed: permanently invalid ops come back as `rejected`
    so they never jam the device queue. Transient failures return 5xx and the device retries
    the whole batch, which is safe because every op is idempotent.
    """
    results = await sync_service.apply_batch(session, user, body.ops)
    await session.commit()
    return UploadResponse(results=results)
