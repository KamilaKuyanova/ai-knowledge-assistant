from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserSettings(BaseModel):
    top_k: int = Field(default=5, ge=1, le=15)
    min_score: float = Field(default=0.35, ge=0.0, le=1.0)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    settings: UserSettings


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    error: str | None
    page_count: int | None
    chunk_count: int
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime


class SourceOut(BaseModel):
    document_id: int
    filename: str
    page: int | None
    quote: str
    score: float


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    sources: list[SourceOut]
    answered: bool
    created_at: datetime


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
