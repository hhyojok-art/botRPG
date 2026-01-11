import discord
from discord.ext import commands
from database import get_active_buffs, delete_buff


class Buffs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='buffs', with_app_command=True)
    async def buffs(self, ctx: commands.Context, member: discord.Member = None):
        """List active temporary buffs for a user (default: yourself)"""
        if member is None:
            member = ctx.author
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        rows = get_active_buffs(ctx.guild.id, member.id)
        if not rows:
            await ctx.reply('Tidak ada buff aktif')
            return
        lines = []
        for buff_key, stat, amount, expires in rows:
            lines.append(f"**{buff_key}** — {stat.upper()} +{amount} (expires {expires})")
        await ctx.reply(embed=discord.Embed(title=f"Buffs — {member.display_name}", description='\n'.join(lines), color=0x1ABC9C))

    @commands.has_permissions(manage_guild=True)
    @commands.hybrid_command(name='removebuff', with_app_command=True)
    async def removebuff(self, ctx: commands.Context, member: discord.Member, buff_key: str):
        """Admin: remove a buff from a user"""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        delete_buff(ctx.guild.id, member.id, buff_key)
        await ctx.reply(f'✅ Buff `{buff_key}` dihapus dari **{member.display_name}**')


async def setup(bot: commands.Bot):
    await bot.add_cog(Buffs(bot))
