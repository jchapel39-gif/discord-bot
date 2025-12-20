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
        response = requests.get(f"{WEB_URL}/link.xml", auth=HTTPBasicAuth(WEB_USER, WEB_PASS), timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        status = "En ligne" if root.find('.//slots') is not None else "Hors ligne"
        
        players = []
        for player in root.findall('.//player'):
            name = player.find('name').text if player.find('name') is not None else "Inconnu"
            players.append(name)
        players_text = ", ".join(players) if players else "Aucun"
        players_count = len(players)
        
        mods = []
        for mod in root.findall('.//mod'):
            name = mod.find('name').text if mod.find('name') is not None else "Inconnu"
            version = mod.find('version').text if mod.find('version') is not None else ""
            mods.append(f"{name} (v{version})")
        mods_text = "\n".join(mods[:20]) + ("\n... et plus" if len(mods) > 20 else "")
        
        return {
            'status': status,
            'players_count': players_count,
            'players_names': players_text,
            'mods': mods_text,
            'mods_count': len(mods)
        }
    except Exception as e:
        return {'error': f"Erreur accès serveur : {str(e)}"}

@bot.command()
async def fs_status(ctx):
    info = await get_server_status()
    if 'error' in info:
        await ctx.send(info['error'])
    else:
        embed = discord.Embed(title="**Statut Serveur FS25 Local**", color=0x568A3B)
        embed.add_field(name="Statut", value=info['status'], inline=False)
        embed.add_field(name="Joueurs", value=f"{info['players_count']} connectés\n{info['players_names']}", inline=False)
        embed.add_field(name="Mods installés", value=f"{info['mods_count']} mods\n{info['mods']}", inline=False)
        await ctx.send(embed=embed)

# --- Infos savegame via FTP ---
async def get_save_info():
    if not all([FTP_HOST, FTP_USER, FTP_PASS, SAVE_PATH]):
        return "Erreur : Infos FTP manquantes."
    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(SAVE_PATH)
        
        # careerSavegame.xml
        career_data = []
        ftp.retrlines('RETR careerSavegame.xml', career_data.append)
        career_content = '\n'.join(career_data)
        career_root = ET.fromstring(career_content)
        playtime_elem = career_root.find('.//playTime')
        playtime = float(playtime_elem.text or 0) if playtime_elem is not None else 0
        hours = int(playtime)
        minutes = int((
