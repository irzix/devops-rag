from fastapi import APIRouter, Depends, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth import User
from app.modules.auth.service import get_current_user
from app.modules.servers.schema import ServerCreate, ServerUpdate, ServerResponse, CommandRequest, CommandResponse
from app.modules.servers.service import servers_service

router = APIRouter()

@router.post("/", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    server_in: ServerCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Register a new server connection under the logged-in administrator."""
    return await servers_service.create_server(session, server_in, current_user.id)

@router.get("/", response_model=List[ServerResponse])
async def list_servers(
    tag: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Retrieve all managed servers registered to the current administrator. Optionally filter by tag."""
    servers = await servers_service.get_all_servers(session, current_user.id)
    if tag:
        # Filter servers where the tag is exactly matched in the comma-separated list
        servers = [s for s in servers if s.tags and tag in [t.strip() for t in s.tags.split(',')]]
    return servers

@router.get("/tags", response_model=List[str])
async def get_server_tags(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Retrieve a list of unique tags across all servers."""
    servers = await servers_service.get_all_servers(session, current_user.id)
    tags = set()
    for s in servers:
        if s.tags:
            for t in s.tags.split(','):
                tags.add(t.strip())
    return sorted(list(tags))

@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Retrieve specific server credentials configuration metadata."""
    return await servers_service.get_server_by_id(session, server_id, current_user.id)

@router.put("/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: int,
    server_in: ServerUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update registry configuration metadata for a managed server."""
    return await servers_service.update_server(session, server_id, server_in, current_user.id)

@router.delete("/{server_id}")
async def delete_server(
    server_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a managed server registry."""
    return await servers_service.delete_server(session, server_id, current_user.id)

@router.post("/{server_id}/execute", response_model=CommandResponse)
async def execute_command(
    server_id: int,
    payload: CommandRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Execute arbitrary terminal commands asynchronously on target server via secure SSH connection."""
    server = await servers_service.get_server_by_id(session, server_id, current_user.id)
    return await servers_service.execute_ssh_command(server, payload.command)
