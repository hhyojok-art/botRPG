import logging
import os

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

logging.basicConfig(
    filename="logs/bot.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("bot")

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
