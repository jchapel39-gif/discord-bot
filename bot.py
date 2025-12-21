import discord
from discord.ext import commands, tasks
import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, time
import ftplib
import xml.etree.ElementTree as ET
from requests.auth import HTTPBasicAuth

# Intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Variables
WEB_URL = os.getenv("WEB_URL")  # http://192.168.1.59:7999
WEB_USER = os.getenv("WEB_USER", "admin")
WEB_PASS = os.getenv("WEB_PASS", "15072018")
FTP_HOST = os.getenv("FTP_HOST")
FTP_PORT = int(os.getenv("FTP_PORT", 21))
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
SAVE_PATH = os.getenv("SAVE_PATH")  # /config/FarmingSimulator2025/savegame1
REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID", "0"))

# Fichier pour stocker les derniers mods vus
LAST_MODS_FILE = "last_mods.json"

@bot.command()
async def ping(ctx):
    await ctx.send("Pong ! Le bot est en ligne 🚜")

# --- Statut serveur + joueurs + mods via interface web ---
async def get_server_status():
    try:
        stats_path = "/fs25_save/FarmingSimulator2025/dedicated_server/gameStats.xml"
        
        if not os.path.exists(stats_path):
            return {'error': "gameStats.xml non trouvé (serveur pas lancé ou pas de partie ?)"}
        
        root = ET.parse(stats_path).getroot()
        
        # Statut
        status = "En ligne" if root.find('.//Slots') is not None else "Hors ligne"
        
        # Joueurs avec noms
        players = []
        for player in root.findall('.//Slots/Player'):
            if player.get('isUsed') == "true":
                name = player.text.strip() if player.text else "Inconnu"
                players.append(name)
        players_text = ", ".join(players) if players else "Aucun"
        players_count = len(players)
        
        # Mods installés
        mods = []
        for mod in root.findall('.//Mods/Mod'):
            name = mod.get('name', "Inconnu")
            version = mod.get('version', "")
            author = mod.get('author', "")
            mods.append(f"{name} (v{version} par {author})")
        mods_text = "\n".join(mods[:20]) + ("\n... et plus" if len(mods) > 20 else "")
        
        return {
            'status': status,
            'players_count': players_count,
            'players_names': players_text,
            'mods': mods_text,
            'mods_count': len(mods)
        }
    except Exception as e:
        return {'error': f"Erreur lecture gameStats.xml : {str(e)}"}
# --- Infos savegame via FTP ---
async def get_save_info():
    try:
        save_dir = "/fs25_save/FarmingSimulator2025/savegame1"  # Chemin monté dans le conteneur bot
        
        career_path = os.path.join(save_dir, "careerSavegame.xml")
        if not os.path.exists(career_path):
            return "careerSavegame.xml non trouvé (serveur pas lancé ou sauvegarde vide ?)"
        
        career_root = ET.parse(career_path).getroot()
        playtime_elem = career_root.find('.//playTime')
        playtime = float(playtime_elem.text or 0) if playtime_elem is not None else 0
        hours = int(playtime)
        minutes = int((playtime - hours) * 60)
        playtime_str = f"{hours}h {minutes}min"
        
        farms_path = os.path.join(save_dir, "farms.xml")
        if not os.path.exists(farms_path):
            return "farms.xml non trouvé."
        
        farms_root = ET.parse(farms_path).getroot()
        
        farms = {}
        total_money = 0
        for farm in farms_root.findall('farm'):
            fid = farm.get('farmId')
            name = farm.get('name', f"Ferme {fid}")
            money = float(farm.get('money', 0))
            farms[name] = money
            total_money += money
        
        return {
            'playtime': playtime_str,
            'total_money': total_money,
            'farms': farms
        }
    except Exception as e:
        return f"Erreur lecture savegame : {str(e)}"

# --- Contrôle serveur ---
async def control_server(action: str):
    try:
        url = f"{WEB_URL}/{action}"
        response = requests.post(url, auth=HTTPBasicAuth(WEB_USER, WEB_PASS), timeout=10)
        response.raise_for_status()
        return True
    except:
        return False

@bot.command()
async def fs_start(ctx):
    if await control_server("start"):
        await ctx.send("Serveur FS25 démarré ! 🌾")
    else:
        await ctx.send("Erreur démarrage serveur.")

@bot.command()
async def fs_stop(ctx):
    if await control_server("stop"):
        await ctx.send("Serveur FS25 arrêté.")
    else:
        await ctx.send("Erreur arrêt serveur.")

@bot.command()
async def fs_restart(ctx):
    if await control_server("restart"):
        await ctx.send("Serveur FS25 redémarré ! 🚜")
    else:
        await ctx.send("Erreur redémarrage serveur.")

# --- Nouveaux mods ModHub ---
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

# --- Rapport quotidien ---
async def send_report():
    if REPORT_CHANNEL_ID == 0:
        print("REPORT_CHANNEL_ID manquant – rapport ignoré.")
        return False
    
    channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not channel:
        print(f"Channel ID {REPORT_CHANNEL_ID} introuvable.")
        return False
    
    server_info = await get_server_status()
    save_info = await get_save_info()
    new_mods = await scrape_new_mods()
    
    embed = discord.Embed(
        title="**Rapport Quotidien FS25 Local 🌾🚜**",
        description=f"Rapport du {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
        color=0x568A3B
    )
    
    # Statut + joueurs + mods serveur (avec gestion d'erreur)
    if 'error' in server_info:
        embed.add_field(name="🚜 Serveur FS25 Local", value=server_info['error'], inline=False)
    else:
        embed.add_field(name="Statut", value=server_info['status'], inline=True)
        embed.add_field(name="Joueurs", value=f"{server_info['players_count']} connectés\n{server_info['players_names']}", inline=True)
        embed.add_field(name="Mods serveur", value=f"{server_info['mods_count']} installés", inline=True)
    
    # Savegame
    if isinstance(save_info, dict):
        farms_text = "\n".join([f"• **{name}** : ${money:,.0f}" for name, money in save_info['farms'].items()]) or "Aucune ferme"
        embed.add_field(name="💰 Savegame", value=f"⏱️ Temps de jeu : {save_info['playtime']}\n💵 Argent total : ${save_info['total_money']:,.0f}\n🏡 Fermes :\n{farms_text}", inline=False)
    else:
        embed.add_field(name="💰 Savegame", value=save_info, inline=False)
    
    # Nouveaux mods ModHub
    if new_mods and not new_mods[0].startswith("Aucun"):
        embed.add_field(name=f"🌱 Nouveaux Mods ModHub ({len(new_mods)} aujourd'hui)", value="\n\n".join(new_mods[:10]), inline=False)
    else:
        embed.add_field(name="🌱 Nouveaux Mods ModHub", value="Aucun aujourd'hui", inline=False)
    
    # Mini-map (si disponible)
    if 'map_url' in server_info:
        embed.set_image(url=server_info['map_url'])
    
    embed.set_thumbnail(url="https://farmingsimulator22mods.com/wp-content/uploads/2025/12/new-holland-8340-v1-0-0-1-fs25-1.jpg")
    embed.set_footer(text="Bot FS25 Local • Prochain rapport demain à 9h")
    
    await channel.send(embed=embed)
    return True

# Rapport quotidien à 9h
@tasks.loop(time=time(hour=9, minute=0))
async def daily_report():
    await send_report()

@bot.event
async def on_ready():
    print(f"{bot.user} est connecté ! Bot FS25 local activé.")
    if not daily_report.is_running():
        daily_report.start()

@bot.command()
async def test_report(ctx):
    await ctx.send("Génération du rapport complet... 🌾")
    await send_report()
    await ctx.send("Rapport envoyé !")

@bot.command()
async def fs_help(ctx):
    await ctx.send(
        "**Commandes FS25 Local**\n"
        "`!ping` → Test\n"
        "`!fs_status` → Statut + joueurs + mods serveur\n"
        "`!fs_start` / `!fs_stop` / `!fs_restart` → Contrôle serveur\n"
        "`!test_report` → Rapport complet immédiat\n"
        "`!fs_help` → Ce message\n\n"
        "Rapport automatique tous les jours à 9h avec tout !"
    )

bot.run(os.getenv("DISCORD_TOKEN"))









