import asyncio
import os

import discord
from discord.ext import commands

# Préfixe des salons créés par Ticket Tool (réglable dans Ticket Tool : /panel -> nom du salon)
TICKET_PREFIX = os.getenv("TICKET_PREFIX", "demande-de-ticket")
ANSWER_TIMEOUT = 10 * 60  # secondes laissées au joueur pour répondre

# ---------------------------------------------------------------------------
# Définition du questionnaire
# Chaque étape : une question + une fonction next(answer, data) qui enregistre
# la réponse et renvoie le nom de l'étape suivante (ou None pour terminer).
# ---------------------------------------------------------------------------
STEPS = {
    "joueur": {
        "question": "Quel est le joueur impliqué ?",
        "next": lambda answer, data: _save(data, "joueur", answer, None),
        # exemple de branche à venir :
        # "next": lambda a, d: _save(d, "joueur", a, "motif"),
    },
}


def _save(data: dict, key: str, value: str, next_step):
    data[key] = value
    return next_step


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _find_ticket_owner(self, channel: discord.TextChannel):
        """Retrouve le joueur : le membre non-bot qui a accès au salon via une permission propre."""
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Role):
                continue
            if overwrite.view_channel is not True:
                continue
            member = target if isinstance(target, discord.Member) else None
            if member is None:
                try:
                    member = await channel.guild.fetch_member(target.id)
                except discord.HTTPException:
                    continue
            if not member.bot:
                return member
        return None

    async def _run_flow(self, channel: discord.TextChannel, user: discord.Member):
        data: dict = {}
        current = "joueur"

        while current:
            step = STEPS[current]
            await channel.send(f"{user.mention} {step['question']}")

            def check(m: discord.Message):
                return m.channel.id == channel.id and m.author.id == user.id

            try:
                msg = await self.bot.wait_for("message", check=check, timeout=ANSWER_TIMEOUT)
            except asyncio.TimeoutError:
                await channel.send("⏱️ Pas de réponse, le questionnaire est interrompu.")
                return

            current = step["next"](msg.content.strip(), data)

        await channel.send("✅ Merci, les informations ont bien été enregistrées. Un admin va prendre le relais.")
        # TODO : ping du staff, sauvegarde, embed récapitulatif...
        print(f"[Ticket {channel.name}] {data}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        if not isinstance(channel, discord.TextChannel):
            return
        if not channel.name.startswith(TICKET_PREFIX):
            return

        # Ticket Tool applique les permissions du joueur juste après la création du salon
        await asyncio.sleep(3)
        channel = self.bot.get_channel(channel.id) or channel

        user = await self._find_ticket_owner(channel)
        if user is None:
            print(f"[Ticket {channel.name}] joueur introuvable, questionnaire ignoré.")
            return

        await self._run_flow(channel, user)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
