from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ─── Auth ────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse



# ─── Documents ───────────────────────────────────────────────────────────────


class DocumentResponse(BaseModel):
    id: int
    user_id: int
    filename: str
    file_size: int = 0
    page_count: int = 0
    status: str = "pending"
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


# ─── Chat ────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
   


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[datetime] = None


class ChatResponse(BaseModel):
    reply: str
    user_id:int
    order_placed: bool = False
    order_id: Optional[int] = None


# ─── Orders ──────────────────────────────────────────────────────────────────


class OrderItem(BaseModel):
    menu_item: str
    quantity: int = Field(default=1, ge=1)
   


class OrderCreate(BaseModel):
    items: list[OrderItem]
    special_instructions: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    user_id: int
    items: list[dict]
    total_amount: float
    status: str
    special_instructions: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern="^(pending|confirmed|preparing|ready|delivered|cancelled)$",
    )


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
    total: int


# ─── History ─────────────────────────────────────────────────────────────────


class HistoryResponse(BaseModel):
    messages: list[ChatMessage]
    total: int


# ─── Menu / Smart ────────────────────────────────────────────────────────────


class MenuSearchResult(BaseModel):
    id: str
    text: str
    score: float
    source: Optional[str] = None


class MenuSearchResponse(BaseModel):
    query: str
    results: list[MenuSearchResult]
    total: int


class RecommendationResponse(BaseModel):
    recommendations: list[MenuSearchResult]
    based_on: str


class BillResponse(BaseModel):
    order_id: int
    items: list[dict]
    subtotal: float
    tax: float
    total: float
    status: str
    generated_at: datetime


# ─── Health ──────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    pinecone: str
    ollama: str
