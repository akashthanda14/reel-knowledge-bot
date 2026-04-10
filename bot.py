"""
Telegram bot — receives reel links, pushes jobs to Redis, waits for results.

Architecture:
  User → Telegram → bot.py → Redis queue → agent.py → Redis result → bot.py → User

bot.py no longer imports or calls agent.py directly.
The two containers communicate exclusively through Redis.
"""

import json
import os
import re
import uuid

import redis.asyncio as aioredis
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes, MessageHandler, filters

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Redis connection string. Inside Docker Compose, "redis" resolves to the
# Redis container because Compose puts all services on the same network
# and uses service names as hostnames.
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# The Redis list key that bot.py writes to and agent.py reads from.
JOB_QUEUE = "jobs:pending"

# How long (seconds) the bot waits for agent.py to finish before giving up.
# Downloading + transcribing a long video can take several minutes.
RESULT_TIMEOUT = 300

# Accepts YouTube and Instagram reel-like links.
URL_RE = re.compile(
    r"https?://"
    r"(?:www\.)?"
    r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/|instagram\.com/(?:reel|p)/)"
    r"[^\s]+"
)


async def post_init(application: Application) -> None:
    """Called once by python-telegram-bot after the app is built.
    Creates one shared Redis client for the lifetime of the bot process.
    Storing it in bot_data makes it accessible in every handler via
    context.bot_data["redis"] without creating a new connection per message."""
    application.bot_data["redis"] = aioredis.from_url(REDIS_URL)


async def post_shutdown(application: Application) -> None:
    """Called once when the bot is shutting down (Ctrl+C / SIGTERM).
    Closes the Redis connection cleanly so no resources are leaked."""
    await application.bot_data["redis"].aclose()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # 1) Extract URL from user message.
    text = update.message.text or ""
    match = URL_RE.search(text)

    if not match:
        await update.message.reply_text(
            "Send me an Instagram reel or YouTube link and I'll extract the key knowledge for you."
        )
        return

    url = match.group(0)

    # 2) Generate a unique ID for this job.
    # uuid4() produces a random 128-bit identifier — essentially impossible to collide.
    # It lets us create a per-job result key in Redis so concurrent requests
    # don't mix up each other's results.
    job_id = str(uuid.uuid4())

    await update.message.reply_text(f"Got it! Processing your reel...\n{url}")

    r: aioredis.Redis = context.bot_data["redis"]

    # 3) Push the job to the queue.
    # RPUSH appends to the right end of the Redis list "jobs:pending".
    # agent.py uses BLPOP which pops from the left — first in, first out.
    payload = json.dumps({"job_id": job_id, "url": url})
    await r.rpush(JOB_QUEUE, payload)

    # 4) Wait for agent.py to push the result.
    # BLPOP blocks until a value appears at the key or the timeout expires.
    # It returns a (key, value) tuple, or None on timeout.
    # This keeps the bot's event loop free — other Telegram messages are
    # handled normally while we wait for this job to finish.
    raw = await r.blpop(f"result:{job_id}", timeout=RESULT_TIMEOUT)

    if raw is None:
        await update.message.reply_text(
            "Timed out waiting for a result (5-minute limit). "
            "The reel may be too long or the agent may be overloaded."
        )
        return

    # 5) Parse and forward the result to the user.
    result = json.loads(raw[1])
    await update.message.reply_text(result["text"])


def main() -> None:
    # post_init and post_shutdown wire up the Redis client to the app lifecycle
    # so it is created once and closed cleanly — not once per message.
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
