import discord
from discord.ext import commands, tasks
import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import asyncio

# Intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Variables Nitrado + Discord
NITRADO_API_TOKEN = os.getenv("NITRADO_API_TOKEN")
NITRADO_SERVICE_ID = os.getenv("NITRADO_SERVICE_ID")
REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID", 0))  # ID du channel pour le rapport quotidien (obligatoire !)

# Headers Nitrado
headers = {"Authorization": f"Bearer {NITRADO_API_TOKEN}"}

# Fichier pour stocker les derniers mods vus
LAST_MODS_FILE = "last_mods.json"

@bot.event
async def on_ready():
    print(f"{bot.user} est connecté ! Rapport quotidien FS25 activé.")
    if not daily_report.is_running():
        daily_report.start()

@bot.command()
async def ping(ctx):
    await ctx.send("Pong ! Le bot est en ligne 🚜")

async def get_nitrado_status():
    if not NITRADO_API_TOKEN or not NITRADO_SERVICE_ID:
        return "Erreur : Token ou Service ID Nitrado manquant."
    try:
        url = f"https://api.nitrado.net/services/{NITRADO_SERVICE_ID}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()['data']['service']
        status = data['status'].capitalize()
        players = data.get('current_players', 0)
        slots = data.get('slots', 16)
        return f"**Statut** : {status}\n**Joueurs** : {players}/{slots}"
    except Exception as e:
        return f"Erreur récupération statut : {str(e)}"

@bot.command()
async def fs_status(ctx):
    status = await get_nitrado_status()
    await ctx.send(status)

@bot.command()
async def fs_joueurs(ctx):
    status = await get_nitrado_status()
    await ctx.send(status)  # Même fonction pour simplifier

async def scrape_new_mods():
    url = "https://www.farming-simulator.com/mods.php?lang=en&country=fr&title=fs2025&filter=newest"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        new_mods = []
        last_seen = load_last_mods()
        
        mod_items = soup.find_all('div', class_='mod-item')[:15]  # Les 15 plus récents
        
        for item in mod_items:
            title_elem = item.find('h3')
            link_elem = item.find('a', href=True)
            date_elem = item.find('span', class_='date')
            
            if title_elem and link_elem and date_elem:
                title = title_elem.text.strip()
                link = "https://www.farming-simulator.com" + link_elem['href']
                date_str = date_elem.text.strip()
                mod_id = link.split('mod_id=')[1].split('&')[0] if 'mod_id=' in link else ""
                
                # Détecter si nouveau (par ID ou date récente)
                if mod_id and mod_id not in last_seen:
                    new_mods.append(f"**{title}** ({date_str})\n{link}")
                    last_seen.add(mod_id)
        
        save_last_mods(last_seen)
        return new_mods if new_mods else ["Aucun nouveau mod aujourd'hui sur le ModHub officiel."]
    except Exception as e:
        return [f"Erreur scraping ModHub : {str(e)}"]

def load_last_mods():
    if os.path.exists(LAST_MODS_FILE):
        with open(LAST_MODS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_last_mods(mods_set):
    with open(LAST_MODS_FILE, 'w') as f:
        json.dump(list(mods_set), f)

# Rapport quotidien à 9h (heure du serveur)
@tasks.loop(time=datetime.time(hour=9, minute=0))  # 9h00 UTC (ajuste si besoin avec tz)
async def daily_report():
    if REPORT_CHANNEL_ID == 0:
        print("REPORT_CHANNEL_ID manquant – rapport ignoré.")
        return
    
    channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not channel:
        print("Channel rapport introuvable.")
        return
    
    status = await get_nitrado_status()
    new_mods = await scrape_new_mods()
    
    report = (
        f"**Rapport quotidien FS25 - {datetime.now().strftime('%d/%m/%Y')}**\n\n"
        f"**Serveur Nitrado**\n{status}\n\n"
        f"**Nouveaux mods sur ModHub officiel** ({len(new_mods)} aujourd'hui) :\n"
    )
    for mod in new_mods:
        report += mod + "\n"
    
    await channel.send(report)

@bot.command()
async def fs_help(ctx):
    await ctx.send(
        "**Commandes FS25**\n"
        "`!ping` → Test\n"
        "`!fs_status` → Statut serveur\n"
        "`!fs_joueurs` → Joueurs connectés\n"
        "`!fs_help` → Ce message\n\n"
        "Rapport automatique tous les jours à 9h dans le channel configuré !"
    )

bot.run(os.getenv("DISCORD_TOKEN"))
