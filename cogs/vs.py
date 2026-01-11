from discord.ext import commands
from discord import app_commands
import discord
import random
from database import (
    get_profile,
    update_profile,
    get_inventory,
    set_equipped,
    add_user_xp,
    add_gold,
    get_cooldown,
    set_cooldown,
    get_shop_item_with_stats,
)

COOLDOWN_SECONDS = 60 * 5


class ConfirmView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.challenger = challenger
        self.opponent = opponent
        self.accepted = None

    @discord.ui.button(label="Terima", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Hanya yang ditantang yang bisa menerima.", ephemeral=True)
            return
        self.accepted = True
        await interaction.response.edit_message(content=f"{interaction.user.mention} menerima tantangan!", view=None)
        self.stop()

    @discord.ui.button(label="Tolak", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Hanya yang ditantang yang bisa menolak.", ephemeral=True)
            return
        self.accepted = False
        await interaction.response.edit_message(content=f"{interaction.user.mention} menolak tantangan.", view=None)
        self.stop()


class VsCog(commands.Cog):
    """Player vs Player duel commands with confirmation."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _calc_power(self, guild_id: int, user_id: int):
        profile = get_profile(guild_id, user_id)
        lvl = profile.get('level', 1) if profile else 1
        base_atk = profile.get('atk', 0) if profile else 0
        base_def = profile.get('def', 0) if profile else 0

        inv = get_inventory(guild_id, user_id)
        atk = 0
        df = 0
        for item in inv:
            try:
                item_name = item[0]
                equipped = item[2]
            except Exception:
                continue
            if equipped:
                stats = get_shop_item_with_stats(guild_id, item_name)
                if stats:
                    try:
                        atk += int(stats[3] or 0)
                        df += int(stats[4] or 0)
                    except Exception:
                        pass

        power = (lvl * 2) + base_atk + atk + random.randint(0, 5)
        defense = (lvl * 2) + base_def + df + random.randint(0, 5)
        return power, defense

    async def _resolve_duel(self, ctx: commands.Context, opponent: discord.Member):
        p_power, p_def = await self._calc_power(ctx.guild.id, ctx.author.id)
        o_power, o_def = await self._calc_power(ctx.guild.id, opponent.id)

        p_score = p_power - o_def + random.randint(-3, 3)
        o_score = o_power - p_def + random.randint(-3, 3)

        if p_score == o_score:
            result = "draw"
        elif p_score > o_score:
            result = "author"
        else:
            result = "opponent"

        if result == 'draw':
            text = f"Duel antara {ctx.author.mention} dan {opponent.mention} berakhir seri!"
            add_user_xp(ctx.guild.id, ctx.author.id, 5)
            add_user_xp(ctx.guild.id, opponent.id, 5)
        elif result == 'author':
            text = f"{ctx.author.mention} menang melawan {opponent.mention}!"
            add_user_xp(ctx.guild.id, ctx.author.id, 20)
            add_gold(ctx.guild.id, ctx.author.id, 10)
            add_user_xp(ctx.guild.id, opponent.id, 5)
        else:
            text = f"{opponent.mention} menang melawan {ctx.author.mention}!"
            add_user_xp(ctx.guild.id, opponent.id, 20)
            add_gold(ctx.guild.id, opponent.id, 10)
            add_user_xp(ctx.guild.id, ctx.author.id, 5)

        # set cooldowns for both participants
        now = int(__import__('time').time())
        set_cooldown(ctx.guild.id, ctx.author.id, 'vs', now)
        set_cooldown(ctx.guild.id, opponent.id, 'vs', now)

        embed = discord.Embed(title="Duel PvP", description=text)
        embed.add_field(name=str(ctx.author), value=f"Score: {p_score}", inline=True)
        embed.add_field(name=str(opponent), value=f"Score: {o_score}", inline=True)
        return embed

    @commands.hybrid_command(name="vs", with_app_command=True, description="Duel user lain (PvP)")
    @app_commands.describe(opponent="User to duel")
    async def vs(self, ctx: commands.Context, opponent: discord.Member):
        """Challenge another member to a duel with confirmation."""
        # cooldown check with owner bypass
        last = get_cooldown(ctx.guild.id, ctx.author.id, 'vs')
        now = int(__import__('time').time())
        try:
            is_owner = await self.bot.is_owner(ctx.author)
        except Exception:
            is_owner = False
        if not is_owner:
            if last and now - last < COOLDOWN_SECONDS:
                remaining = COOLDOWN_SECONDS - (now - last)
                m, s = divmod(remaining, 60)
                await ctx.reply(f'Kamu harus menunggu {m} menit {s} detik sebelum duel lagi.')
                return
        if opponent.bot:
            await ctx.reply("Kamu tidak bisa menantang bot.")
            return
        if opponent.id == ctx.author.id:
            await ctx.reply("Tidak bisa duel dengan diri sendiri.")
            return

        view = ConfirmView(ctx.author, opponent, timeout=30)
        prompt = await ctx.reply(f"{opponent.mention}, {ctx.author.display_name} menantangmu ke duel! Terima?", view=view)

        # wait until the view completes or times out
        await view.wait()

        if view.accepted:
            embed = await self._resolve_duel(ctx, opponent)
            await ctx.followup.send(embed=embed) if hasattr(ctx, 'followup') else await ctx.reply(embed=embed)
        else:
            # accepted == False or None (declined or timed out)
            if view.accepted is False:
                await ctx.reply(f"{opponent.mention} menolak tantangan.")
            else:
                await ctx.reply(f"Tantangan kedaluwarsa — {opponent.mention} tidak merespon.")


async def setup(bot: commands.Bot):
    await bot.add_cog(VsCog(bot))
