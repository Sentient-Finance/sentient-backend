"""
Telegram bot for Sentient Finance alert channel registration.

Handles the connect-token flow:
  /start             → show welcome message with usage instructions
  /start <token>     → validate token, confirm channel registration

Run:
    python -m apps.telegram_bot.main

Or via the Makefile / docker-compose.

Required env vars:
    TELEGRAM_BOT_TOKEN      — bot token from @BotFather
    ALERTS_API_URL          — base URL of the alerts API (e.g. http://localhost:8000)
    TELEGRAM_ADMIN_IDS      — comma-separated list of Telegram user IDs that can use /alert
                               (optional; leave empty to disable admin commands)
"""

from __future__ import annotations

import logging
import os
import sys
import urllib.request
from typing import Any

# Ensure libs/ is on the path (needed when running as module)
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

try:
    from telegram import Update
    from telegram.constants import ParseMode
    from telegram.ext import (
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
except ImportError:
    sys.stderr.write(
        "Error: python-telegram-bot is not installed. Run: pip install python-telegram-bot\n"
    )
    sys.exit(1)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALERTS_API_URL = os.environ.get("ALERTS_API_URL", "http://localhost:8000").rstrip("/")
ADMIN_IDS = set()
_raw_admin = os.environ.get("TELEGRAM_ADMIN_IDS", "")
if _raw_admin:
    for _uid in _raw_admin.split(","):
        _uid = _uid.strip()
        if _uid:
            ADMIN_IDS.add(str(_uid))

if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable is not set")
    sys.exit(1)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def _api_call(
    method: str, path: str, data: dict[str, Any] | None = None
) -> dict | None:
    """Call the alerts API. Returns JSON dict or None on error."""
    url = f"{ALERTS_API_URL}{path}"
    try:
        import json

        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("API call failed: %s %s → %s", method, url, exc)
        return None


def _confirm_channel(connect_token: str, chat_id: str) -> dict | None:
    return _api_call(
        "POST",
        "/api/v1/alerts/channels/confirm",
        {
            "connect_token": connect_token,
            "chat_id": chat_id,
        },
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — with or without a connect token."""
    if not update.effective_user or not update.effective_chat or not update.message:
        return

    chat_id = str(update.effective_chat.id)

    if context.args:
        # /start <connect_token>
        token = context.args[0].strip()
        if len(token) < 10:
            await update.message.reply_text(
                "⚠️ That doesn't look like a valid connect token.\n"
                "Please use the link provided by the Sentient Finance app.",
                parse_mode=ParseMode.HTML,
            )
            return

        await update.message.reply_text("🔗 Verifying your token…")

        result = _confirm_channel(token, chat_id)
        if result and result.get("ok"):
            await update.message.reply_text(
                "✅ <b>Channel connected!</b>\n\n"
                "You'll now receive price alerts from Sentient Finance "
                "directly to this chat.\n\n"
                "Use /alert to test, or /stop to disconnect.",
                parse_mode=ParseMode.HTML,
            )
            logger.info(
                "Telegram channel confirmed: chat_id=%s channel_id=%s status=%s",
                chat_id,
                result.get("channel_id"),
                result.get("status"),
            )
        elif result and result.get("detail"):
            # Token expired or not found
            await update.message.reply_text(
                f"❌ {result['detail']}\n\n"
                "Please request a new link from the Sentient Finance app.",
            )
        else:
            await update.message.reply_text(
                "❌ Could not verify your token. Please try again later or "
                "request a new link from the Sentient Finance app.",
            )
    else:
        # No token — just a friendly welcome
        await update.message.reply_text(
            "👋 <b>Welcome to Sentient Finance Alerts!</b>\n\n"
            "This bot sends you real-time price alerts for your DeFi vaults.\n\n"
            "<b>To connect:</b>\n"
            "1. Open the Sentient Finance app\n"
            "2. Go to Notifications → Add Telegram\n"
            "3. Click the deep link to register this chat\n\n"
            "<b>Commands:</b>\n"
            "/alert — Send a test alert\n"
            "/stop — Disconnect this channel",
            parse_mode=ParseMode.HTML,
        )


async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a test alert to this chat (admins only)."""
    if not update.effective_user or not update.effective_chat or not update.message:
        return

    user_id = str(update.effective_user.id)

    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔ You are not authorized to use this command."
        )
        return

    if context.args:
        message = " ".join(context.args)
    else:
        message = (
            "🧪 <b>Test Alert</b>\n\n"
            "This is a test message from Sentient Finance.\n"
            "If you're seeing this, your Telegram alerts are working!"
        )

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the user's Telegram notification channel via the API."""
    if not update.effective_user or not update.effective_chat or not update.message:
        return

    chat_id = str(update.effective_chat.id)

    # Find the channel by chat_id first, then delete by internal channel_id
    channel = _api_call(
        "GET",
        f"/api/v1/alerts/channels/by-chat_id?chat_id={chat_id}",
    )

    if not channel:
        await update.message.reply_text(
            "❌ No connected channel found for this chat.\n\n"
            "If you've already disconnected, you can ignore this message.",
        )
        return

    channel_id = channel.get("id")
    if not channel_id:
        await update.message.reply_text(
            "❌ Could not determine your channel ID. Please try again later.",
        )
        return

    result = _api_call(
        "DELETE",
        f"/api/v1/alerts/channels/{channel_id}",
    )

    if result is None:
        await update.message.reply_text(
            "❌ Failed to disconnect. Please try again later.",
        )
    else:
        await update.message.reply_text(
            "👋 You've been disconnected from Sentient Finance alerts.\n\n"
            "To re-connect, use the deep link from the Sentient Finance app.",
        )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any unrecognized command."""
    await update.message.reply_text(
        "🤔 I don't understand that command.\n\n" "Try /start to get started.",
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning("Telegram error: %s %s", context.error, update)


# ---------------------------------------------------------------------------
# Polling mode (default for development)
# ---------------------------------------------------------------------------


def run_polling_mode() -> None:
    """Run the bot using long polling (development mode)."""
    import telegram.ext

    app = telegram.ext.ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    app.add_error_handler(error_handler)

    logger.info("Bot starting in polling mode — press Ctrl+C to stop")
    app.run_polling(drop_pending_updates=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_polling_mode()
