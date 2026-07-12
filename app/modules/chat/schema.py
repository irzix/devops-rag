from datetime import datetime
from pydantic import BaseModel, Field

class ChatSessionCreate(BaseModel):
    """Payload to instantiate a new chat session."""
    title: str = Field(..., min_length=1, max_length=100)

class ChatSessionResponse(BaseModel):
    """Metadata response representing a chat session."""
    id: int
    title: str
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ChatMessageResponse(BaseModel):
    """Metadata response representing a single message in a session thread."""
    id: int
    session_id: int
    sender: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class AgentActionResponse(BaseModel):
    """Metadata response representing a queued server command approval."""
    id: str
    session_id: int
    server_id: int
    command: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
