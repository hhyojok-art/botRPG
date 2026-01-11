import os
import asyncio
import discord
import logging
from discord.ext import commands
from dotenv import load_dotenv
from redis_client import is_bot_enabled
from database import get_prefix_db
import io
from PIL import Image, ImageDraw, ImageFont
from utils.fonts import load_font

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True


async def get_prefix(bot, message):
    # DM -> default prefix
    if not message.guild:
        return '!'
    prefix = get_prefix_db(message.guild.id)
    return prefix


bot = commands.Bot(command_prefix=get_prefix, intents=intents)

# ======================
# LOGGING
# ======================
logging.basicConfig(
    filename="logs/bot.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("bot")

# ======================
# GLOBAL CHECK
# ======================
@bot.check
async def maintenance_check(ctx):
    # Allow owner to run the maintenance toggle command even when maintenance is active,
    # but otherwise do NOT bypass maintenance for owners so maintenance truly blocks everyone.
    try:
        if ctx.command and ctx.command.name == 'maintenance':
            # allow owner to toggle maintenance
            try:
                if await bot.is_owner(ctx.author):
                    return True
            except Exception:
                pass
    except Exception:
        pass

    # debug: print current maintenance flag (cached)
    try:
        cached_val, cached_ts = None, None
        from redis_client import get_is_bot_enabled_cached
        cached_val, cached_ts = get_is_bot_enabled_cached()
        print(f"[maintenance_check] ctx.command={getattr(ctx.command,'name',None)} author={getattr(ctx.author,'id',None)} cached_enabled={cached_val} cached_ts={cached_ts}")
    except Exception:
        pass

    return await is_bot_enabled()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        # Jika maintenance aktif, kirim PNG bertuliskan 'Bot sedang maintenance' menggunakan font Undertale
        try:
            enabled = await is_bot_enabled()
        except Exception:
            enabled = True

        if not enabled:
            # Jika ada file maintenance.png di Assets/background, kirim file tersebut
            static_path = os.path.join(os.path.dirname(__file__), 'Assets', 'background', 'maintenance.png')
            try:
                if os.path.isfile(static_path):
                    await ctx.send(file=discord.File(static_path))
                    return
            except Exception:
                # jika gagal akses file, lanjut ke pembuatan gambar dinamis
                pass

            # fallback: buat gambar PNG dinamis
            width, height = 900, 300
            bg_color = (0, 0, 0)
            text_color = (255, 255, 255)
            text = "Bot sedang maintenance"

            img = Image.new('RGB', (width, height), color=bg_color)
            draw = ImageDraw.Draw(img)

            # try to load Undertale-first font via helper
            try:
                font = load_font(48)
            except Exception:
                font = ImageFont.load_default()

            # ukuran teks dan pos tengah
            text_w, text_h = draw.textsize(text, font=font)
            x = (width - text_w) / 2
            y = (height - text_h) / 2
            draw.text((x, y), text, font=font, fill=text_color)

            b = io.BytesIO()
            img.save(b, format='PNG')
            b.seek(0)
            try:
                await ctx.send(file=discord.File(b, filename='maintenance.png'))
            except Exception:
                # jika gagal kirim file, fallback ke embed
                await ctx.send(embed=discord.Embed(
                    title="🛠 Sedang Maintenance",
                    description="Bot sedang dalam mode maintenance. Coba lagi nanti.",
                    color=0xE67E22
                ))
            return
        # jika bukan maintenance, kirim embed default
        await ctx.send(embed=discord.Embed(
            title="🛠 Sedang Maintenance",
            description="Bot sedang dalam mode maintenance. Coba lagi nanti.",
            color=0xE67E22
        ))
        return

    # Friendly handling for common errors
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=discord.Embed(
            description=f"🚫 Kamu tidak punya izin: {error}",
            color=0xE74C3C
        ))
        return

    # Unwrap original exception if CommandInvokeError
    orig = getattr(error, 'original', error)
    # Log error with traceback
    logger.error("Unhandled command error: %s", repr(orig), exc_info=orig)

    # Notify user with friendly embed (no traceback)
    await ctx.send(embed=discord.Embed(
        title="❗ Terjadi Kesalahan",
        description="Ada kesalahan saat menjalankan command. Admin sudah diberitahu.",
        color=0xE74C3C
    ))

@bot.event
async def on_ready():
    logger.info(f"Bot ready as {bot.user} (ID: {bot.user.id})")
    try:
        await bot.tree.sync()
    except Exception:
        logger.exception("Failed to sync application commands")


# Global check for application (slash) commands so maintenance blocks them too
async def app_maintenance_check(interaction: discord.Interaction):
    try:
        # allow owner to toggle maintenance via slash
        if interaction.command and getattr(interaction.command, 'name', None) == 'maintenance':
            try:
                if await bot.is_owner(interaction.user):
                    return True
            except Exception:
                pass
    except Exception:
        pass

    # debug print for app commands
    try:
        from redis_client import get_is_bot_enabled_cached
        cached_val, cached_ts = get_is_bot_enabled_cached()
        print(f"[app_maintenance_check] cmd={getattr(interaction.command,'name',None)} user={getattr(interaction.user,'id',None)} cached_enabled={cached_val} cached_ts={cached_ts}")
    except Exception:
        pass

    return await is_bot_enabled()

# Register the check on the command tree (some discord.py versions don't support decorator)
try:
    bot.tree.add_check(app_maintenance_check)
except Exception:
    # fallback: ignore registration failure (older/newer versions)
    pass

# ======================
# AUTO LOAD COGS
# ======================
async def load_cogs():
    for file in os.listdir("cogs"):
        if file.endswith(".py"):
            await bot.load_extension(f"cogs.{file[:-3]}")

async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

asyncio.run(main())
