from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["part2", "part3", "writing"]


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    conversation_id: int | None = None
    # Required when starting a new chat; for an existing chat it must match the chat's mode.
    category: Category | None = None


class SourceOut(BaseModel):
    rank: int
    score: float
    source_file: str
    section_title: str
    doc_url: str | None = None


class ChatResponse(BaseModel):
    conversation_id: int
    answer: str
    sources: list[SourceOut]


class ConversationOut(BaseModel):
    id: int
    title: str
    category: str | None
    created_at: datetime
    updated_at: datetime


class ConversationUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    sources: list[SourceOut] = []
