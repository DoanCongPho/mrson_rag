from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_name: str = Field(..., min_length=1, max_length=50)
    query: str = Field(..., min_length=1)
    conversation_id: int | None = None


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
