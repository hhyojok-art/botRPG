import discord
from discord.ext import commands
import random
import time
import asyncio
from datetime import datetime, timedelta
import re


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")
from database import (
    list_shop_items,
    get_shop_item,
    add_shop_item,
    remove_shop_item,
    get_user_xp,
    set_user_xp,
    get_inventory,
    get_shop_item_with_stats,
    add_item,
    set_equipped,
    get_equipped_items,
    spend_gold,
    get_cooldown,
    set_cooldown,
    add_user_xp,
    add_gold,
    add_buff,
)
# Larger pool of possible shop items used for refresh
SHOP_POOL = [
    ("Sword of Light", 200, "ATK +10", 10, 0, 'weapon'),
    ("Greatsword", 350, "ATK +18", 18, 0, 'weapon'),
    ("Battle Tonic", 200, "Buff ATK +10 for 1 hour", 10, 3600, 'buff'),
    ("Leather Helmet", 100, "DEF +5", 0, 5, 'head'),
    ("Iron Helmet", 180, "DEF +9", 0, 9, 'head'),
    ("Ring of Vitality", 150, "ATK +5, DEF +5", 5, 5, 'accessory'),
    ("Amulet of Strength", 220, "ATK +12", 12, 0, 'accessory'),
    ("Background Orange", 100, "Background (Orange)", 0, 0, 'background'),
    ("Background Blue", 100, "Background (Blue)", 0, 0, 'background'),
    ("Background Green", 100, "Background (Green)", 0, 0, 'background'),
    ("Background Gray", 100, "Background (Gray)", 0, 0, 'background'),
    ("Leather Armor", 200, "DEF +12", 0, 12, 'body'),
    ("Steel Shield", 250, "DEF +15", 0, 15, 'offhand'),
    ("Mysterious Shard", 50, "A curious fragment", 0, 0, 'none'),
]


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._refresh_task = self.bot.loop.create_task(self._daily_shop_refresher())

    @commands.hybrid_command(name='shop', with_app_command=True)
    async def shop(self, ctx: commands.Context):
        """List items in the shop"""
        if not ctx.guild:
            await ctx.reply('Shop hanya tersedia di server')
            return
        items = list_shop_items(ctx.guild.id)
        # If shop is empty, seed some default items so it's not empty
        if not items:
            # choose a few items from pool to seed
            sample = random.sample(SHOP_POOL, min(len(SHOP_POOL), 6))
            for name, price, desc, atk, defn, slot in sample:
                add_shop_item(ctx.guild.id, name, price, desc, atk, defn, slot)
            items = list_shop_items(ctx.guild.id)
        if not items:
            await ctx.reply('Shop kosong di server ini')
            return
        def slugify(name: str) -> str:
            s = name.lower()
            s = re.sub(r"[^a-z0-9]+", "_", s)
            s = s.strip("_")
            return s

        lines = []
        for name, price, desc in items:
            # fetch stats to see if this is a buff
            row = get_shop_item_with_stats(ctx.guild.id, name)
            atk_b = 0
            def_b = 0
            slot = 'none'
            if row:
                _, _, _, atk_b, def_b, slot = row

            slug = slugify(name)
            extra = ''
            if slot == 'buff':
                # atk_b: amount, def_b: duration seconds
                dur = int(def_b or 0)
                amount = int(atk_b or 0)
                hrs = dur // 3600
                mins = (dur % 3600) // 60
                dur_text = (f"{hrs}j" if hrs else "") + (f" {mins}m" if mins else "")
                if not dur_text:
                    dur_text = f"{dur}s"
                extra = f"\n🧪 BUFF: {('ATK+' if amount>0 else 'DEF+')}{amount} for {dur_text}"
            lines.append(f"**{name}** — {price} XP\n{desc}{extra}\n`!buy {slug}`")
        embed = discord.Embed(title='🛒 Server Shop', description='Items available to buy', color=0x9B59B6)
        embed.add_field(name='Items', value='\n\n'.join(lines), inline=False)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name='buy', with_app_command=True)
    async def buy(self, ctx: commands.Context, item_name: str):
        """Buy an item with XP"""
        if not ctx.guild:
            await ctx.reply('Command hanya di server')
            return
        row = get_shop_item_with_stats(ctx.guild.id, item_name)
        # fallback: try case-insensitive exact match if direct lookup fails
        if not row:
            items = list_shop_items(ctx.guild.id)
            found_name = None
            for name, price, desc in items:
                # direct case-insensitive match
                if name.lower() == item_name.lower():
                    found_name = name
                    break
                # slug match (e.g. sword_of_light)
                slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip('_')
                if slug == item_name.lower():
                    found_name = name
                    break
            if found_name:
                row = get_shop_item_with_stats(ctx.guild.id, found_name)
            else:
                await ctx.reply('Item tidak ditemukan')
                return
        name, price, desc, atk_bonus, def_bonus, slot = row
        xp = get_user_xp(ctx.guild.id, ctx.author.id)
        if xp < price:
            await ctx.reply(f'XP kamu kurang: {xp} XP (harga {price} XP)')
            return
        # deduct xp
        set_user_xp(ctx.guild.id, ctx.author.id, xp - price)
        # If item is a temporary buff (slot == 'buff'), interpret atk as amount and def as duration (seconds)
        if slot == 'buff':
            try:
                buff_amount = int(atk_bonus or 0)
                duration = int(def_bonus or 3600)
            except Exception:
                buff_amount = 0
                duration = 3600
            # For simplicity, buff stat chosen by presence: if atk_bonus>0 -> 'atk', else 'def'
            stat = 'atk' if buff_amount > 0 else 'def'
            add_buff(ctx.guild.id, ctx.author.id, name, stat, buff_amount, duration)
            await ctx.reply(f'✅ Kamu membeli **{name}** dan mendapatkan buff {stat}+{buff_amount} selama {duration} detik')
        else:
            add_item(ctx.guild.id, ctx.author.id, name)
            await ctx.reply(f'✅ Kamu membeli **{name}** seharga {price} XP')

    @commands.hybrid_command(name='shoprefresh', with_app_command=True)
    @commands.has_permissions(manage_guild=True)
    async def shoprefresh(self, ctx: commands.Context, count: int = 6):
        """Admin: refresh the server shop with a random selection of items."""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        # clamp count
        count = max(1, min(count, len(SHOP_POOL)))
        # remove existing items
        existing = list_shop_items(ctx.guild.id)
        for name, price, desc in existing:
            remove_shop_item(ctx.guild.id, name)
        # add random selection
        sample = random.sample(SHOP_POOL, count)
        for name, price, desc, atk, defn, slot in sample:
            add_shop_item(ctx.guild.id, name, price, desc, atk, defn, slot)
        await ctx.reply(f'✅ Shop telah diperbarui dengan {count} item.')

    async def _refresh_guild_shop(self, guild_id: int, count: int = 6):
        # remove existing items
        existing = list_shop_items(guild_id)
        for name, price, desc in existing:
            remove_shop_item(guild_id, name)
        # add random selection
        sample = random.sample(SHOP_POOL, min(count, len(SHOP_POOL)))
        for name, price, desc, atk, defn, slot in sample:
            add_shop_item(guild_id, name, price, desc, atk, defn, slot)

    async def _daily_shop_refresher(self):
        """Background task: refresh all guild shops daily at UTC midnight."""
        try:
            while True:
                now = datetime.utcnow()
                # next UTC midnight
                next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                wait_seconds = (next_midnight - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                # refresh for all guilds
                for g in list(self.bot.guilds):
                    try:
                        await self._refresh_guild_shop(g.id, 6)
                    except Exception:
                        continue
        except asyncio.CancelledError:
            return

    def cog_unload(self):
        if self._refresh_task and not self._refresh_task.cancelled():
            self._refresh_task.cancel()

    @commands.hybrid_command(name='daily', with_app_command=True)
    async def daily(self, ctx: commands.Context):
        """Claim daily reward: XP, gold, and small chance to get an item (24h cooldown)"""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        last = get_cooldown(ctx.guild.id, ctx.author.id, 'daily')
        now = int(time.time())
        # owner bypass
        try:
            is_owner = await self.bot.is_owner(ctx.author)
        except Exception:
            is_owner = False
        if not is_owner:
            if last and now - last < 86400:
                remaining = 86400 - (now - last)
                h, rem = divmod(remaining, 3600)
                m, s = divmod(rem, 60)
                await ctx.reply(f'⌛ Kamu sudah klaim daily. Tunggu {h}j {m}m {s}s lagi.')
                return

        xp_gain = random.randint(20, 50)
        gold_gain = random.randint(10, 30)
        add_user_xp(ctx.guild.id, ctx.author.id, xp_gain)
        add_gold(ctx.guild.id, ctx.author.id, gold_gain)

        # small chance to drop an item from shop
        drop_text = ''
        shop_items = list_shop_items(ctx.guild.id)
        if shop_items and random.random() < 0.25:
            # pick an item name from shop list
            choice_name = random.choice(shop_items)[0]
            add_item(ctx.guild.id, ctx.author.id, choice_name)
            drop_text = f"\n🎁 Kamu juga mendapatkan item: **{choice_name}**"

        set_cooldown(ctx.guild.id, ctx.author.id, 'daily', now)
        await ctx.reply(embed=discord.Embed(
            title='📅 Daily Reward',
            description=f'+{xp_gain} XP, +{gold_gain} gold{drop_text}',
            color=0x2ECC71
        ))

    @commands.hybrid_command(name='inventory', with_app_command=True)
    async def inventory(self, ctx: commands.Context):
        """Tampilkan inventory dan item terpasang"""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        inv = get_inventory(ctx.guild.id, ctx.author.id)
        if not inv:
            await ctx.reply('Inventory kosong')
            return
        lines = []
        for name, qty, equipped, slot in inv:
            eq = ' (equipped)' if equipped else ''
            slot_txt = f' [{slot}]' if slot and slot != 'none' else ''
            lines.append(f"**{name}** x{qty}{eq}{slot_txt}")
        await ctx.reply(embed=discord.Embed(title='Inventory', description='\n'.join(lines), color=0x95A5A6))

    @commands.hybrid_command(name='equip', with_app_command=True)
    async def equip(self, ctx: commands.Context, item_name: str):
        """Equip an item from your inventory to apply its stat bonuses"""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        # Check ownership
        inv = get_inventory(ctx.guild.id, ctx.author.id)
        owned = None
        target = item_name.lower()
        for n, qty, equipped, slot in inv:
            if qty <= 0:
                continue
            if n.lower() == target or slugify(n) == target:
                owned = (n, qty, equipped, slot)
                break
        if not owned:
            await ctx.reply('Kamu tidak memiliki item ini')
            return
        name = owned[0]
        # get item stats
        row = get_shop_item_with_stats(ctx.guild.id, name)
        if not row:
            await ctx.reply('Item shop stat tidak ditemukan')
            return
        _, price, desc, atk_bonus, def_bonus, slot = row

        # auto-unequip any item in the same slot
        if slot and slot != 'none':
            equipped_items = get_equipped_items(ctx.guild.id, ctx.author.id)
            for ename, eq_qty, eslot in equipped_items:
                if eslot == slot and ename != name:
                    # remove bonuses of existing equipped same-slot item
                    erow = get_shop_item_with_stats(ctx.guild.id, ename)
                    if erow:
                        _, _, _, eatk, edef, _ = erow
                        from database import get_profile as db_get_profile, update_profile as db_update_profile
                        prof = db_get_profile(ctx.guild.id, ctx.author.id)
                        new_atk = max(0, prof['atk'] - (eatk or 0))
                        new_def = max(0, prof['def'] - (edef or 0))
                        db_update_profile(ctx.guild.id, ctx.author.id, **{'atk': new_atk, 'def': new_def})
                    set_equipped(ctx.guild.id, ctx.author.id, ename, False)

        # apply bonuses for this item
        from database import get_profile as db_get_profile, update_profile as db_update_profile
        prof = db_get_profile(ctx.guild.id, ctx.author.id)
        new_atk = prof['atk'] + (atk_bonus or 0)
        new_def = prof['def'] + (def_bonus or 0)
        db_update_profile(ctx.guild.id, ctx.author.id, **{'atk': new_atk, 'def': new_def})
        set_equipped(ctx.guild.id, ctx.author.id, name, True)
        await ctx.reply(f'✅ **{name}** telah dipasangkan. ATK +{atk_bonus}, DEF +{def_bonus}\nSlot: {slot}')

    @commands.hybrid_command(name='unequip', with_app_command=True)
    async def unequip(self, ctx: commands.Context, item_name: str):
        """Unequip an equipped item and remove its bonuses"""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        inv = get_inventory(ctx.guild.id, ctx.author.id)
        owned = None
        target = item_name.lower()
        for n, qty, equipped, slot in inv:
            if not equipped:
                continue
            if n.lower() == target or slugify(n) == target:
                owned = (n, qty, equipped, slot)
                break
        if not owned:
            await ctx.reply('Item tidak terpasang')
            return
        name = owned[0]
        row = get_shop_item_with_stats(ctx.guild.id, name)
        if not row:
            await ctx.reply('Item shop stat tidak ditemukan')
            return
        _, price, desc, atk_bonus, def_bonus, slot = row
        from database import get_profile as db_get_profile, update_profile as db_update_profile
        prof = db_get_profile(ctx.guild.id, ctx.author.id)
        new_atk = max(0, prof['atk'] - (atk_bonus or 0))
        new_def = max(0, prof['def'] - (def_bonus or 0))
        db_update_profile(ctx.guild.id, ctx.author.id, **{'atk': new_atk, 'def': new_def})
        set_equipped(ctx.guild.id, ctx.author.id, name, False)
        await ctx.reply(f'✅ **{name}** dilepas. ATK -{atk_bonus}, DEF -{def_bonus}')

    @commands.is_owner()
    @commands.hybrid_command(name='shopadd', with_app_command=True)
    async def shopadd(self, ctx: commands.Context, item_name: str, price: int, *, description: str = ''):
        """Owner: add/update shop item"""
        if not ctx.guild:
            await ctx.reply('Hanya untuk server')
            return
        add_shop_item(ctx.guild.id, item_name, price, description)
        await ctx.reply(f'✅ Item **{item_name}** disimpan dengan harga {price} XP')

    @commands.is_owner()
    @commands.hybrid_command(name='shopremove', with_app_command=True)
    async def shopremove(self, ctx: commands.Context, item_name: str):
        """Owner: remove shop item"""
        if not ctx.guild:
            await ctx.reply('Hanya untuk server')
            return
        remove_shop_item(ctx.guild.id, item_name)
        await ctx.reply(f'✅ Item **{item_name}** dihapus')


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
