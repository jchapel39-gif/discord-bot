import discord
from discord.ext import commands
import os
import requests
from xml.etree import ElementTree as ET

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

FS_SERVER_URL = "85.190.160.26:11900"  # Remplace par l'IP/port de ton serveur FS
FS_WEB_USER = "admin"                  # Username de l'interface web
FS_WEB_PASS = "S6kby6Kz"                # Mot de passe de l'interface web

@bot.event
async def on_ready():
    print(f"{bot.user} est connecté !")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong !")

# Liste des joueurs
@bot.command()
async def fs_joueurs(ctx):
    try:
        response = requests.get(f"{FS_SERVER_URL}/link.xml")
        response.raise_for_status()
        root = ET.fromstring(response.content)
        players = [player.find('name').text for player in root.findall('.//player')]
        if players:
            await ctx.send("**Joueurs connectés :**\n" + "\n".join(players))
        else:
            await ctx.send("Aucun joueur connecté.")
    except Exception as e:
        await ctx.send(f"Erreur : {str(e)} (serveur FS inaccessible ?)")

# Liste des mods
@bot.command()
async def fs_mods(ctx):
    try:
        response = requests.get(f"{FS_SERVER_URL}/link.xml")
        response.raise_for_status()
        root = ET.fromstring(response.content)
        mods = [f"{mod.find('name').text} (v{mod.find('version').text})" for mod in root.findall('.//mod')]
        if mods:
            await ctx.send("**Mods installés :**\n" + "\n".join(mods[:20]) + ("\n... et plus" if len(mods)>20 else ""))
        else:
            await ctx.send("Aucun mod installé.")
    except Exception as e:
        await ctx.send(f"Erreur : {str(e)}")

# Contrôle du serveur (stop/start/restart)
async def control_server(action: str, ctx):
    try:
        auth = (FS_WEB_USER, FS_WEB_PASS)
        if action == "stop":
            requests.post(f"{FS_SERVER_URL}/stop", auth=auth)
        elif action == "start":
            requests.post(f"{FS_SERVER_URL}/start", auth=auth)
        elif action == "restart":
            requests.post(f"{FS_SERVER_URL}/restart", auth=auth)
        await ctx.send(f"Serveur FS : {action} demandé !")
    except Exception as e:
        await ctx.send(f"Erreur contrôle : {str(e)} (mauvais auth ?)")

@bot.command()
async def fs_stop(ctx):
    await control_server("stop", ctx)

@bot.command()
async def fs_start(ctx):
    await control_server("start", ctx)

@bot.command()
async def fs_restart(ctx):
    await control_server("restart", ctx)

bot.run(os.getenv("DISCORD_TOKEN"))
