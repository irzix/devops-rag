from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.modules.auth import User
from app.modules.auth.service import get_current_user
from app.modules.notifications.models import NotificationChannel
from app.modules.notifications.service import send_notification

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────


class ChannelCreate(BaseModel):
    name: str = Field(..., min_length=1)
    channel_type: str = Field(...)  # "telegram", "slack", "discord"
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    webhook_url: Optional[str] = None
    is_active: bool = True
    notify_on_health: bool = True
    notify_on_incident: bool = False


class ChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    is_active: Optional[bool] = None
    notify_on_health: Optional[bool] = None
    notify_on_incident: Optional[bool] = None


class ChannelResponse(BaseModel):
    id: int
    name: str
    channel_type: str
    is_active: bool
    notify_on_health: bool
    notify_on_incident: bool
    # Omit tokens/webhooks in standard list response for security, 
    # or obscure them. For simplicity in this demo, we return them.
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    webhook_url: Optional[str] = None

    class Config:
        from_attributes = True


class TestMessageRequest(BaseModel):
    message: str = "👋 Hello from DevOps Copilot! This is a test notification."


# ── Endpoints ────────────────────────────────────────────────


@router.post("/", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    payload: ChannelCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Register a new notification channel (Telegram/Slack/Discord)."""
    # Validation
    if payload.channel_type == "telegram":
        if not payload.bot_token or not payload.chat_id:
            raise HTTPException(
                status_code=400, 
                detail="bot_token and chat_id are required for telegram"
            )
    elif payload.channel_type in ["slack", "discord"]:
        if not payload.webhook_url:
            raise HTTPException(
                status_code=400, 
                detail=f"webhook_url is required for {payload.channel_type}"
            )
    else:
        raise HTTPException(status_code=400, detail="Invalid channel_type")

    channel = NotificationChannel(
        owner_id=current_user.id,
        name=payload.name,
        channel_type=payload.channel_type,
        bot_token=payload.bot_token,
        chat_id=payload.chat_id,
        webhook_url=payload.webhook_url,
        is_active=payload.is_active,
        notify_on_health=payload.notify_on_health,
        notify_on_incident=payload.notify_on_incident,
    )
    
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


@router.get("/", response_model=List[ChannelResponse])
async def list_channels(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all notification channels for the current user."""
    result = await session.exec(
        select(NotificationChannel).where(NotificationChannel.owner_id == current_user.id)
    )
    return result.all()


@router.put("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: int,
    payload: ChannelUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update settings (like active status) for a channel."""
    result = await session.exec(
        select(NotificationChannel)
        .where(NotificationChannel.id == channel_id)
        .where(NotificationChannel.owner_id == current_user.id)
    )
    channel = result.first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if payload.name is not None:
        channel.name = payload.name
    if payload.is_active is not None:
        channel.is_active = payload.is_active
    if payload.notify_on_health is not None:
        channel.notify_on_health = payload.notify_on_health
    if payload.notify_on_incident is not None:
        channel.notify_on_incident = payload.notify_on_incident

    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a notification channel."""
    result = await session.exec(
        select(NotificationChannel)
        .where(NotificationChannel.id == channel_id)
        .where(NotificationChannel.owner_id == current_user.id)
    )
    channel = result.first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    await session.delete(channel)
    await session.commit()
    return None


@router.post("/{channel_id}/test")
async def test_channel(
    channel_id: int,
    payload: TestMessageRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Send a test message to verify the channel configuration."""
    result = await session.exec(
        select(NotificationChannel)
        .where(NotificationChannel.id == channel_id)
        .where(NotificationChannel.owner_id == current_user.id)
    )
    channel = result.first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    success = await send_notification(channel, payload.message)
    if not success:
        raise HTTPException(
            status_code=500, 
            detail="Failed to send notification. Check server logs or token/webhook validity."
        )
        
    return {"status": "success", "message": "Test notification sent"}
