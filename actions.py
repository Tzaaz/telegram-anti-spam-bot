# FILE: actions.py
"""
Moderation actions: delete, warn, mute, ban, and admin logging.
"""
import logging
from datetime import datetime, timedelta
from telegram import Bot, ChatPermissions
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


async def delete_message(bot: Bot, chat_id: int, message_id: int) -> bool:
    """
    Delete a message from a chat.

    Returns:
        True if successful, False otherwise
    """
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"✅ Deleted message {message_id} in chat {chat_id}")
        return True
    except TelegramError as e:
        logger.error(f"❌ Failed to delete message {message_id}: {e}")
        return False


async def send_warning(
    bot: Bot, chat_id: int, user_id: int, username: str, reason: str
) -> bool:
    """
    Send a warning message to the chat.

    Returns:
        True if successful, False otherwise
    """
    try:
        user_mention = f"@{username}" if username else f"User {user_id}"
        warning_text = (
            f"⚠️ Warning {user_mention}: Your message was flagged.\n"
            f"Reason: {reason}\n"
            f"Please avoid posting spam or suspicious content."
        )
        await bot.send_message(chat_id=chat_id, text=warning_text)
        logger.info(f"✅ Sent warning to user {user_id} in chat {chat_id}")
        return True
    except TelegramError as e:
        logger.error(f"❌ Failed to send warning: {e}")
        return False


async def mute_user(
    bot: Bot, chat_id: int, user_id: int, duration_hours: int = 24
) -> bool:
    """
    Mute a user in a chat for specified duration.

    Args:
        bot: Bot instance
        chat_id: Chat ID
        user_id: User ID to mute
        duration_hours: Mute duration in hours (default 24)

    Returns:
        True if successful, False otherwise
    """
    try:
        until_date = datetime.now() + timedelta(hours=duration_hours)
        # Restrict all permissions
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
        )
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions,
            until_date=until_date,
        )
        logger.info(
            f"✅ Muted user {user_id} in chat {chat_id} for {duration_hours}h"
        )
        return True
    except TelegramError as e:
        logger.error(f"❌ Failed to mute user {user_id}: {e}")
        return False


async def ban_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Ban a user from a chat.

    Returns:
        True if successful, False otherwise
    """
    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        logger.info(f"✅ Banned user {user_id} from chat {chat_id}")
        return True
    except TelegramError as e:
        logger.error(f"❌ Failed to ban user {user_id}: {e}")
        return False


async def log_to_admin_channel(
    bot: Bot,
    admin_chat_id: int,
    action: str,
    chat_id: int,
    user_id: int,
    username: str,
    score: int,
    reasons: str,
):
    """
    Send a compact log entry to the admin log channel.

    Args:
        bot: Bot instance
        admin_chat_id: Admin channel chat ID
        action: Action taken (WARN, DELETE, MUTE, BAN)
        chat_id: Chat where action occurred
        user_id: Target user ID
        username: Target username (or None)
        score: Spam score
        reasons: Comma-separated list of reasons
    """
    try:
        user_mention = f"@{username}" if username else f"ID:{user_id}"
        log_text = (
            f"🔴 [{action}] Chat:{chat_id}\n"
            f"User: {user_mention} ({user_id})\n"
            f"Score: {score} | {reasons}"
        )
        await bot.send_message(chat_id=admin_chat_id, text=log_text)
        logger.debug(f"✅ Logged {action} to admin channel")
    except TelegramError as e:
        logger.error(f"❌ Failed to log to admin channel: {e}")


async def notify_startup(bot: Bot, admin_chat_id: int, webhook_url: str):
    """
    Send a startup notification to the admin log channel.

    Args:
        bot: Bot instance
        admin_chat_id: Admin channel chat ID
        webhook_url: Webhook URL that was set
    """
    try:
        startup_text = (
            f"🚀 Bot started successfully!\n"
            f"Webhook: {webhook_url}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        await bot.send_message(chat_id=admin_chat_id, text=startup_text)
        logger.info("✅ Sent startup notification to admin channel")
    except TelegramError as e:
        logger.error(f"❌ Failed to send startup notification: {e}")
