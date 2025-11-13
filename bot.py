# FILE: bot.py
"""
Telegram anti-spam bot entrypoint.
Runs webhook server using aiohttp and registers webhook on startup.
"""
import logging
import sys
from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import get_config
from storage import Store
from handlers import status_command, togglestrict_command, message_handler, error_handler
from actions import notify_startup

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def health_check(request):
    """Health check endpoint for Render."""
    return web.Response(text="ok", status=200)


async def webhook_handler(request):
    """Handle incoming webhook requests from Telegram."""
    try:
        # Get the application from the app state
        application: Application = request.app["telegram_app"]

        # Parse the update
        update_data = await request.json()
        update = Update.de_json(update_data, application.bot)

        # Process the update
        await application.process_update(update)

        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return web.Response(status=500)


async def setup_webhook(app: web.Application):
    """Set up webhook on application startup."""
    config = get_config()
    application: Application = app["telegram_app"]

    # Initialize Redis store
    store = Store(config.REDIS_URL)
    await store.connect()
    application.bot_data["store"] = store

    # Set webhook
    webhook_url = f"{config.PUBLIC_BASE_URL}/webhook"
    try:
        await application.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
        )
        logger.info(f"✅ Webhook set: {webhook_url}")

        # Send startup notification to admin channel
        await notify_startup(application.bot, config.ADMIN_LOG_CHAT_ID, webhook_url)

    except Exception as e:
        logger.error(f"❌ Failed to set webhook: {e}")
        raise


async def cleanup_webhook(app: web.Application):
    """Clean up resources on application shutdown."""
    application: Application = app["telegram_app"]

    # Close Redis connection
    store: Store = application.bot_data.get("store")
    if store:
        await store.close()

    # Delete webhook
    try:
        await application.bot.delete_webhook()
        logger.info("Webhook deleted")
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")


def create_app() -> web.Application:
    """Create and configure the aiohttp application."""
    config = get_config()

    # Create Telegram application
    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("togglestrict", togglestrict_command))
    application.add_handler(
        MessageHandler(filters.TEXT | filters.CAPTION, message_handler)
    )
    application.add_error_handler(error_handler)

    # Create aiohttp app
    app = web.Application()
    app["telegram_app"] = application

    # Add routes
    app.router.add_get("/healthz", health_check)
    app.router.add_post("/webhook", webhook_handler)

    # Add startup/cleanup hooks
    app.on_startup.append(setup_webhook)
    app.on_cleanup.append(cleanup_webhook)

    return app


def main():
    """Main entry point."""
    try:
        config = get_config()
        logger.info(f"Starting bot on {config.HOST}:{config.PORT}")
        logger.info(f"Webhook URL: {config.PUBLIC_BASE_URL}/webhook")
        logger.info(f"Health check: {config.PUBLIC_BASE_URL}/healthz")

        app = create_app()
        web.run_app(app, host=config.HOST, port=config.PORT)

    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
