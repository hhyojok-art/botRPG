import random
import time
from discord.ext import commands
import discord
from database import (
    get_cooldown,
    set_cooldown,
    add_item,
    get_inventory,
    get_profile,
    update_profile,
    remove_item,
)

POTIONS = [
    # name, description, effect dict, weight
    ("Minor Potion", "Restores 20 HP", {"hp": 20}, 30),
    ("Red Potion", "Restores 40 HP", {"hp": 40}, 20),
    ("Greater Potion", "Restores 80 HP", {"hp": 80}, 8),
    ("Defense Elixir", "Increase DEF by 5 (temporary) — permanent for simplicity", {"def": 5}, 10),
    ("Blue Tonic", "Increase DEF by 10", {"def": 10}, 4),
    ("Poison Vial", "Deals 30 HP damage to user", {"hp": -30}, 6),
    ("Bitter Tonic", "Reduces DEF by 5", {"def": -5}, 5),
]

COOLDOWN_SECONDS = 3600  # 1 hour


class Potions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="claim", with_app_command=True)
    async def claim(self, ctx: commands.Context):
        """Claim a random potion (1 hour cooldown)."""
        if not ctx.guild:
            await ctx.reply("Command hanya bisa dipakai di server")
            return
        guild_id = ctx.guild.id
        user_id = ctx.author.id

        last = get_cooldown(guild_id, user_id, 'claim')
        now = int(time.time())
        # allow bot owner to bypass cooldown
        try:
            is_owner = await self.bot.is_owner(ctx.author)
        except Exception:
            is_owner = False

        if last and now - last < COOLDOWN_SECONDS and not is_owner:
            remaining = COOLDOWN_SECONDS - (now - last)
            m, s = divmod(remaining, 60)
            await ctx.reply(f"⌛ Kamu harus menunggu {m} menit {s} detik sebelum klaim lagi.")
            return

        # choose random potion by weight
        names = [p[0] for p in POTIONS]
        weights = [p[3] for p in POTIONS]
        choice = random.choices(POTIONS, weights=weights, k=1)[0]
        name, desc, effect, weight = choice

        add_item(guild_id, user_id, name, qty=1)
        # only set cooldown for non-owners
        if not is_owner:
            set_cooldown(guild_id, user_id, 'claim')

        embed = discord.Embed(title="🎁 Klaim Potion", description=f"Kamu mendapat **{name}** — {desc}", color=0xE74C3C)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="use", with_app_command=True)
    async def use(self, ctx: commands.Context, *, potion_name: str):
        """Use a potion from your inventory: !use <potion_name>"""
        if not ctx.guild:
            await ctx.reply("Command hanya bisa dipakai di server")
            return
        guild_id = ctx.guild.id
        user_id = ctx.author.id

        # find potion in POTIONS list by case-insensitive or slug
        pname = potion_name.strip()
        found = None
        for p in POTIONS:
            if p[0].lower() == pname.lower():
                found = p
                break
        if not found:
            # allow partial match
            for p in POTIONS:
                if pname.lower() in p[0].lower():
                    found = p
                    break
        if not found:
            await ctx.reply("Potion tidak ditemukan atau tidak valid.")
            return
        name, desc, effect, weight = found

        # check inventory
        inv = get_inventory(guild_id, user_id)
        inv_map = {row[0]: row[1] for row in inv}
        if name not in inv_map or inv_map[name] <= 0:
            await ctx.reply("Kamu tidak punya potion ini di inventory.")
            return

        # apply effect
        profile = get_profile(guild_id, user_id)
        hp = profile['hp']
        max_hp = profile['max_hp']
        deff = profile['def']

        changed = []
        if 'hp' in effect:
            delta = effect['hp']
            new_hp = hp + delta
            # cap at max_hp
            if new_hp > max_hp:
                new_hp = max_hp
            # don't allow <=0 — set to 1
            if new_hp <= 0:
                new_hp = 1
            update_profile(guild_id, user_id, hp=new_hp)
            if delta >= 0:
                changed.append(f"HP +{delta} (sekarang {new_hp}/{max_hp})")
            else:
                changed.append(f"HP {delta} (sekarang {new_hp}/{max_hp})")

        if 'def' in effect:
            delta = effect['def']
            new_def = deff + delta
            if new_def < 0:
                new_def = 0
            update_profile(guild_id, user_id, **{'def': new_def})
            if delta >= 0:
                changed.append(f"DEF +{delta} (sekarang {new_def})")
            else:
                changed.append(f"DEF {delta} (sekarang {new_def})")

        # remove one potion
        remove_item(guild_id, user_id, name, qty=1)

        embed = discord.Embed(title=f"🧪 Menggunakan {name}", description="\n".join(changed) if changed else "Effect applied.", color=0x9B59B6)
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Potions(bot))
