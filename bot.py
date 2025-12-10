import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} est connecté !')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong !')

bot.run(os.getenv('MTQ0ODAxNTE3MzQ0NDA0NzAzNw.GiIbDD.-GS0e-03ldz70SDJaHKXi4cxsp4KpI1gsO_VbA'))

