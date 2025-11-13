# FILE: handlers.py
"""
Telegram command and message handlers.
"""
import logging
from telegram import Update, ChatMemberOwner, ChatMemberAdministrator
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from config import get_config
from storage import Store
from rules import calculate_spam_score, get_rules_config
from actions import (
    delete_message,
    send_warning,
    mute_user,
    ban_user,
    log_to_admin_channel,
)
from utils import extract_text_from_message

logger = logging.getLogger(__name__)


async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the message sender is a chat admin or owner."""
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return isinstance(member, (ChatMemberOwner, ChatMemberAdministrator))
    except TelegramError as e:
        logger.error(f"Error checking admin status: {e}")
        return False


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /status command.
    Shows bot status, Redis connection, and strict mode state.
    """
    config = get_config()
    store: Store = context.bot_data.get("store")

    # Check Redis health
    redis_status = "N/A"
    if store:
        is_healthy = await store.healthy()
        redis_status = "OK" if is_healthy else "ERROR"

    # Check strict mode for this chat
    strict_status = "OFF"
    if store and update.effective_chat:
        is_strict = await store.is_strict_mode(update.effective_chat.id)
        strict_status = "ON" if is_strict else "OFF"

    status_text = (
        f"✅ Bot online\n"
        f"Redis: {redis_status}\n"
        f"Strict Mode: {strict_status}"
    )

    await update.message.reply_text(status_text)
    logger.info(f"Status command executed by user {update.effective_user.id}")


async def togglestrict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /togglestrict command.
    Toggles strict mode for the current chat (admin only).
    """
    # Check if user is admin
    if not await is_user_admin(update, context):
        await update.message.reply_text("❌ Only admins can toggle strict mode.")
        return

    store: Store = context.bot_data.get("store")
    if not store:
        await update.message.reply_text("❌ Redis not available.")
        return

    chat_id = update.effective_chat.id
    new_state = await store.toggle_strict_mode(chat_id)

    status_emoji = "🔴" if new_state else "🟢"
    status_text = "ENABLED" if new_state else "DISABLED"
    await update.message.reply_text(f"{status_emoji} Strict mode {status_text}")

    logger.info(
        f"Strict mode toggled to {new_state} in chat {chat_id} "
        f"by user {update.effective_user.id}"
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle incoming messages for spam detection.
    Scores messages and takes appropriate action based on thresholds.
    """
    # Skip if no message or no text/caption
    if not update.message:
        return

    message = update.message
    text = extract_text_from_message(message)

    if not text:
        return  # Nothing to analyze

    chat_id = message.chat_id
    user_id = message.from_user.id
    username = message.from_user.username
    message_id = message.message_id

    config = get_config()
    store: Store = context.bot_data.get("store")

    # Safety check: never act on admins
    if await is_user_admin(update, context):
        logger.debug(f"Skipping admin user {user_id}")
        return

    # Check whitelist
    if store and await store.is_whitelisted(chat_id, user_id):
        logger.debug(f"Skipping whitelisted user {user_id}")
        return

    # Check blacklist (immediate action)
    if store and await store.is_blacklisted(chat_id, user_id):
        logger.info(f"Blacklisted user {user_id} detected, banning")
        await delete_message(context.bot, chat_id, message_id)
        await ban_user(context.bot, chat_id, user_id)
        await log_to_admin_channel(
            context.bot,
            config.ADMIN_LOG_CHAT_ID,
            "BAN",
            chat_id,
            user_id,
            username,
            score=999,
            reasons="Blacklisted user",
        )
        return

    # Dedup check
    if store and await store.is_duplicate(chat_id, text):
        logger.debug(f"Duplicate content detected, skipping")
        return

    # Get strict mode state
    strict_mode = False
    if store:
        strict_mode = await store.is_strict_mode(chat_id)

    # Calculate spam score
    rules_config = get_rules_config()
    spam_score = calculate_spam_score(text, strict_mode, rules_config)

    logger.info(
        f"Message from user {user_id} in chat {chat_id}: "
        f"score={spam_score.total}, reasons={spam_score.reasons}"
    )

    # No action needed if score is below warning threshold
    if not spam_score.should_warn and not spam_score.should_delete:
        return

    # Mark as processed to avoid duplicate actions
    if store:
        await store.mark_as_processed(chat_id, text)

    # Take action based on score
    if spam_score.should_delete:
        # Hard delete: delete message and apply strike policy
        await delete_message(context.bot, chat_id, message_id)

        # Get current strikes
        current_strikes = 0
        if store:
            current_strikes = await store.get_strikes(chat_id, user_id)

        # Increment strikes
        new_strikes = 0
        if store:
            new_strikes = await store.increment_strikes(chat_id, user_id)
        else:
            new_strikes = current_strikes + 1

        # Apply strike policy
        action_taken = "DELETE"
        if new_strikes == 1:
            # First offense: warn
            await send_warning(
                context.bot,
                chat_id,
                user_id,
                username,
                f"Spam detected (score: {spam_score.total})",
            )
            action_taken = "DELETE+WARN"
        elif new_strikes == 2:
            # Second offense: mute for 24h
            await mute_user(context.bot, chat_id, user_id, duration_hours=24)
            action_taken = "DELETE+MUTE"
        else:
            # Third+ offense: ban
            await ban_user(context.bot, chat_id, user_id)
            action_taken = "DELETE+BAN"

        # Log to admin channel
        await log_to_admin_channel(
            context.bot,
            config.ADMIN_LOG_CHAT_ID,
            action_taken,
            chat_id,
            user_id,
            username,
            spam_score.total,
            ", ".join(spam_score.reasons),
        )

    elif spam_score.should_warn:
        # Just a warning, no deletion
        await send_warning(
            context.bot,
            chat_id,
            user_id,
            username,
            f"Suspicious content (score: {spam_score.total})",
        )
        await log_to_admin_channel(
            context.bot,
            config.ADMIN_LOG_CHAT_ID,
            "WARN",
            chat_id,
            user_id,
            username,
            spam_score.total,
            ", ".join(spam_score.reasons),
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=True)
