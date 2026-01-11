import discord
from discord.ext import commands
from discord import app_commands
from database import get_prefix_db
import os
import inspect


class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot, pages: list[discord.Embed], categories: dict, dashboard_url: str | None, invite_url: str | None):
        super().__init__(timeout=120)
        self.bot = bot
        self.pages = pages
        self.index = 0
        self.categories = categories
        self.current_category = 'All'

        # Link buttons
        if dashboard_url:
            self.add_item(discord.ui.Button(label="Dashboard", url=dashboard_url, style=discord.ButtonStyle.link))
        if invite_url:
            self.add_item(discord.ui.Button(label="Invite Bot", url=invite_url, style=discord.ButtonStyle.link))

        # navigation buttons are defined by decorator callbacks below
        # Build category select dynamically (always include 'All')
        options = [discord.SelectOption(label='All', value='All')]
        for k in sorted(self.categories.keys()):
            options.append(discord.SelectOption(label=k, value=k))

        sel = discord.ui.Select(placeholder='Pilih kategori', options=options)

        async def sel_callback(interaction: discord.Interaction):
            value = sel.values[0] if sel.values else 'All'
            self.current_category = value
            lines = []
            if value == 'All':
                for k, v in self.categories.items():
                    lines.extend([f"**{k}**\n{line}" for line in v])
            else:
                lines = self.categories.get(value, [])

            self.pages = build_pages_from_lines(lines)
            self.index = 0
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)

        sel.callback = sel_callback
        self.add_item(sel)

    async def update_message(self, interaction: discord.Interaction):
        embed = self.pages[self.index]
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='◀ Prev', style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label='Next ▶', style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label='Close', style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()

    # select callback is attached dynamically in __init__


def build_pages_from_lines(lines: list[str], per_page: int = 6) -> list:
    pages: list[discord.Embed] = []
    if not lines:
        embed = discord.Embed(title='📜 Daftar Command', description='Tidak ada command', color=0x95A5A6)
        return [embed]

    for i in range(0, len(lines), per_page):
        chunk = lines[i:i+per_page]
        embed = discord.Embed(title='📜 Daftar Command', description='List command', color=0x2ECC71)
        embed.add_field(name='Commands', value='\n\n'.join(chunk), inline=False)
        embed.set_footer(text=f'Page {i//per_page + 1} / {(len(lines)-1)//per_page + 1}')
        pages.append(embed)
    return pages


class Public(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Reply with an attractive about embed when the bot is mentioned in a guild
        if message.author.bot:
            return
        if not message.guild:
            return
        # check direct mention like @Bot or <@!id>
        if self.bot.user in message.mentions:
            try:
                embed = discord.Embed(title=f"Hai, aku {self.bot.user.name}!", color=0x1ABC9C)
                embed.description = (
                    "Aku adalah bot serbaguna untuk server kamu — leveling, shop, RPG, quests, dan banyak lagi.\n"
                    "Ketik `!list` untuk melihat semua perintah, atau tag lagi untuk info singkat."
                )
                embed.add_field(name='Fitur Singkat', value='• Profile & XP\n• Shop & Inventory\n• Adventure (RPG)\n• Daily Quests\n• Badges & Achievements', inline=False)
                embed.add_field(name='Dokumentasi', value='Lihat docs/FEATURES.md atau README untuk detail lebih lengkap.', inline=False)
                embed.set_footer(text='Pesan ini bisa kamu edit sesuai gaya server — saya ringkas saja 😄')
                await message.channel.send(embed=embed)
            except Exception:
                try:
                    await message.channel.send('Hai! Saya bot ini — gunakan `!list` untuk melihat perintah dan fitur.')
                except Exception:
                    pass

    @commands.hybrid_command(name="ping", with_app_command=True)
    async def ping(self, ctx: commands.Context):
        """Cek latency bot (hybrid: /ping dan !ping)"""
        await ctx.reply(f"🏓 Pong! `{round(self.bot.latency * 1000)}ms`")

    @commands.hybrid_command(name="list", with_app_command=True)
    async def list(self, ctx: commands.Context):
        """Tampilkan daftar command (embed)"""
        prefix = '!'
        if ctx.guild:
            prefix = get_prefix_db(ctx.guild.id)

        embed = discord.Embed(
            title="📜 Daftar Command",
            description="Gunakan prefix atau slash command — klik tombol untuk dashboard / invite",
            color=0x2ECC71,
        )

        # Public commands from this cog
        public_cog = self.bot.get_cog('Public')
        public_lines = []
        if public_cog:
            for cmd in public_cog.get_commands():
                has_slash = getattr(cmd, 'app_command', None) is not None
                # build usage from parameters
                params = []
                for pname, p in cmd.clean_params.items():
                    # skip context/interaction params from method signatures
                    if pname in ('ctx', 'interaction'):
                        continue
                    # display python-safe param names nicely (e.g. def_ -> def)
                    display_name = pname[:-1] if pname.endswith('_') else pname
                    if p.default is p.empty:
                        params.append(f"<{display_name}>")
                    else:
                        params.append(f"[{display_name}]")
                params_str = ' '.join(params)
                usage = f"{prefix}{cmd.name}" + (f" {params_str}" if params_str else '')
                names = f"`{usage}`"
                if has_slash:
                    slash_usage = f"/{cmd.name}" + (f" {params_str}" if params_str else '')
                    names += f" / `{slash_usage}`"
                desc = cmd.short_doc or cmd.help or ''
                public_lines.append(f"**{names}** — {desc}")

        owner_cog = self.bot.get_cog('Owner')
        owner_lines = []
        if owner_cog:
            for cmd in owner_cog.get_commands():
                has_slash = getattr(cmd, 'app_command', None) is not None
                params = []
                for pname, p in cmd.clean_params.items():
                    if pname in ('ctx', 'interaction'):
                        continue
                    display_name = pname[:-1] if pname.endswith('_') else pname
                    if p.default is p.empty:
                        params.append(f"<{display_name}>")
                    else:
                        params.append(f"[{display_name}]")
                params_str = ' '.join(params)
                usage = f"{prefix}{cmd.name}" + (f" {params_str}" if params_str else '')
                names = f"`{usage}`"
                if has_slash:
                    slash_usage = f"/{cmd.name}" + (f" {params_str}" if params_str else '')
                    names += f" / `{slash_usage}`"
                desc = cmd.short_doc or cmd.help or ''
                owner_lines.append(f"**{names}** — {desc}")

        if public_lines:
            pass

        # Build categories mapping: cog_name -> lines
        categories = {}
        if public_lines:
            categories['Public'] = public_lines
        if owner_lines:
            categories['Owner'] = owner_lines

        # include any other cogs dynamically
        for cog_name, cog in self.bot.cogs.items():
            if cog_name in ('Public', 'Owner'):
                continue
            lines = []
            for cmd in cog.get_commands():
                has_slash = getattr(cmd, 'app_command', None) is not None
                params = []
                for pname, p in cmd.clean_params.items():
                    if pname in ('ctx', 'interaction'):
                        continue
                    display_name = pname[:-1] if pname.endswith('_') else pname
                    if p.default is p.empty:
                        params.append(f"<{display_name}>")
                    else:
                        params.append(f"[{display_name}]")
                params_str = ' '.join(params)
                usage = f"{prefix}{cmd.name}" + (f" {params_str}" if params_str else '')
                names = f"`{usage}`"
                if has_slash:
                    slash_usage = f"/{cmd.name}" + (f" {params_str}" if params_str else '')
                    names += f" / `{slash_usage}`"
                desc = cmd.short_doc or cmd.help or ''
                lines.append(f"**{names}** — {desc}")
            if lines:
                categories[cog_name] = lines

        # Build 'All' combined lines with emoji for known categories
        cat_emojis = {
            'Public': '🌍',
            'Owner': '👑',
            'Profile': '🎖️',
            'Economy': '🛒',
            'RPG': '⚔️',
            'Potions': '🧪',
            'Daily': '🎯',
            'Crafting': '🛠️',
            'Buffs': '✨',
            'Achievements': '🏅',
            'Admin': '🛡️',
        }

        all_lines = []
        for k, v in categories.items():
            emoji = cat_emojis.get(k, '🧩')
            header = f"__**{emoji} {k}**__"
            all_lines.append(header)
            all_lines.extend(v)

        pages = build_pages_from_lines(all_lines)

        # Buttons: use env vars if provided
        dash = os.getenv('DASHBOARD_URL')
        client_id = os.getenv('CLIENT_ID')
        invite = None
        if client_id:
            invite = f"https://discord.com/oauth2/authorize?client_id={client_id}&scope=bot%20applications.commands&permissions=8"

        view = HelpView(self.bot, pages, categories, dash, invite)
        await ctx.reply(embed=pages[0], view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Public(bot))
