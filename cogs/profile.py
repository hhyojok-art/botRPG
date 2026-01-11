import discord
from discord.ext import commands
import os
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps
from utils.fonts import load_font
from database import get_user_xp, get_leaderboard, get_equipped_items, get_profile, get_selected_badge


def xp_to_level(xp: int) -> int:
    # Simple formula: 1 level per 100 XP
    return xp // 100


def level_progress(xp: int) -> tuple[int, int]:
    level = xp_to_level(xp)
    current = xp - (level * 100)
    return current, 100


def render_bar(current: int, total: int, length: int = 20) -> str:
    filled = int((current / total) * length) if total else 0
    bar = '█' * filled + '─' * (length - filled)
    percent = int((current / total) * 100) if total else 0
    return f"[{bar}] {percent}%"


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='profile', with_app_command=True)
    async def profile(self, ctx: commands.Context, member: discord.Member = None):
        """Tampilkan profile XP & level"""
        if member is None:
            member = ctx.author
        guild_id = ctx.guild.id if ctx.guild else 0
        xp = get_user_xp(guild_id, member.id)
        level = xp_to_level(xp)
        cur, total = level_progress(xp)
        bar = render_bar(cur, total)

        # We'll render a profile card image on top of background (like owo bot)
        # Determine equipped background (slot 'background')
        bg_name = None
        if ctx.guild:
            equipped = get_equipped_items(ctx.guild.id, member.id)
            for item_name, qty, slot in equipped:
                if slot and slot.lower() == 'background':
                    if '_' in item_name:
                        bg_name = item_name.split('_', 1)[1]
                    else:
                        parts = item_name.split()
                        if len(parts) > 1 and parts[0].lower() == 'background':
                            bg_name = '_'.join(parts[1:]).lower()
                        else:
                            bg_name = item_name.lower()
                    break

        if not bg_name:
            bg_name = 'default'

        bg_path = os.path.join('Assets', 'background', f"{bg_name}.png")
        if not os.path.exists(bg_path):
            alt = os.path.join('Assets', 'background', 'gray.png')
            if os.path.exists(alt):
                bg_path = alt
            else:
                bg_path = None

        # Fetch additional profile info
        prof = None
        if ctx.guild:
            prof = get_profile(ctx.guild.id, member.id)

        # Compose image
        try:
            if bg_path and os.path.exists(bg_path):
                bg = Image.open(bg_path).convert("RGBA")
            else:
                # fallback solid background
                bg = Image.new('RGBA', (900, 300), (54, 57, 63, 255))

            # standard card size
            CARD_W, CARD_H = 900, 300
            bg = bg.resize((CARD_W, CARD_H))

            # download avatar
            avatar_bytes = None
            async with aiohttp.ClientSession() as session:
                async with session.get(str(member.display_avatar.url)) as r:
                    if r.status == 200:
                        avatar_bytes = await r.read()

            if avatar_bytes:
                av = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
            else:
                av = Image.new('RGBA', (200, 200), (255, 255, 255, 255))

            # prepare avatar circle
            AV_SIZE = 180
            av = av.resize((AV_SIZE, AV_SIZE))
            mask = Image.new('L', (AV_SIZE, AV_SIZE), 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.ellipse((0, 0, AV_SIZE, AV_SIZE), fill=255)
            avatar_circle = ImageOps.fit(av, (AV_SIZE, AV_SIZE), centering=(0.5, 0.5))
            avatar_circle.putalpha(mask)

            card = Image.new('RGBA', (CARD_W, CARD_H))
            card.paste(bg, (0, 0))
            # paste avatar
            AV_X, AV_Y = 40, (CARD_H - AV_SIZE) // 2
            card.paste(avatar_circle, (AV_X, AV_Y), avatar_circle)

            draw = ImageDraw.Draw(card)

            # fonts (use Undertale font if available)
            try:
                font_bold = load_font(36)
                font_regular = load_font(20)
                font_small = load_font(16)
            except Exception:
                font_bold = ImageFont.load_default()
                font_regular = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # texts
            name_text = member.display_name
            level_text = f"Level {level}"
            xp_text = f"{xp} XP"
            progress_pct = int((cur / total) * 100) if total else 0

            # draw name and level
            TEXT_X = AV_X + AV_SIZE + 30
            TEXT_Y = AV_Y
            draw.text((TEXT_X, TEXT_Y), name_text, font=font_bold, fill=(255, 255, 255, 255))
            draw.text((TEXT_X, TEXT_Y + 44), level_text, font=font_regular, fill=(230, 230, 230, 255))
            draw.text((TEXT_X, TEXT_Y + 70), xp_text + f"  ({progress_pct}%)", font=font_regular, fill=(200, 200, 200, 255))

            # draw progress bar
            BAR_W, BAR_H = 420, 22
            BAR_X = TEXT_X
            BAR_Y = TEXT_Y + 110
            # background bar
            draw.rectangle([BAR_X, BAR_Y, BAR_X + BAR_W, BAR_Y + BAR_H], fill=(60, 60, 60, 200))
            # filled
            filled_w = int((cur / total) * BAR_W) if total else 0
            draw.rectangle([BAR_X, BAR_Y, BAR_X + filled_w, BAR_Y + BAR_H], fill=(50, 200, 120, 230))
            # bar border
            draw.rectangle([BAR_X, BAR_Y, BAR_X + BAR_W, BAR_Y + BAR_H], outline=(0, 0, 0, 150), width=1)

            # additional stats: atk/def/gold if available
            if prof:
                stats_text = f"ATK: {prof.get('atk',0)}   DEF: {prof.get('def',0)}   Gold: {prof.get('gold',0)}"
                draw.text((TEXT_X, BAR_Y + BAR_H + 12), stats_text, font=font_small, fill=(200,200,200,255))

            # draw selected badge icon if present
            badge_key = None
            if ctx.guild:
                try:
                    badge_key = get_selected_badge(ctx.guild.id, member.id)
                except Exception:
                    badge_key = None
            if badge_key:
                try:
                    badge_path = os.path.join('Assets', 'badges', f"{badge_key}.png")
                    if os.path.exists(badge_path):
                        badge_img = Image.open(badge_path).convert('RGBA')
                        BADGE_SIZE = 72
                        badge_img = badge_img.resize((BADGE_SIZE, BADGE_SIZE))
                        # paste badge at top-right of avatar
                        bx = AV_X + AV_SIZE - (BADGE_SIZE // 2)
                        by = AV_Y - (BADGE_SIZE // 2)
                        card.paste(badge_img, (bx, by), badge_img)
                except Exception:
                    pass

            # save to bytes
            bio = io.BytesIO()
            bio.name = 'profile.png'
            card.save(bio, 'PNG')
            bio.seek(0)

            file = discord.File(fp=bio, filename='profile.png')
            embed = discord.Embed(title=f"{member.display_name}'s Profile", color=0x1ABC9C)
            await ctx.reply(embed=embed, file=file)
        except Exception:
            # on failure fallback to simple embed
            embed = discord.Embed(title=f"{member.display_name}'s Profile", color=0x1ABC9C)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name='Level', value=str(level), inline=True)
            embed.add_field(name='XP', value=f"{xp} XP", inline=True)
            embed.add_field(name='Progress', value=bar, inline=False)
            # try to attach badge thumbnail if user has selected badge
            try:
                badge_key = None
                if ctx.guild:
                    badge_key = get_selected_badge(ctx.guild.id, member.id)
                if badge_key:
                    # try Assets/badges/<key>.png first
                    badge_path = os.path.join('Assets', 'badges', f"{badge_key}.png")
                    if os.path.exists(badge_path):
                        bfile = discord.File(badge_path, filename='badge.png')
                        embed.set_thumbnail(url='attachment://badge.png')
                        await ctx.reply(embed=embed, file=bfile)
                        return
                    # generate a small fallback badge image (initials)
                    name = BADGES.get(badge_key, (badge_key, ''))[0] if 'BADGES' in globals() else badge_key
                    initials = ''.join([w[0] for w in name.split()][:2]).upper() or badge_key[:2].upper()
                    bimg = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
                    bd = ImageDraw.Draw(bimg)
                    # circle background
                    bd.ellipse((0, 0, 128, 128), fill=(243,156,18,255))
                    # initials
                    try:
                        f = load_font(48)
                    except Exception:
                        f = ImageFont.load_default()
                    w, h = bd.textsize(initials, font=f)
                    bd.text(((128-w)/2, (128-h)/2), initials, font=f, fill=(255,255,255,255))
                    bb = io.BytesIO()
                    bb.name = 'badge.png'
                    bimg.save(bb, 'PNG')
                    bb.seek(0)
                    bfile = discord.File(bb, filename='badge.png')
                    embed.set_thumbnail(url='attachment://badge.png')
                    await ctx.reply(embed=embed, file=bfile)
                    return
            except Exception:
                pass
            await ctx.reply(embed=embed)

    @commands.hybrid_command(name='leaderboard', with_app_command=True)
    async def leaderboard(self, ctx: commands.Context, limit: int = 10):
        """Tampilkan leaderboard XP server"""
        if not ctx.guild:
            await ctx.reply("Leaderboard hanya untuk server")
            return
        rows = get_leaderboard(ctx.guild.id, limit=limit)
        if not rows:
            await ctx.reply("Belum ada data XP di server ini")
            return
        lines = []
        for i, (user_id, xp) in enumerate(rows, start=1):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            lines.append(f"**{i}. {name}** — `{xp} XP`")
        embed = discord.Embed(title='🏆 Leaderboard', description='Top users by XP', color=0xF1C40F)
        embed.add_field(name='Top', value='\n'.join(lines), inline=False)
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
