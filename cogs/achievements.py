import discord
from discord.ext import commands
from database import award_achievement, list_user_achievements, set_selected_badge, get_selected_badge

BADGES = {
    'starter': ('Pemula', 'Badge untuk pemain baru'),
    'slayer': ('Monster Slayer', 'Menang 10 kali melawan monster'),
    'collector': ('Collector', 'Kumpulkan 50 item'),
}

# Load AI-generated badges from data/badges.json if present
try:
    import json
    from pathlib import Path
    _badges_file = Path(__file__).resolve().parents[1] / 'data' / 'badges.json'
    if _badges_file.exists():
        with _badges_file.open('r', encoding='utf-8') as _f:
            _d = json.load(_f)
        for k, v in _d.items():
            # v expected [name, desc]
            if k not in BADGES:
                BADGES[k] = (v[0], v[1])
except Exception:
    pass


class Achievements(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name='badges', with_app_command=True, invoke_without_command=True)
    async def badges(self, ctx: commands.Context, member: discord.Member = None):
        """List badges earned by a user
        Usage: `!badges [member]` or `!badges list [member]`
        """
        # behave like previous list when invoked without subcommand
        if member is None:
            member = ctx.author
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        rows = list_user_achievements(ctx.guild.id, member.id)
        if not rows:
            await ctx.reply('Belum ada badge')
            return
        lines = []
        for key, ts in rows:
            name, desc = BADGES.get(key, (key, ''))
            lines.append(f"**{name}** (`{key}`) — {desc}")
        sel = get_selected_badge(ctx.guild.id, member.id)
        footer = f"Selected: {sel}" if sel else "No badge selected"
        await ctx.reply(embed=discord.Embed(title=f"Badges — {member.display_name}", description='\n'.join(lines), color=0xF39C12).set_footer(text=footer))

    @badges.command(name='show')
    async def badges_show(self, ctx: commands.Context, what: str = None, badge_key: str = None):
        """Show badge assets. Usage: `!badges show icon <badge_key>`"""
        if not what or what.lower() != 'icon' or not badge_key:
            await ctx.reply('Gunakan: `!badges show icon <badge_key>`')
            return
        # try to find image in Assets/badges/<badge_key>.png
        import os
        path = os.path.join('Assets', 'badges', f"{badge_key}.png")
        if not os.path.exists(path):
            await ctx.reply('Icon badge tidak ditemukan')
            return
        try:
            file = discord.File(path, filename='badge.png')
            embed = discord.Embed(title=f"Badge: {BADGES.get(badge_key,(badge_key,''))[0]}", color=0xF39C12)
            embed.set_image(url='attachment://badge.png')
            await ctx.reply(embed=embed, file=file)
        except Exception:
            await ctx.reply('Gagal menampilkan icon')

    @badges.command(name='giftowner')
    async def badges_giftowner(self, ctx: commands.Context, badge_key: str = None):
        """Gift a badge to the server owner. Usage: `!badges giftowner <badge_key>`"""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        if not badge_key:
            await ctx.reply('Gunakan: `!badges giftowner <badge_key>`')
            return
        # only staff or bot owner can gift
        if not ctx.author.guild_permissions.manage_guild and not await self.bot.is_owner(ctx.author):
            await ctx.reply('Hanya staff (Manage Guild) atau owner bot yang dapat memberikan badge ke owner')
            return
        owner_id = ctx.guild.owner_id
        award_achievement(ctx.guild.id, owner_id, badge_key)
        owner_member = ctx.guild.get_member(owner_id)
        name = owner_member.display_name if owner_member else f"Owner ({owner_id})"
        await ctx.reply(f'✅ Badge `{badge_key}` diberikan ke **{name}**')

    @commands.hybrid_command(name='badge', with_app_command=True)
    async def badge(self, ctx: commands.Context, action: str, *, args: str = None):
        """badge select <badge_key>  — pilih badge yang sudah dimiliki
badge set <member> <badge_key> — OWNER only: paksa set selected badge
award <member> <badge_key> — staff: award a badge to a user
"""
        action = action.lower()
        if action == 'select':
            if not args:
                await ctx.reply('Gunakan: badge select <badge_key>')
                return
            key = args.strip()
            # check ownership of badge
            rows = list_user_achievements(ctx.guild.id, ctx.author.id)
            owned = [r[0] for r in rows]
            if key not in owned:
                await ctx.reply('Kamu belum mendapatkan badge ini')
                return
            set_selected_badge(ctx.guild.id, ctx.author.id, key)
            await ctx.reply(f'✅ Badge `{key}` dipilih')
            return

        if action == 'set':
            # owner-only: set selected badge for any member (bypass)
            if not await self.bot.is_owner(ctx.author):
                await ctx.reply('Hanya owner yang bisa memakai perintah ini')
                return
            if not args:
                await ctx.reply('Gunakan: badge set <member> <badge_key>')
                return
            parts = args.split()
            if len(parts) < 2:
                await ctx.reply('Gunakan: badge set <member> <badge_key>')
                return
            member_mention = parts[0]
            badge_key = parts[1]
            member = None
            try:
                member = await commands.MemberConverter().convert(ctx, member_mention)
            except Exception:
                await ctx.reply('Member tidak ditemukan')
                return
            set_selected_badge(ctx.guild.id, member.id, badge_key)
            await ctx.reply(f'✅ Badge `{badge_key}` dipaksa dipilih untuk **{member.display_name}**')
            return

        if action == 'award':
            # staff: award badge to member
            if not ctx.author.guild_permissions.manage_guild and not await self.bot.is_owner(ctx.author):
                await ctx.reply('Hanya staff (Manage Guild) atau owner yang dapat award')
                return
            if not args:
                await ctx.reply('Gunakan: badge award <member> <badge_key>')
                return
            parts = args.split()
            if len(parts) < 2:
                await ctx.reply('Gunakan: badge award <member> <badge_key>')
                return
            member_mention = parts[0]
            badge_key = parts[1]
            try:
                member = await commands.MemberConverter().convert(ctx, member_mention)
            except Exception:
                await ctx.reply('Member tidak ditemukan')
                return
            award_achievement(ctx.guild.id, member.id, badge_key)
            await ctx.reply(f'✅ Badge `{badge_key}` diberikan ke **{member.display_name}**')
            return

        await ctx.reply('Unknown badge action')


async def setup(bot: commands.Bot):
    await bot.add_cog(Achievements(bot))
    # Auto-award all badges to the application owner in every guild
    try:
        info = await bot.application_info()
        owner = info.owner
        for g in bot.guilds:
            for key in BADGES.keys():
                try:
                    award_achievement(g.id, owner.id, key)
                except Exception:
                    continue
    except Exception:
        pass
