import discord
from discord.ext import commands
import os
import requests
from xml.etree import ElementTree as ET

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

FS_SERVER_URL = os.getenv("85.190.160.26:11900")
FS_WEB_USER = os.getenv("admin")
FS_WEB_PASS = os.getenv("S6kby6Kz")
AUTH = (FS_WEB_USER, FS_WEB_PASS) if FS_WEB_USER and FS_WEB_PASS else None

@bot.event
async def on_ready():
    print(f"{bot.user} est connecté !")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong !")

async def get_xml(ctx):
    try:
        response = requests.get(f"{FS_SERVER_URL}/link.xml")
        response.raise_for_status()
        return ET.fromstring(response.content)
    except Exception as e:
        await ctx.send(f"Erreur accès serveur FS : {str(e)} (vérifie URL/port/API activée)")
        return None

@bot.command()
async def fs_joueurs(ctx):
    root = await get_xml(ctx)
    if not root:
        return
    players = [player.find('name').text for player in root.findall('.//player') if player.find('name') is not None]
    if players:
        await ctx.send("**Joueurs connectés :**\n" + "\n".join(players))
    else:
        await ctx.send("Aucun joueur connecté.")

@bot.command()
async def fs_mods(ctx):
    root = await get_xml(ctx)
    if not root:
        return
    mods = []
    for mod in root.findall('.//mod'):
        name = mod.find('name').text if mod.find('name') is not None else "Inconnu"
        version = mod.find('version').text if mod.find('version') is not None else ""
        mods.append(f"{name} (v{version})")
    if mods:
        message = "**Mods installés :**\n" + "\n".join(mods[:30])
        if len(mods) > 30:
            message += f"\n... et {len(mods)-30} de plus"
        await ctx.send(message)
    else:
        await ctx.send("Aucun mod installé.")

async def control_fs(action: str, ctx):
    try:
        url = f"{FS_SERVER_URL}/{action}"
        response = requests.post(url, auth=AUTH)
        response.raise_for_status()
        await ctx.send(f"Serveur FS25 : {action} demandé !")
    except Exception as e:
        await ctx.send(f"Erreur {action} serveur : {str(e)} (mauvais auth ? serveur off ?)")

@bot.command()
async def fs_stop(ctx):
    await control_fs("stop", ctx)

@bot.command()
async def fs_start(ctx):
    await control_fs("start", ctx)

@bot.command()
async def fs_restart(ctx):
    await control_fs("restart", ctx)

@bot.command()
async def fs_help(ctx):
    await ctx.send("Commandes FS25 :\n!fs_joueurs\n!fs_mods\n!fs_stop\n!fs_start\n!fs_restart")

bot.run(os.getenv("DISCORD_TOKEN"))

