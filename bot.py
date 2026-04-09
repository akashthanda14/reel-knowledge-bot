"""
Telegram bot — receives reel links and runs the agent pipeline.
"""

import asyncio
import os
import re

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from agent import process_url

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Accepts YouTube and Instagram reel-like links.
URL_RE = re.compile(
    r"https?://"
    r"(?:www\.)?"
    r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/|instagram\.com/(?:reel|p)/)"
    r"[^\s]+"
)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # 1) Extract URL from user message
    text = update.message.text or ""
    match = URL_RE.search(text)

    if not match:
        await update.message.reply_text(
            "Send me an Instagram reel or YouTube link and I'll extract the key knowledge for you."
        )
        return

    url = match.group(0)
    await update.message.reply_text(f"Got it! Processing your reel...\n{url}")

    try:
        # 2) Run full pipeline (download -> transcribe -> classify -> save)
        result = await process_url(url)
        # 3) Send final summary/status back to Telegram
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Something went wrong: {e}")


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
