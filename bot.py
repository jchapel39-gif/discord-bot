NITRADO_API_TOKEN = os.getenv("dQBNhUFsi_nkkmdXOJpmZFbZQN-zTs0s6winJQZLr-HANBEI9RqSTgXHCvJ7Pkc6NwOLXTqUbUyfAvjYhI_71zLFPsMy3fzYNmjC")  # Ton API key
NITRADO_SERVICE_ID = os.getenv("18100027")  # Ton service ID (un nombre)

headers = {
    "Authorization": f"Bearer {NITRADO_API_TOKEN}"
}

async def nitrado_control(action: str, ctx):
    try:
        if action == "status":
            url = f"https://api.nitrado.net/services/{NITRADO_SERVICE_ID}"
            response = requests.get(url, headers=headers)
            data = response.json()
            status = data['data']['service']['status']
            await ctx.send(f"Statut serveur FS25 : {status}")
        else:
            url = f"https://api.nitrado.net/services/{NITRADO_SERVICE_ID}/gameserver/{action}"
            response = requests.post(url, headers=headers)
            await ctx.send(f"Commande {action} envoyée au serveur FS25 !")
    except Exception as e:
        await ctx.send(f"Erreur Nitrado API : {str(e)} (vérifie token/ID)")

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
