from sqlmodel import SQLModel, Field
from typing import Optional


class NotificationChannel(SQLModel, table=True):
    """Configuration for sending alerts to external platforms."""

    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True, nullable=False)

    name: str = Field(nullable=False)  # e.g., "My Telegram", "DevOps Slack"
    channel_type: str = Field(nullable=False)  # "telegram", "slack", "discord"

    # Telegram specific
    bot_token: Optional[str] = Field(default=None)
    chat_id: Optional[str] = Field(default=None)

    # Slack / Discord specific
    webhook_url: Optional[str] = Field(default=None)

    is_active: bool = Field(default=True)
    notify_on_health: bool = Field(default=True)
    notify_on_incident: bool = Field(default=False)
