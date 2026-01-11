import random
import time
import discord
from discord.ext import commands
from database import (
    get_daily_quest,
    create_daily_quest,
    increment_daily_progress,
)
import os
import io
from PIL import Image, ImageDraw, ImageFont
from utils.fonts import load_font

# Simple pool of daily quests
DAILY_POOL = [
    # key, description template, target, reward_gold, reward_xp, reward_item
    ("adventures", "Lakukan {target}x `adventure` hari ini", 3, 50, 20, None),
    ("claims", "Klaim potion sebanyak {target}x", 2, 20, 10, None),
    ("win_battles", "Menang melawan monster {target}x", 1, 100, 50, 'Minor Potion'),
    ("collect_items", "Kumpulkan {target} item apapun", 5, 30, 15, None),
]


class Daily(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="quest", with_app_command=True)
    async def quest(self, ctx: commands.Context):
        """Tampilkan quest harian saat ini (atau buat baru jika belum ada)"""
        if not ctx.guild:
            await ctx.reply("Perintah hanya bisa dipakai di server")
            return
        guild_id = ctx.guild.id
        user_id = ctx.author.id

        q = get_daily_quest(guild_id, user_id)
        if not q:
            # create random quest
            template = random.choice(DAILY_POOL)
            quest_key, desc_template, target, reward_gold, reward_xp, reward_item = template
            # allow some randomness in target if desired
            if isinstance(target, (list, tuple)):
                t = random.randint(target[0], target[1])
            else:
                t = target
            create_daily_quest(guild_id, user_id, quest_key, target=t, reward_gold=reward_gold, reward_xp=reward_xp, reward_item=reward_item)
            q = get_daily_quest(guild_id, user_id)
            desc = desc_template.format(target=t)
        else:
            # find description from pool
            desc = None
            for tpl in DAILY_POOL:
                if tpl[0] == q['quest_key']:
                    desc = tpl[1].format(target=q['target'])
                    break
            if not desc:
                desc = f"{q['quest_key']} ({q['progress']}/{q['target']})"

        embed = discord.Embed(title="🎯 Quest Harian", color=0xF1C40F)
        embed.add_field(name="Quest", value=desc, inline=False)
        embed.add_field(name="Progress", value=f"{q['progress']}/{q['target']}", inline=True)
        rewards = []
        if q['reward_gold']:
            rewards.append(f"{q['reward_gold']} gold")
        if q['reward_xp']:
            rewards.append(f"{q['reward_xp']} XP")
        if q['reward_item']:
            rewards.append(q['reward_item'])
        embed.add_field(name="Reward", value=", ".join(rewards) if rewards else "(none)", inline=True)
        embed.set_footer(text="Quest akan direset 24 jam sejak dibuat")
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="progress", with_app_command=True)
    async def progress(self, ctx: commands.Context, amount: int = 1):
        """Laporkan progress quest (biasanya dipanggil otomatis oleh cog lain)."""
        if not ctx.guild:
            await ctx.reply("Perintah hanya bisa dipakai di server")
            return
        guild_id = ctx.guild.id
        user_id = ctx.author.id
        res = increment_daily_progress(guild_id, user_id, amount=amount)
        if res.get('error') == 'no_quest':
            await ctx.reply('Belum ada quest hari ini. Jalankan `!quest` untuk membuat quest.')
            return
        if res.get('claimed'):
            rewards = res.get('rewards', {})
            parts = []
            if 'gold' in rewards:
                parts.append(f"{rewards['gold']} gold")
            if 'xp' in rewards:
                parts.append(f"{rewards['xp']} XP")
            if 'item' in rewards:
                parts.append(f"{rewards['item']}")
            await ctx.reply(f"✅ Quest selesai dan auto-claimed! Kamu mendapat: {', '.join(parts)}")
            # generate an Undertale-style congratulations image and send
            try:
                # small 800x200 banner
                W, H = 800, 200
                img = Image.new('RGBA', (W, H), (30, 30, 30, 255))
                draw = ImageDraw.Draw(img)
                # load undertale-first fonts using helper
                try:
                    font = load_font(48)
                    subfont = load_font(24)
                except Exception:
                    font = ImageFont.load_default()
                    subfont = ImageFont.load_default()
                title = "SELAMAT!"
                subtitle = "Quest hari ini telah selesai"
                # white title
                tw, th = draw.textsize(title, font=font)
                draw.text(((W-tw)/2, 30), title, font=font, fill=(255,255,255,255))
                sw, sh = draw.textsize(subtitle, font=subfont)
                draw.text(((W-sw)/2, 30+th+10), subtitle, font=subfont, fill=(200,200,200,255))
                # save to bytes
                bio = io.BytesIO()
                bio.name = 'congrats.png'
                img.save(bio, 'PNG')
                bio.seek(0)
                f = discord.File(fp=bio, filename='congrats.png')
                embed = discord.Embed(title='🎉 Quest Selesai', description='Selamat! Kamu menyelesaikan quest hari ini.', color=0xFFFFFF)
                embed.set_image(url='attachment://congrats.png')
                await ctx.reply(embed=embed, file=f)
            except Exception:
                pass
        else:
            await ctx.reply(f"Progress tercatat: {res.get('progress')}/{res.get('target')}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Daily(bot))
