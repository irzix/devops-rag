from sqlmodel import SQLModel, Field
from typing import Optional

class Server(SQLModel, table=True):
    """
    SQLModel representation of the target managed servers.
    Stores SSH access configurations with encrypted credentials.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # User-friendly identifier (e.g. "staging-vps")
    name: str = Field(index=True, unique=True, nullable=False)
    
    # Target machine host/IP address
    ip_address: str = Field(nullable=False)
    
    # Port target machine is listening to SSH (usually 22)
    ssh_port: int = Field(default=22)
    
    # Username for SSH login (e.g. "root" or "deploy")
    ssh_username: str = Field(default="root")
    
    # Either "password" or "key" (SSH private key authorization)
    ssh_auth_type: str = Field(default="password")
    
    # AES-encrypted password string or private key string
    encrypted_credential: str = Field(nullable=False)
    
    # Comma-separated list of tags (e.g. "production,web") for grouping and multi-execution
    tags: str = Field(default="")
    
    # Owner relation to user table
    owner_id: int = Field(foreign_key="user.id", nullable=False)
