import json
import random
import discord
from discord.ext import commands
from pathlib import Path
import io
from PIL import Image, ImageDraw, ImageFont, ImageOps
from database import (
    get_profile,
    update_profile,
    add_user_xp,
    add_gold,
    get_user_xp,
    get_effective_profile,
    get_onboarded,
    set_onboarded,
    get_inventory,
    add_item,
    increment_daily_progress,
    add_win,
    award_achievement,
)
from utils.fonts import load_font


DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
MONSTER_FILE = DATA_DIR / 'monsters.json'


def xp_to_level(xp: int) -> int:
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


def load_monsters():
    try:
        with open(MONSTER_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # log what was loaded for easier debugging in runtime
        import logging
        logger = logging.getLogger('bot')
        try:
            count = len(data) if isinstance(data, list) else 1
        except Exception:
            count = 0
        try:
            size = MONSTER_FILE.stat().st_size
        except Exception:
            size = 0
        logger.info(f"[rpg] load_monsters: loaded {count} monsters from {MONSTER_FILE} (size={size} bytes)")
        return data
    except Exception as e:
        import logging
        logger = logging.getLogger('bot')
        exists = MONSTER_FILE.exists()
        try:
            size = MONSTER_FILE.stat().st_size if exists else 0
        except Exception:
            size = 0
        logger.exception(f"[rpg] load_monsters: failed to load {MONSTER_FILE} exists={exists} size={size}")
        return []


def save_monsters(lst):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(MONSTER_FILE, 'w', encoding='utf-8') as f:
        json.dump(lst, f, ensure_ascii=False, indent=2)


class RPG(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='adventure', with_app_command=True)
    async def adventure(self, ctx: commands.Context):
        """Pergi berpetualang: lawan monster, dapat XP & gold"""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        # Cooldown: 1 hour (3600s)
        from database import get_cooldown, set_cooldown
        import time
        last = get_cooldown(ctx.guild.id, ctx.author.id, 'adventure')
        now = int(time.time())
        # owners bypass cooldown
        try:
            is_owner = await self.bot.is_owner(ctx.author)
        except Exception:
            is_owner = False
        if not is_owner:
            if last and now - last < 3600:
                remaining = 3600 - (now - last)
                m, s = divmod(remaining, 60)
                await ctx.reply(f'⌛ Kamu harus menunggu {m} menit {s} detik sebelum berpetualang lagi.')
                return

        # Onboarding: first time user uses adventure, show short Indonesian tutorial
        try:
            onboarded = get_onboarded(ctx.guild.id, ctx.author.id)
        except Exception:
            onboarded = False
        if not onboarded:
            emb = discord.Embed(title='Selamat datang di Adventure!', description='Panduan singkat untuk memulai:', color=0xF39C12)
            emb.add_field(name='Mulai', value='Gunakan `!adventure` untuk pergi berpetualang melawan monster dan dapatkan XP serta gold.', inline=False)
            emb.add_field(name='Ekonomi & Inventory', value='Gunakan `!shop` untuk melihat item, `!buy <item>` untuk membelinya dengan XP, dan `!inventory` untuk melihat item kamu.', inline=False)
            emb.add_field(name='Perlengkapan', value='Pakailah `!equip <item>` untuk menambah ATK/DEF. Lepas dengan `!unequip`.', inline=False)
            emb.add_field(name='Potion & Quest', value='Klaim potion dengan `!claim` dan cek quest harian dengan `!quest` (auto klaim saat selesai).', inline=False)
            emb.set_footer(text='Selamat bermain — semoga beruntung!')
            await ctx.reply(embed=emb)
            try:
                set_onboarded(ctx.guild.id, ctx.author.id)
            except Exception:
                pass

        # use effective profile (includes temporary buffs)
        profile = get_effective_profile(ctx.guild.id, ctx.author.id)
        user_hp = get_profile(ctx.guild.id, ctx.author.id)['hp']
        user_atk = profile.get('atk', 0)
        user_def = profile.get('def', 0)

        monsters = load_monsters()
        if not monsters:
            await ctx.reply('No monsters configured. Owner can add monsters.')
            return
        monster = random.choice(monsters).copy()
        mon_hp = monster.get('hp', 10)

        log = []
        # simple battle loop
        while user_hp > 0 and mon_hp > 0:
            # user hits
            dmg = max(1, user_atk - monster['def'])
            mon_hp -= dmg
            log.append(f"You hit {monster['name']} for {dmg} dmg. ({max(0, mon_hp)} hp left)")
            if mon_hp <= 0:
                break
            # monster hits
            mdmg = max(1, monster['atk'] - user_def)
            user_hp -= mdmg
            log.append(f"{monster['name']} hits you for {mdmg} dmg. ({max(0, user_hp)} hp left)")

        # set cooldown now
        set_cooldown(ctx.guild.id, ctx.author.id, 'adventure', now)

        # locate monster image (Assets/Mob/Transperent)
        ASSETS_DIR = Path(__file__).resolve().parents[1] / 'Assets' / 'Mob' / 'Transperent'
        monster_image_path = None
        try:
            if ASSETS_DIR.exists():
                for p in ASSETS_DIR.iterdir():
                    if p.is_file() and p.stem.lower() == monster['name'].lower():
                        monster_image_path = p
                        break
        except Exception:
            monster_image_path = None

        if user_hp > 0:
            # win
            xp_gain = monster['xp'] + random.randint(0, 5)
            gold_gain = monster['gold'] + random.randint(0, 5)
            add_user_xp(ctx.guild.id, ctx.author.id, xp_gain)
            add_gold(ctx.guild.id, ctx.author.id, gold_gain)
            # small chance to drop item
            if random.random() < 0.15:
                item = 'Mysterious Shard'
                add_item(ctx.guild.id, ctx.author.id, item)
                drop_text = f"You found an item: **{item}**!"
            else:
                drop_text = ''

            # increment daily 'adventures' quest progress automatically
            try:
                increment_daily_progress(ctx.guild.id, ctx.author.id, amount=1)
            except Exception:
                pass
            # increment win counter and auto-award 'slayer' badge at 10 wins
            try:
                wins = add_win(ctx.guild.id, ctx.author.id, amount=1)
                if wins >= 10:
                    award_achievement(ctx.guild.id, ctx.author.id, 'slayer')
            except Exception:
                pass

            title = "🏹 Adventure — Victory!"
            desc = f"You defeated {monster['name']}!\n+{xp_gain} XP, +{gold_gain} gold\n{drop_text}"
            color = 0x2ECC71

            # Render a battle card: left text, right-top 1:1 monster image
            CARD_W, CARD_H = 900, 340
            PADDING = 20
            MON_SIZE = 280
            card = Image.new('RGBA', (CARD_W, CARD_H), (30, 30, 30, 255))
            draw = ImageDraw.Draw(card)

            # fonts (prefer undertale if available)
            try:
                font_bold = load_font(36)
                font_reg = load_font(20)
            except Exception:
                font_bold = ImageFont.load_default()
                font_reg = ImageFont.load_default()

            # draw title and desc
            text_x = PADDING
            text_y = PADDING
            draw.text((text_x, text_y), title, font=font_bold, fill=(255, 255, 255, 255))
            desc_y = text_y + 44
            draw.text((text_x, desc_y), desc, font=font_reg, fill=(220, 220, 220, 255))

            # draw battle log lines
            log_lines = log[-6:]
            log_y = desc_y + 70
            for i, line in enumerate(log_lines):
                draw.text((text_x, log_y + i * 22), line, font=font_reg, fill=(200, 200, 200, 255))

            # paste monster image at right-top with 1:1 ratio
            if monster_image_path and monster_image_path.exists():
                try:
                    mon_img = Image.open(monster_image_path).convert('RGBA')
                    mon_img = ImageOps.fit(mon_img, (MON_SIZE, MON_SIZE), centering=(0.5, 0.5))
                except Exception:
                    mon_img = Image.new('RGBA', (MON_SIZE, MON_SIZE), (80, 80, 80, 255))
            else:
                mon_img = Image.new('RGBA', (MON_SIZE, MON_SIZE), (80, 80, 80, 255))

            mon_x = CARD_W - MON_SIZE - PADDING
            mon_y = PADDING
            border_box = (mon_x - 6, mon_y - 6, mon_x + MON_SIZE + 6, mon_y + MON_SIZE + 6)
            draw.rectangle(border_box, fill=(0, 0, 0, 180))
            card.paste(mon_img, (mon_x, mon_y), mon_img)

            bio = io.BytesIO()
            bio.name = 'adventure.png'
            card.save(bio, 'PNG')
            bio.seek(0)
            file = discord.File(bio, filename='adventure.png')

            embed = discord.Embed(title=title, description=desc, color=color)
            await ctx.reply(embed=embed, file=file)
        else:
            # lose: set HP to 1 (can't go below), maybe penalty
            update_profile(ctx.guild.id, ctx.author.id, hp=1)
            title = "💀 Adventure — Defeat"
            desc = f"You were defeated by {monster['name']}."
            color = 0xE74C3C

            CARD_W, CARD_H = 900, 340
            PADDING = 20
            MON_SIZE = 280
            card = Image.new('RGBA', (CARD_W, CARD_H), (30, 30, 30, 255))
            draw = ImageDraw.Draw(card)

            # fonts (prefer undertale if available)
            try:
                font_bold = load_font(36)
                font_reg = load_font(20)
            except Exception:
                font_bold = ImageFont.load_default()
                font_reg = ImageFont.load_default()

            text_x = PADDING
            text_y = PADDING
            draw.text((text_x, text_y), title, font=font_bold, fill=(255, 255, 255, 255))
            desc_y = text_y + 44
            draw.text((text_x, desc_y), desc, font=font_reg, fill=(220, 220, 220, 255))
            log_lines = log[-6:]
            log_y = desc_y + 70
            for i, line in enumerate(log_lines):
                draw.text((text_x, log_y + i * 22), line, font=font_reg, fill=(200, 200, 200, 255))

            if monster_image_path and monster_image_path.exists():
                try:
                    mon_img = Image.open(monster_image_path).convert('RGBA')
                    mon_img = ImageOps.fit(mon_img, (MON_SIZE, MON_SIZE), centering=(0.5, 0.5))
                except Exception:
                    mon_img = Image.new('RGBA', (MON_SIZE, MON_SIZE), (80, 80, 80, 255))
            else:
                mon_img = Image.new('RGBA', (MON_SIZE, MON_SIZE), (80, 80, 80, 255))

            mon_x = CARD_W - MON_SIZE - PADDING
            mon_y = PADDING
            border_box = (mon_x - 6, mon_y - 6, mon_x + MON_SIZE + 6, mon_y + MON_SIZE + 6)
            draw.rectangle(border_box, fill=(0, 0, 0, 180))
            card.paste(mon_img, (mon_x, mon_y), mon_img)

            bio = io.BytesIO()
            bio.name = 'adventure.png'
            card.save(bio, 'PNG')
            bio.seek(0)
            file = discord.File(bio, filename='adventure.png')

            embed = discord.Embed(title=title, description=desc, color=color)
            await ctx.reply(embed=embed, file=file)

    @commands.hybrid_command(name='rpgstats', with_app_command=True)
    async def rpgstats(self, ctx: commands.Context, member: discord.Member = None):
        """Tampilkan RPG stats (HP/ATK/DEF/GOLD/XP/Level)"""
        if member is None:
            member = ctx.author
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        profile = get_profile(ctx.guild.id, member.id)
        xp = get_user_xp(ctx.guild.id, member.id)
        level = xp_to_level(xp)
        cur, total = level_progress(xp)
        bar = render_bar(cur, total)

        from database import get_selected_badge
        badge = get_selected_badge(ctx.guild.id, member.id)
        title = f"{member.display_name} — RPG Stats"
        if badge:
            title = f"{member.display_name} — {badge}"
        embed = discord.Embed(title=title, color=0x9B59B6)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name='Level', value=str(level), inline=True)
        embed.add_field(name='XP', value=f"{xp} XP", inline=True)
        embed.add_field(name='Progress', value=bar, inline=False)
        embed.add_field(name='HP', value=f"{profile['hp']} / {profile['max_hp']}", inline=True)
        embed.add_field(name='ATK', value=str(profile['atk']), inline=True)
        embed.add_field(name='DEF', value=str(profile['def']), inline=True)
        embed.add_field(name='Gold', value=str(profile['gold']), inline=True)
        inv = get_inventory(ctx.guild.id, member.id)
        if inv:
            embed.add_field(name='Inventory', value='\n'.join([f"{n} x{q}" for n, q, *rest in inv]), inline=False)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name='heal', with_app_command=True)
    async def heal(self, ctx: commands.Context):
        """Heal yourself for a gold cost (owner can heal others with setxp)"""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        profile = get_profile(ctx.guild.id, ctx.author.id)
        cost = 10
        if profile['gold'] < cost:
            await ctx.reply(f'Gold tidak cukup untuk heal (butuh {cost})')
            return
        # heal to full
        update_profile(ctx.guild.id, ctx.author.id, hp=profile['max_hp'])
        add_gold(ctx.guild.id, ctx.author.id, -cost)
        await ctx.reply(f'✅ Kamu disembuhkan ke penuh (biaya {cost} gold)')


async def setup(bot: commands.Bot):
    await bot.add_cog(RPG(bot))
