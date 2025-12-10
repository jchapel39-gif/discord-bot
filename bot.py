import discord
from discord.ext import commands, tasks
import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, time

# Intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Variables d'environnement
NITRADO_API_TOKEN = os.getenv("NITRADO_API_TOKEN")
NITRADO_SERVICE_ID = os.getenv("NITRADO_SERVICE_ID")
REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID", "0"))

# Headers Nitrado
headers = {"Authorization": f"Bearer {NITRADO_API_TOKEN}"}

# Fichier pour stocker les derniers mods vus
LAST_MODS_FILE = "last_mods.json"

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
    await ctx.send(f"**Joueurs connectés**\n{status.split('Joueurs')[1] if 'Joueurs' in status else status}")

async def scrape_new_mods():
    url = "https://www.farming-simulator.com/mods.php?lang=en&country=fr&title=fs2025&filter=newest"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        new_mods = []
        last_seen = load_last_mods()
        
        mod_items = soup.find_all('div', class_='mod-item')[:15]
        
        for item in mod_items:
            title_elem = item.find('h3')
            link_elem = item.find('a', href=True)
            date_elem = item.find('span', class_='date') or item.find(string=lambda t: 'ago' in t or 'Today' in t or 'Yesterday' in t if t else False)
            
            if title_elem and link_elem:
                title = title_elem.text.strip()
                link = "https://www.farming-simulator.com" + link_elem['href']
                mod_id = link.split('mod_id=')[1].split('&')[0] if 'mod_id=' in link else None
                date_str = date_elem.strip() if isinstance(date_elem, str) else (date_elem.text.strip() if date_elem else "Date inconnue")
                
                if mod_id and mod_id not in last_seen:
                    new_mods.append(f"**{title}** ({date_str})\n{link}")
                    last_seen.add(mod_id)
        
        if new_mods:
            save_last_mods(last_seen)
        return new_mods if new_mods else ["Aucun nouveau mod détecté aujourd'hui sur le ModHub officiel."]
    except Exception as e:
        return [f"Erreur scraping ModHub : {str(e)}"]

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
        print("REPORT_CHANNEL_ID manquant – rapport ignoré.")
        return False
    
    channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not channel:
        print(f"Channel ID {REPORT_CHANNEL_ID} introuvable.")
        return False
    
    status = await get_nitrado_status()
    new_mods = await scrape_new_mods()
    
    embed = discord.Embed(
        title="**Rapport Quotidien FS25 🌾🚜**",
        description=f"Rapport du {datetime.now().strftime('%d/%m/%Y à %H:%M')} – Tout va bien à la ferme !",
        color=0x568A3B  # Vert champ
    )
    
    embed.add_field(name="🚜 Statut du Serveur Nitrado", value=status, inline=False)
    
    # Nouveaux mods
    if new_mods and not new_mods[0].startswith("Aucun") and not new_mods[0].startswith("Erreur"):
        mods_text = "\n\n".join(new_mods[:10])
        embed.add_field(name=f"🌱 Nouveaux Mods sur ModHub Officiel ({len(new_mods)} aujourd'hui)", value=mods_text, inline=False)
    else:
        embed.add_field(name="🌱 Nouveaux Mods sur ModHub Officiel", value=new_mods[0] if new_mods else "Aucun.", inline=False)
    
    embed.set_thumbnail(url="https://farmingsimulator22mods.com/wp-content/uploads/2025/12/new-holland-8340-v1-0-0-1-fs25-1.jpg")
    embed.set_footer(text="Bot FS25 • Prochain rapport demain à 9h")
    
    await channel.send(embed=embed)
    return True

# Rapport quotidien à 9h
@tasks.loop(time=time(hour=9, minute=0))
async def daily_report():
    await send_report()

@bot.event
async def on_ready():
    print(f"{bot.user} est connecté ! Rapport quotidien FS25 activé.")
    if not daily_report.is_running():
        daily_report.start()

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
        "`!test_report` → Rapport immédiat\n"
        "`!fs_help` → Ce message\n\n"
        "Rapport automatique tous les jours à 9h avec statut et nouveaux mods !"
    )

bot.run(os.getenv("DISCORD_TOKEN"))
