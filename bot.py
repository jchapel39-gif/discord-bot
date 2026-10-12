import os

import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True  # à activer aussi dans le Developer Portal
intents.members = True          # idem (Server Members Intent)

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def setup_hook():
    await bot.load_extension("tickets")


@bot.event
async def on_ready():
    print(f"{bot.user} est connecté ! AdminArma3 activé.")


@bot.command()
async def ping(ctx):
    await ctx.send("Pong ! AdminArma3 est en ligne 🪖")


token = os.getenv("DISCORD_TOKEN")
if not token:
    raise SystemExit("DISCORD_TOKEN manquant (voir .env.example)")
bot.run(token)
