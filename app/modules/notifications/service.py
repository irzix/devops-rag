import logging
import httpx
from sqlmodel import select

from app.core.database import async_session_maker
from app.modules.notifications.models import NotificationChannel
from app.modules.servers.models import Server
from app.modules.monitoring.models import HealthCheck

logger = logging.getLogger("notifications.service")


async def send_telegram(bot_token: str, chat_id: str, message: str) -> bool:
    """Send a Markdown message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False


async def send_slack(webhook_url: str, message: str) -> bool:
    """Send a message via Slack incoming webhook."""
    payload = {"text": message}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False


async def send_discord(webhook_url: str, message: str) -> bool:
    """Send a message via Discord incoming webhook."""
    payload = {"content": message}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Failed to send Discord notification: {e}")
        return False


async def send_notification(channel: NotificationChannel, message: str) -> bool:
    """Route the message to the correct platform sender."""
    if not channel.is_active:
        return False

    if channel.channel_type == "telegram":
        if not channel.bot_token or not channel.chat_id:
            return False
        return await send_telegram(channel.bot_token, channel.chat_id, message)

    elif channel.channel_type == "slack":
        if not channel.webhook_url:
            return False
        return await send_slack(channel.webhook_url, message)

    elif channel.channel_type == "discord":
        if not channel.webhook_url:
            return False
        return await send_discord(channel.webhook_url, message)

    return False


async def send_health_alert(server: Server, health: HealthCheck):
    """Format and send a health alert to all active channels for the server owner."""
    async with async_session_maker() as session:
        result = await session.exec(
            select(NotificationChannel)
            .where(NotificationChannel.owner_id == server.owner_id)
            .where(NotificationChannel.is_active == True)
            .where(NotificationChannel.notify_on_health == True)
        )
        channels = result.all()

    if not channels:
        return

    # Determine emoji based on status
    emoji = "🔴" if health.status == "unreachable" else "🟡"
    
    # Format message (Markdown compatible for Telegram)
    msg = f"{emoji} **Health Alert: {server.name}**\n\n"
    msg += f"**Status:** {health.status.upper()}\n"
    msg += f"**IP:** `{server.ip_address}`\n\n"

    if health.status == "unreachable":
        msg += f"**Error:** {health.error_message or 'Unknown connection error'}\n"
    else:
        msg += f"**CPU:** {health.cpu_percent or '?'}%\n"
        msg += f"**RAM:** {health.memory_percent or '?'}%\n"
        msg += f"**Disk:** {health.disk_percent or '?'}%\n"

    for channel in channels:
        await send_notification(channel, msg)
