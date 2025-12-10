import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True  # Obligatoire pour lire les messages

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} est connecté !")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong !")

bot.run(os.getenv("DISCORD_TOKEN"))  # Utilise une variable d'environnement pour le token


