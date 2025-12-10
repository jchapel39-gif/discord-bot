import discord
from discord.ext import commands, tasks
import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

# Intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Variables Nitrado + Discord
NITRADO_API_TOKEN = os.getenv("NITRADO_API_TOKEN")
NITRADO_SERVICE_ID = os.getenv("NITRADO_SERVICE_ID")
REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID", 0))  # ID du channel pour les rapports (obligatoire)

# Headers Nitrado
headers = {"Authorization": f"Bearer {NITRADO_API_TOKEN}"}

# Fichier pour stocker les derniers mods vus (IDs)
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
    await ctx.send(f"**Statut du serveur FS25**\n{status}")

@bot.command()
async def fs_joueurs(ctx):
    status = await get_nitrado_status()
    await ctx.send(f"**Joueurs connectés sur le serveur FS25**\n{status.split('Joueurs')[1] if 'Joueurs' in status else status}")

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
            date_elem = item.find('span', class_='date') or item.find(text=lambda t: 'ago' in t or 'Today' in t or 'Yesterday' in t)
            
            if title_elem and link_elem:
                title = title_elem.text.strip()
                link = "https://www.farming-simulator.com" + link_elem['href']
                mod_id = link.split('mod_id=')[1].split('&')[0] if 'mod_id=' in link else None
                date_str = date_elem.text.strip() if date_elem else "Date inconnue"
                
                if mod_id and mod_id not in last_seen:
                    new_mods.append(f"**{title}** ({date_str})\n{link}")
                    last_seen.add(mod_id)
        
        if new_mods:
            save_last_mods(last_seen)
        return new_mods if new_mods else ["Aucun nouveau mod détecté aujourd'hui sur le ModHub officiel."]
    except Exception as e:
        return [f"Erreur scraping ModHub : {str(e)} (site inaccessible ou structure changée)"]

def load_last_mods():
    if os.path.exists(LAST_MODS_FILE):
        try:
            with open(LAST_MODS_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_last_mods(mods_set):
    with open(LAST_MODS_FILE, 'w') as f:
        json.dump(list(mods_set), f)

async def send_report():
    if REPORT_CHANNEL_ID == 0:
        print("REPORT_CHANNEL_ID manquant – impossible d'envoyer le rapport.")
        return False
    
    channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not channel:
        print("Channel rapport introuvable.")
        return False
    
    status = await get_nitrado_status()
    new_mods = await scrape_new_mods()
    
    report = (
        f"**Rapport FS25 - {datetime.now().strftime('%d/%m/%Y à %H:%M')}**\n\n"
        f"**Serveur Nitrado**\n{status}\n\n"
        f"**Nouveaux mods sur ModHub officiel** ({len(new_mods) if isinstance(new_mods, list) else 0} aujourd'hui) :\n"
    )
    for mod in new_mods:
        report += mod + "\n\n"
    
    await channel.send(report)
    return True

# Rapport quotidien à 9h (UTC – ajuste si ton serveur est en heure FR : ajoute tzinfo si besoin)
@tasks.loop(time=datetime.time(hour=9, minute=0))
async def daily_report():
    await send_report()

# Nouvelle commande pour tester le rapport immédiatement
@bot.command()
async def test_report(ctx):
    await ctx.send("Génération du rapport de test en cours... 🌾")
    success = await send_report()
    if success:
        await ctx.send("Rapport envoyé dans le channel configuré !")
    else:
        await ctx.send("Erreur lors de l'envoi (vérifie REPORT_CHANNEL_ID)")

@bot.command()
async def fs_help(ctx):
    await ctx.send(
        "**Commandes FS25**\n"
        "`!ping` → Test\n"
        "`!fs_status` → Statut serveur\n"
        "`!fs_joueurs` → Joueurs connectés\n"
        "`!test_report` → Envoie un rapport de test immédiatement\n"
        "`!fs_help` → Ce message\n\n"
        "Rapport automatique tous les jours à 9h dans le channel configuré !"
    )

bot.run(os.getenv("DISCORD_TOKEN"))
