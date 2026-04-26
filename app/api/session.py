from fastapi import APIRouter

from app.models.schemas import ClearRequest, ApiResponse, SessionInfoResponse
from app.session.manager import session_store

router = APIRouter()


@router.post("/clear")
async def clear_session(req: ClearRequest):
    if not req.Id:
        return ApiResponse(code=400, message="Session ID cannot be empty")
    await session_store.clear(req.Id)
    return ApiResponse(data="Session history cleared")


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    info = await session_store.get_info(session_id)
    if info is None:
        return ApiResponse(code=404, message="Session not found")
    return ApiResponse(data=info)
