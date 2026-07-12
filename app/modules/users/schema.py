from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    email: str = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool

    class Config:
        # Allows Pydantic to read ORM models (similar to class-transformer in NestJS)
        from_attributes = True
