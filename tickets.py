import asyncio
import os
import re

import discord
from discord.ext import commands


def normalize(text: str) -> str:
    return re.sub(r"[\s_]+", "-", (text or "").lower())


# Un salon est considéré comme un ticket si son nom OU sa catégorie contient ce texte
TICKET_MATCH = normalize(os.getenv("TICKET_MATCH", "ticket"))
ANSWER_TIMEOUT = 10 * 60  # secondes laissées au joueur pour répondre

# ---------------------------------------------------------------------------
# Questionnaire : chaque étape = une question + next(answer, data) qui
# enregistre la réponse et renvoie l'étape suivante (ou None pour terminer).
# ---------------------------------------------------------------------------
STEPS = {
    "joueur": {
        "question": "Quel est le joueur impliqué ?",
        "next": lambda answer, data: _save(data, "joueur", answer, None),
    },
}


def _save(data: dict, key: str, value: str, next_step):
    data[key] = value
    return next_step


def is_ticket_channel(channel: discord.TextChannel) -> bool:
    name = normalize(channel.name)
    category = normalize(channel.category.name) if channel.category else ""
    return TICKET_MATCH in name or TICKET_MATCH in category


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Retrouver le joueur qui a ouvert le ticket ---------------------------
    async def _owner_from_overwrites(self, channel: discord.TextChannel):
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Role) or overwrite.view_channel is not True:
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

    async def _owner_from_history(self, channel: discord.TextChannel):
        """Plan B : le 1er message de Ticket Tool mentionne le joueur."""
        try:
            async for msg in channel.history(limit=10, oldest_first=True):
                if msg.author.bot:
                    for user in msg.mentions:
                        if not user.bot:
                            return user
        except discord.HTTPException:
            pass
        return None

    async def _find_owner(self, channel: discord.TextChannel):
        for _ in range(3):
            await asyncio.sleep(2)
            owner = await self._owner_from_overwrites(channel) or await self._owner_from_history(channel)
            if owner:
                return owner
        return None

    # --- Déroulé du questionnaire --------------------------------------------
    async def run_flow(self, channel: discord.TextChannel, user: discord.abc.User):
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
        print(f"[Ticket {channel.name}] réponses : {data}")

    # --- Événements -------------------------------------------------------------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        cat = channel.category.name if getattr(channel, "category", None) else "aucune"
        print(f"[Salon créé] nom={channel.name!r} catégorie={cat!r} type={channel.type}")

        if not isinstance(channel, discord.TextChannel) or not is_ticket_channel(channel):
            print(f"[Salon créé] ignoré (ne contient pas {TICKET_MATCH!r})")
            return

        user = await self._find_owner(channel)
        if user is None:
            print(f"[Ticket {channel.name}] joueur introuvable, questionnaire ignoré.")
            return

        print(f"[Ticket {channel.name}] joueur détecté : {user}")
        await self.run_flow(channel, user)

    # --- Test manuel (admins) : !ticket_test dans n'importe quel salon -------------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ticket_test(self, ctx: commands.Context):
        await self.run_flow(ctx.channel, ctx.author)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
