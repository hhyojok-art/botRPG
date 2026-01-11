import logging
import os
import sys

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

# File handler
logging.basicConfig(
    filename="logs/bot.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# Also log to stdout so hosting platforms show logs
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
console_handler.setFormatter(console_formatter)

logger = logging.getLogger("bot")
logger.addHandler(console_handler)

async def log_to_channel(bot, message: str):
    if not LOG_CHANNEL_ID:
        return
    try:
        channel_id = int(LOG_CHANNEL_ID)
    except Exception:
        return
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send(f"📜 `{message}`")
