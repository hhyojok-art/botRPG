import os
import discord
import logging
from discord.ext import commands
from redis_client import set_bot_enabled
from database import set_prefix_db
from database import set_user_xp
from database import add_shop_item, update_profile
from cogs.rpg import load_monsters, save_monsters


class Owner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.is_owner()
    @commands.hybrid_command(name="maintenance", with_app_command=True)
    async def maintenance(self, ctx: commands.Context, mode: str):
        """Owner command: maintenance on/off"""
        mode = mode.lower()
        if mode not in ("on", "off"):
            await ctx.reply("Gunakan: maintenance on | maintenance off")
            return

        enabled = True if mode == "off" else False
        await set_bot_enabled(enabled)
        await ctx.reply(f"✅ Maintenance set to `{mode}`")
        # If maintenance turned ON (enabled == False), try to generate maintenance image in background
        if not enabled:
            # Only auto-generate if MAINT_AUTO_GENERATE is enabled
            try:
                auto = os.getenv('MAINT_AUTO_GENERATE', '0').lower() in ('1', 'true', 'yes')
            except Exception:
                auto = False
            if auto:
                try:
                    import scripts.update_maintenance_image as umi
                    logger = logging.getLogger('bot')

                    def _run_generator():
                        try:
                            umi.main()
                        except Exception as e:
                            logger.exception("[owner] maintenance generator error")

                    import asyncio
                    asyncio.create_task(asyncio.to_thread(_run_generator))
                except Exception:
                    logger = logging.getLogger('bot')
                    logger.exception("[owner] failed to import maintenance generator")

    @commands.has_permissions(manage_guild=True)
    @commands.hybrid_command(name='autobalance', with_app_command=True)
    async def autobalance(self, ctx: commands.Context):
        """Auto-balance monsters' HP/ATK/DEF based on server average player level (owner/mod)."""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        try:
            monsters = load_monsters()
            if not monsters:
                await ctx.reply('Belum ada monster untuk di-balance')
                return
            # compute average player level from xp
            from database import get_all_user_xp
            xps = get_all_user_xp(ctx.guild.id)
            if not xps:
                await ctx.reply('Tidak ada data pemain untuk menghitung rata-rata level')
                return
            avg_xp = sum(xps) / len(xps)
            avg_level = max(1, int(avg_xp // 100))
            # target average monster HP
            target_avg_hp = 100 * avg_level
            cur_avg_hp = sum([m.get('hp', 1) for m in monsters]) / len(monsters)
            if cur_avg_hp <= 0:
                cur_avg_hp = 1
            factor = target_avg_hp / cur_avg_hp
            # apply scaling
            new_list = []
            for m in monsters:
                nm = m.copy()
                old_hp = max(1, int(m.get('hp', 10)))
                nm['hp'] = max(1, int(old_hp * factor))
                # scale atk/def a bit
                old_atk = max(0, int(m.get('atk', 0)))
                old_def = max(0, int(m.get('def', 0)))
                nm['atk'] = max(0, int(old_atk * factor**0.5))
                nm['def'] = max(0, int(old_def * factor**0.5))
                new_list.append(nm)
            # backup and save
            import time, json, shutil
            DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
            MONSTER_FILE = DATA_DIR / 'monsters.json'
            if MONSTER_FILE.exists():
                bak = DATA_DIR / f'monsters.bak.{int(time.time())}.json'
                shutil.copy2(MONSTER_FILE, bak)
            save_monsters(new_list)
            await ctx.reply(f'✅ Monsters balanced to avg level {avg_level}. Previous avg HP {int(cur_avg_hp)} -> target {int(target_avg_hp)}')
        except Exception as e:
            import logging, traceback
            logging.getLogger('bot').exception('autobalance failed')
            await ctx.reply(f'Autobalance gagal: {e}')

    @commands.is_owner()
    @commands.hybrid_command(name="setprefix", with_app_command=True)
    async def setprefix(self, ctx: commands.Context, prefix: str):
        """Atur prefix untuk server ini (owner saja)"""
        if not ctx.guild:
            await ctx.reply("Command ini hanya bisa dipakai di server")
            return
        if len(prefix) > 5:
            await ctx.reply("Prefix terlalu panjang (maks 5 karakter)")
            return
        set_prefix_db(ctx.guild.id, prefix)
        await ctx.reply(f"✅ Prefix server diubah menjadi `{prefix}`")

    @commands.is_owner()
    @commands.hybrid_command(name="stop", with_app_command=True)
    async def stop(self, ctx: commands.Context):
        """Matikan bot (owner only)"""
        await ctx.reply("🔌 Bot dimatikan oleh owner")
        await self.bot.close()

    @commands.is_owner()
    @commands.hybrid_command(name="reload", with_app_command=True)
    async def reload(self, ctx: commands.Context, cog: str = None):
        """Reload cog(s). Usage: `reload` or `reload <cog_name>` (without .py)"""
        # If cog is None -> reload all cogs
        applied = []
        failed = []

        if cog is None or cog.lower() in ("all", "*"):
            for file in os.listdir("cogs"):
                if not file.endswith(".py"):
                    continue
                name = file[:-3]
                ext = f"cogs.{name}"
                try:
                    await self.bot.reload_extension(ext)
                    applied.append(name)
                except Exception as e:
                    failed.append(f"{name}: {e}")
        else:
            # Accept formats: 'public' or 'cogs.public'
            if cog.startswith("cogs."):
                ext = cog
                name = cog.split(".")[-1]
            else:
                name = cog
                ext = f"cogs.{name}"
            try:
                await self.bot.reload_extension(ext)
                applied.append(name)
            except Exception as e:
                failed.append(f"{name}: {e}")

        # Build response
        embed = discord.Embed(title="Reload Cogs", color=0x3498DB)
        if applied:
            embed.add_field(name="✅ Reloaded", value="\n".join(applied), inline=False)
        if failed:
            embed.add_field(name="❌ Failed", value="\n".join(failed), inline=False)
        if not applied and not failed:
            embed.description = "No cogs found to reload."

        await ctx.reply(embed=embed)

    @commands.is_owner()
    @commands.hybrid_command(name='setxp', with_app_command=True)
    async def setxp(self, ctx: commands.Context, member: discord.Member, xp: int):
        """Owner: set XP for a user in this server"""
        if not ctx.guild:
            await ctx.reply('Hanya bisa di server')
            return
        set_user_xp(ctx.guild.id, member.id, xp)
        await ctx.reply(f'✅ XP untuk **{member.display_name}** di-set ke {xp} XP')

    @commands.is_owner()
    @commands.hybrid_command(name='setstat', with_app_command=True)
    async def setstat(self, ctx: commands.Context, member: discord.Member, stat: str, value: int):
        """Owner: set player stat (hp, max_hp, atk, def, gold)"""
        if not ctx.guild:
            await ctx.reply('Hanya bisa di server')
            return
        stat = stat.lower()
        allowed = {'hp', 'max_hp', 'atk', 'def', 'gold'}
        if stat not in allowed:
            await ctx.reply(f"Stat tidak valid. Pilih salah satu: {', '.join(sorted(allowed))}")
            return
        update_profile(ctx.guild.id, member.id, **{stat: value})
        await ctx.reply(f'✅ Stat `{stat}` untuk **{member.display_name}** diset ke {value}')

    @commands.is_owner()
    @commands.hybrid_command(name='listmonsters', with_app_command=True)
    async def listmonsters(self, ctx: commands.Context):
        """List configured monsters"""
        monsters = load_monsters()
        if not monsters:
            await ctx.reply('Belum ada monster yang dikonfigurasi')
            return
        lines = [f"**{m['name']}** — HP:{m.get('hp',0)} ATK:{m.get('atk',0)} DEF:{m.get('def',0)} XP:{m.get('xp',0)} GOLD:{m.get('gold',0)}" for m in monsters]
        embed = discord.Embed(title='Monsters', description='Configured monsters', color=0xE67E22)
        embed.add_field(name='List', value='\n'.join(lines), inline=False)
        await ctx.reply(embed=embed)

    @commands.is_owner()
    @commands.hybrid_command(name='addmonster', with_app_command=True)
    async def addmonster(self, ctx: commands.Context, name: str, hp: int, atk: int, def_: int, xp: int, gold: int):
        """Add a monster to monsters.json"""
        monsters = load_monsters()
        monsters.append({'name': name, 'hp': hp, 'atk': atk, 'def': def_, 'xp': xp, 'gold': gold})
        save_monsters(monsters)
        await ctx.reply(f'✅ Monster **{name}** ditambahkan')

    @commands.is_owner()
    @commands.hybrid_command(name='setmonster', with_app_command=True)
    async def setmonster(self, ctx: commands.Context, name: str, stat: str, value: int):
        """Set a monster stat by name (hp, atk, def, xp, gold)"""
        monsters = load_monsters()
        found = False
        stat = stat.lower()
        for m in monsters:
            if m['name'].lower() == name.lower():
                if stat not in ('hp','atk','def','xp','gold'):
                    await ctx.reply('Stat monster invalid (hp, atk, def, xp, gold)')
                    return
                # def is reserved name in python, but our json key is 'def'
                m[stat] = value
                found = True
                break
        if not found:
            await ctx.reply('Monster tidak ditemukan')
            return
        save_monsters(monsters)
        await ctx.reply(f'✅ Monster **{name}** stat `{stat}` diubah menjadi {value}')

    @commands.is_owner()
    @commands.hybrid_command(name='removemonster', with_app_command=True)
    async def removemonster(self, ctx: commands.Context, name: str):
        """Remove a monster by name"""
        monsters = load_monsters()
        new = [m for m in monsters if m['name'].lower() != name.lower()]
        save_monsters(new)
        await ctx.reply(f'✅ Monster **{name}** dihapus (jika ada)')

    @commands.is_owner()
    @commands.hybrid_command(name='shopseed', with_app_command=True)
    async def shopseed(self, ctx: commands.Context):
        """Seed server shop with powerful attack/defense items"""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        items = [
            ('Sword of Might', 500, 'Large ATK +25', 25, 0, 'weapon'),
            ('Greatsword', 750, 'Huge ATK +40', 40, 0, 'weapon'),
            ('Shield of Fortitude', 400, 'Large DEF +20', 0, 20, 'offhand'),
            ('Tower Shield', 700, 'Huge DEF +35', 0, 35, 'offhand'),
            ('Amulet of Power', 600, 'ATK +20, DEF +10', 20, 10, 'accessory'),
            ('Battle Tonic', 200, 'Buff ATK +10 for 1 hour', 10, 3600, 'buff'),
        ]
        for item in items:
            # support tuples with either (name,price,desc) or (name,price,desc,atk,def,slot)
            if len(item) >= 6:
                name, price, desc, atk, defn, slot = item
                add_shop_item(ctx.guild.id, name, price, desc, atk, defn, slot)
            else:
                name, price, desc = item
                add_shop_item(ctx.guild.id, name, price, desc)
        await ctx.reply(f'✅ Shop seeded with {len(items)} powerful items')


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
