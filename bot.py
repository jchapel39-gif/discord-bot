import discord
from discord.ext import commands
import os
import requests

# Intents nécessaires
intents = discord.Intents.default()
intents.message_content = True

# Préfixe du bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Variables Nitrado (à définir dans Portainer > Environment variables)
NITRADO_API_TOKEN = os.getenv("NITRADO_API_TOKEN")      # Ta clé API Nitrado
NITRADO_SERVICE_ID = os.getenv("NITRADO_SERVICE_ID")    # L'ID de ton serveur FS25

# Headers pour les requêtes API Nitrado
headers = {
    "Authorization": f"Bearer {NITRADO_API_TOKEN}"
}

@bot.event
async def on_ready():
    print(f"{bot.user} est connecté ! Prêt à gérer la ferme FS25 sur Nitrado.")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong ! Le bot est en ligne 🚜")

async def nitrado_control(action: str, ctx):
    if not NITRADO_API_TOKEN or not NITRADO_SERVICE_ID:
        await ctx.send("Erreur : Token API ou Service ID Nitrado manquant. Contacte l'admin.")
        return

    try:
        if action == "status":
            url = f"https://api.nitrado.net/services/{NITRADO_SERVICE_ID}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            status = data['data']['service']['status'].capitalize()
            await ctx.send(f"**Statut du serveur FS25** : {status}")
        else:
            url = f"https://api.nitrado.list/services/{NITRADO_SERVICE_ID}/gameserver/{action}"
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            await ctx.send(f"Commande **{action.upper()}** envoyée au serveur FS25 ! 🌾")
    except requests.exceptions.HTTPError as http_err:
        await ctx.send(f"Erreur API Nitrado : {http_err} (vérifie token/ID ou scopes)")
    except Exception as e:
        await ctx.send(f"Erreur inattendue : {str(e)}")

# Commandes Nitrado existantes
@bot.command()
async def fs_status(ctx):
    await nitrado_control("status", ctx)

@bot.command()
async def fs_start(ctx):
    await nitrado_control("start", ctx)

@bot.command()
async def fs_stop(ctx):
    await nitrado_control("stop", ctx)

@bot.command()
async def fs_restart(ctx):
    await nitrado_control("restart", ctx)

# Nouvelle commande : Liste des joueurs (compteur seulement pour FS25)
@bot.command()
async def fs_joueurs(ctx):
    if not NITRADO_API_TOKEN or not NITRADO_SERVICE_ID:
        await ctx.send("Erreur : Token API ou Service ID Nitrado manquant.")
        return

    try:
        url = f"https://api.nitrado.net/services/{NITRADO_SERVICE_ID}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()['data']['service']

        current = data.get('current_players', 0)  # Nombre de joueurs connectés
        slots = data.get('slots', 16)             # Nombre total de slots

        await ctx.send(f"**Joueurs connectés sur le serveur FS25** : {current}/{slots}\n"
                       "(Noms non disponibles via l'API pour Farming Simulator – visible dans le panel Nitrado ou en jeu)")
    except Exception as e:
        await ctx.send(f"Erreur récupération joueurs : {str(e)}")

@bot.command()
async def fs_help(ctx):
    help_text = (
        "**Commandes Farming Simulator 2025 (Nitrado)**\n\n"
        "`!ping` → Teste si le bot répond\n"
        "`!fs_status` → Affiche l'état actuel du serveur\n"
        "`!fs_joueurs` → Affiche le nombre de joueurs connectés (noms non disponibles via API)\n"
        "`!fs_start` → Démarre le serveur\n"
        "`!fs_stop` → Arrête le serveur\n"
        "`!fs_restart` → Redémarre le serveur\n"
        "`!fs_help` → Affiche ce message\n\n"
        "Mods et détails joueurs : gère-les via le panel Nitrado → Admin Web Interface"
    )
    await ctx.send(help_text)

# Lancement du bot
bot.run(os.getenv("DISCORD_TOKEN"))
