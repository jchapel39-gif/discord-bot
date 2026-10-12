import asyncio
import os
import re

import discord
from discord.ext import commands


def normalize(text: str) -> str:
    return re.sub(r"[\s_]+", "-", (text or "").lower())


# Un salon est considéré comme un ticket si son nom OU sa catégorie contient ce texte
TICKET_MATCH = normalize(os.getenv("TICKET_MATCH", "ticket"))
ANSWER_TIMEOUT = 10 * 60  # secondes laissées pour répondre à chaque étape
MAX_TRIES = 3             # nombre d'essais si la réponse n'est pas valide

# ---------------------------------------------------------------------------
# Validations
# ---------------------------------------------------------------------------
YOUTUBE_RE = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?(?:youtube\.com/(?:watch\?\S*v=|shorts/|live/)|youtu\.be/)[\w-]{6,}\S*",
    re.IGNORECASE,
)


def validate_amount(text: str):
    return text if re.search(r"\d", text) else None


def validate_youtube(text: str):
    match = YOUTUBE_RE.search(text)
    if not match:
        return None
    url = match.group(0)
    return url if url.lower().startswith("http") else "https://" + url


# ---------------------------------------------------------------------------
# Questionnaire
#  type "choice" : message + réactions ; emoji -> (valeur enregistrée, étape suivante)
#  type "text"   : question ouverte (validate optionnel), réponse dans data[key]
#  type "player" : cherche le joueur sur le Discord et le convoque dans le ticket
#  who : qui peut répondre -> "owner" (ouvreur du ticket), "target" (joueur convoqué), "both"
#  {user} = mention de l'ouvreur, {target} = mention du joueur convoqué
# ---------------------------------------------------------------------------
START = "type"

STEPS = {
    "type": {
        "type": "choice",
        "who": "owner",
        "question": (
            "Bonjour {user}, ta demande concerne-t-elle un incident avec un joueur ou autre chose ?\n\n"
            "✅ : incident avec un joueur\n"
            "❓ : autre chose"
        ),
        "key": "type",
        "choices": {
            "✅": ("incident_joueur", "joueur"),
            "❓": ("autre", "demande"),
        },
    },
    # --- Branche ✅ : incident avec un joueur ---
    "joueur": {
        "type": "player",
        "who": "owner",
        "question": "{user} Quel est le nom du joueur impliqué ? (tu peux aussi le mentionner avec @)",
        "next": "accord",
    },
    "accord": {
        "type": "choice",
        "who": "target",
        "question": (
            "{target}, es-tu d'accord pour régler cet incident à l'amiable avec {user} ?\n\n"
            "✅ : oui, d'accord\n"
            "❌ : non, pas d'accord"
        ),
        "key": "accord",
        "choices": {
            "✅": ("oui", "somme"),
            "❌": ("non", "preuve"),
        },
    },
    "somme": {
        "type": "text",
        "who": "both",
        "question": "Quelle est la somme mise en accord ? ({user} ou {target} peut l'écrire)",
        "key": "somme",
        "validate": validate_amount,
        "error": "Je ne vois pas de montant, écris la somme en chiffres (ex : 50000).",
        "next": None,
    },
    "preuve": {
        "type": "text",
        "who": "owner",
        "question": "{user} Pas d'accord : c'est à toi, qui as ouvert le ticket, de prouver. Envoie un lien YouTube comme preuve vidéo.",
        "key": "preuve",
        "validate": validate_youtube,
        "error": "Ce n'est pas un lien YouTube valide (youtube.com/watch?v=… ou youtu.be/…). Réessaie.",
        "next": None,
    },
    # --- Branche ❓ : autre chose ---
    "demande": {
        "type": "text",
        "who": "owner",
        "question": "{user} Écris ta demande ci-dessous.",
        "key": "demande",
        "next": None,
    },
}


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

    # --- Recherche et convocation du joueur ------------------------------------
    async def _resolve_member(self, guild: discord.Guild, msg: discord.Message, owner):
        """Renvoie (membre, None) ou (None, message d'erreur)."""
        member = next((u for u in msg.mentions if isinstance(u, discord.Member)), None)

        if member is None:
            query = msg.content.strip().lstrip("@").lower()
            if not query:
                return None, "Réponse vide, écris le nom du joueur."
            try:
                results = await guild.query_members(query=query, limit=10)
            except discord.HTTPException:
                results = []
            exact = [
                m for m in results
                if query in (m.name.lower(), m.display_name.lower(), (m.global_name or "").lower())
            ]
            if len(exact) == 1:
                member = exact[0]
            elif len(results) == 1:
                member = results[0]
            elif len(results) > 1:
                return None, f"Plusieurs joueurs correspondent à « {query} ». Mentionne-le avec @ pour que je choisisse le bon."
            else:
                return None, f"Je ne trouve aucun joueur « {query} » sur ce Discord. Réessaie avec son pseudo Discord ou mentionne-le avec @."

        if member.bot:
            return None, "Je ne peux pas convoquer un bot, indique un joueur."
        if member.id == owner.id:
            return None, "Tu ne peux pas te désigner toi-même, indique le joueur impliqué."
        return member, None

    async def _summon(self, channel: discord.TextChannel, member: discord.Member, owner) -> bool:
        try:
            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                add_reactions=True,
            )
        except discord.Forbidden:
            await channel.send(
                f"⚠️ Je n'ai pas la permission d'ajouter {member.mention} à ce salon. Un admin doit le faire manuellement."
            )
            return False
        await channel.send(
            f"📢 {member.mention}, tu es convoqué dans ce ticket : {owner.mention} signale un incident te concernant."
        )
        return True

    # --- Déroulé du questionnaire --------------------------------------------
    async def run_flow(self, channel: discord.TextChannel, owner: discord.abc.User):
        data: dict = {}
        target = None
        current = START

        while current:
            step = STEPS[current]
            text = step["question"].format(user=owner.mention, target=target.mention if target else "")

            allowed = set()
            if step.get("who", "owner") in ("owner", "both"):
                allowed.add(owner.id)
            if step.get("who") in ("target", "both") and target:
                allowed.add(target.id)

            try:
                if step["type"] == "choice":
                    prompt = await channel.send(text)
                    for emoji in step["choices"]:
                        await prompt.add_reaction(emoji)

                    def check_reaction(p: discord.RawReactionActionEvent):
                        return (
                            p.message_id == prompt.id
                            and p.user_id in allowed
                            and str(p.emoji) in step["choices"]
                        )

                    payload = await self.bot.wait_for("raw_reaction_add", check=check_reaction, timeout=ANSWER_TIMEOUT)
                    value, current = step["choices"][str(payload.emoji)]
                    data[step["key"]] = value
                    continue

                # type "text" ou "player" : réponse écrite, avec plusieurs essais
                await channel.send(text)

                def check_message(m: discord.Message):
                    return m.channel.id == channel.id and m.author.id in allowed

                for _ in range(MAX_TRIES):
                    msg = await self.bot.wait_for("message", check=check_message, timeout=ANSWER_TIMEOUT)
                    content = msg.content.strip()

                    if step["type"] == "player":
                        member, error = await self._resolve_member(channel.guild, msg, owner)
                        if member is None:
                            await channel.send(error)
                            continue
                        if not await self._summon(channel, member, owner):
                            return
                        target = member
                        data["joueur"] = f"{member} ({member.id})"
                        break

                    validate = step.get("validate")
                    value = validate(content) if validate else (content or None)
                    if value is None:
                        await channel.send(step.get("error", "Réponse vide, réessaie."))
                        continue
                    data[step["key"]] = value
                    break
                else:
                    await channel.send("Je n'ai pas compris ta réponse. Un admin va prendre le relais.")
                    return

                current = step["next"]

            except asyncio.TimeoutError:
                await channel.send("⏱️ Pas de réponse, le questionnaire est interrompu.")
                return

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
