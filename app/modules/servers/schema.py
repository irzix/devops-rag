from pydantic import BaseModel, Field
from typing import Literal

class ServerCreate(BaseModel):
    """DTO for creating a new managed server connection."""
    name: str = Field(..., min_length=3, max_length=50)
    ip_address: str = Field(...)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(default="root")
    ssh_auth_type: Literal["password", "key"] = Field(default="password")
    
    # Raw password or private key string. Will be encrypted before database storage.
    credential: str = Field(..., min_length=1)
    
    tags: str = Field(default="")

class ServerUpdate(BaseModel):
    """DTO for updating an existing managed server connection."""
    name: str | None = Field(None, min_length=3, max_length=50)
    ip_address: str | None = None
    ssh_port: int | None = Field(None, ge=1, le=65535)
    ssh_username: str | None = None
    ssh_auth_type: Literal["password", "key"] | None = None
    credential: str | None = None
    tags: str | None = None

class ServerResponse(BaseModel):
    """Safe database projection returning public server parameters (excludes credentials)."""
    id: int
    name: str
    ip_address: str
    ssh_port: int
    ssh_username: str
    ssh_auth_type: str
    tags: str
    owner_id: int

    class Config:
        from_attributes = True

class CommandRequest(BaseModel):
    """Input payload to execute custom commands on target server."""
    command: str = Field(..., min_length=1)

class CommandResponse(BaseModel):
    """Response returned after running SSH commands."""
    stdout: str
    stderr: str
    exit_code: int
