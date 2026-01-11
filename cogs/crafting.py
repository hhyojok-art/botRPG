import discord
from discord.ext import commands
from database import get_inventory, remove_item, add_item, get_profile, spend_gold

# Simple recipes: name -> {ingredients: {item_name: qty}, result: (item_name, qty), cost_gold}
RECIPES = {
    'iron_ingot': {
        'display': 'Iron Ingot',
        'ingredients': {'Iron Ore': 3},
        'result': ('Iron Ingot', 1),
        'cost_gold': 0,
    },
    'health_potion': {
        'display': 'Health Potion',
        'ingredients': {'Herb': 2, 'Empty Bottle': 1},
        'result': ('Minor Potion', 1),
        'cost_gold': 10,
    },
    'steel_sword': {
        'display': 'Steel Sword',
        'ingredients': {'Iron Ingot': 4, 'Wood': 2},
        'result': ('Steel Sword', 1),
        'cost_gold': 50,
    }
}


class Crafting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='recipes', with_app_command=True)
    async def recipes(self, ctx: commands.Context):
        """List semua resep crafting"""
        lines = []
        for k, v in RECIPES.items():
            ing = ', '.join([f"{n}x {q}" if q!=1 else n for n, q in v['ingredients'].items()])
            lines.append(f"**{v['display']}** (`{k}`): {ing} — cost {v.get('cost_gold',0)} gold")
        embed = discord.Embed(title='📜 Recipes', description='Available crafting recipes', color=0x8E44AD)
        embed.add_field(name='Recipes', value='\n'.join(lines), inline=False)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name='recipe', with_app_command=True)
    async def recipe(self, ctx: commands.Context, name: str):
        """Show recipe details: !recipe <recipe_key>"""
        key = name.strip().lower()
        if key not in RECIPES:
            await ctx.reply('Recipe tidak ditemukan')
            return
        v = RECIPES[key]
        ing = '\n'.join([f"- {n}: {q}" for n, q in v['ingredients'].items()])
        desc = f"Ingredients:\n{ing}\nCost: {v.get('cost_gold',0)} gold\nProduces: {v['result'][1]}x {v['result'][0]}"
        embed = discord.Embed(title=f"Recipe: {v['display']}", description=desc, color=0x8E44AD)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name='craft', with_app_command=True)
    async def craft(self, ctx: commands.Context, name: str):
        """Craft an item if you have the ingredients and gold: !craft <recipe_key>"""
        if not ctx.guild:
            await ctx.reply('Hanya di server')
            return
        guild_id = ctx.guild.id
        user_id = ctx.author.id
        key = name.strip().lower()
        if key not in RECIPES:
            await ctx.reply('Recipe tidak ditemukan')
            return
        v = RECIPES[key]
        inv = get_inventory(guild_id, user_id)
        inv_map = {row[0]: row[1] for row in inv}
        # check ingredients
        missing = []
        for item_name, qty in v['ingredients'].items():
            if inv_map.get(item_name, 0) < qty:
                missing.append(f"{item_name} x{qty}")
        if missing:
            await ctx.reply(f"Bahan kurang: {', '.join(missing)}")
            return
        # check gold
        cost = v.get('cost_gold', 0)
        profile = get_profile(guild_id, user_id)
        if cost and profile['gold'] < cost:
            await ctx.reply('Gold tidak cukup untuk crafting')
            return
        # consume ingredients
        for item_name, qty in v['ingredients'].items():
            remove_item(guild_id, user_id, item_name, qty=qty)
        # charge gold
        if cost:
            spend_gold(guild_id, user_id, cost)
        # give result
        result_name, result_qty = v['result']
        add_item(guild_id, user_id, result_name, qty=result_qty)
        await ctx.reply(f'✅ Berhasil craft {result_qty}x {result_name}!')


async def setup(bot: commands.Bot):
    await bot.add_cog(Crafting(bot))
