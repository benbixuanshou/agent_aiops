from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    Id: Optional[str] = Field(default="", alias="Id")
    Question: str = Field(..., alias="Question")

    model_config = {"populate_by_name": True}


class ClearRequest(BaseModel):
    Id: str = Field(..., alias="Id")

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    success: bool
    answer: Optional[str] = None
    error_message: Optional[str] = None


class SseMessage(BaseModel):
    type: str  # "content" | "error" | "done"
    data: Optional[str] = None


class SessionInfoResponse(BaseModel):
    session_id: str
    message_pair_count: int
    create_time: float


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[object] = None


class FileUploadResponse(BaseModel):
    file_name: str
    file_path: str
    file_size: int
