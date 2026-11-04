import logging
import asyncio
from typing import Optional
import discord
from discord.ext import commands

logger = logging.getLogger("WelcomeCog")

WELCOME_CHANNEL_ID = 1559330249421103120  # #welcome


def get_channel_ref(guild: discord.Guild, name: str, fallback_names: list = None) -> str:
    """Finds channel in guild and returns clickable <#id> mention, or #name fallback."""
    names_to_try = [name] + (fallback_names or [])
    for n in names_to_try:
        ch = discord.utils.get(guild.text_channels, name=n)
        if ch:
            return f"<#{ch.id}>"
    return f"**#{name}**"


def build_welcome_embed(guild: discord.Guild) -> discord.Embed:
    rules_ref = get_channel_ref(guild, "rules")
    roles_ref = get_channel_ref(guild, "roles")
    announcements_ref = get_channel_ref(guild, "announcements")
    intro_ref = get_channel_ref(guild, "introductions", ["intro", "introduction"])
    general_ref = get_channel_ref(guild, "general", ["general-chat", "chat"])
    clips_ref = get_channel_ref(guild, "clips-and-highlights", ["clips", "highlights"])
    media_ref = get_channel_ref(guild, "media", ["pictures", "memes"])

    description = (
        "Welcome! We're glad to have you here. 💜\n\n"
        "This is a place to meet new people, play games, share moments, and enjoy the community. "
        "Whether you're here to game, chat, or just hang out, there's a place for you.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "### ✦ GET STARTED\n\n"
        f"**01 — Read the rules**\n"
        f"Visit {rules_ref} and take a moment to understand our community guidelines.\n\n"
        f"**02 — Choose your roles**\n"
        f"Head over to {roles_ref} and select your games and notification preferences.\n\n"
        f"**03 — Introduce yourself**\n"
        f"Drop a quick introduction in {intro_ref} and get to know everyone.\n\n"
        f"**04 — Stay updated**\n"
        f"Check {announcements_ref} for important server news and updates.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "### ✦ EXPLORE THE SERVER\n\n"
        f"💬 {general_ref} — Everyday conversations.\n\n"
        f"🎮 {clips_ref} — Share your best gaming moments.\n\n"
        f"🖼️ {media_ref} — Share pictures, videos, and other media.\n\n"
        "🔊 **Voice Channels** — Find people to play with in duos, trios, and squads.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "### ✦ A FEW THINGS TO REMEMBER\n\n"
        "• Respect everyone.\n"
        "• Keep conversations in their appropriate channels.\n"
        "• No harassment, spam, or unnecessary drama.\n"
        "• Have fun and help keep the community welcoming.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**Enjoy your stay, and welcome to the community! ♡**\n\n"
        "*— MissJey's Team*"
    )

    MISSJEY_AVATAR_URL = "https://yt3.googleusercontent.com/O143rEtFVDnaNLx5zkY4QcYIXpKuUMIWkAN_m7ZJeuE5qCGhPMXJqWzHhiChGeJtWZq_lEFKkQ=s900-c-k-c0x00ffffff-no-rj"
    MISSJEY_BANNER_URL = "https://yt3.googleusercontent.com/AkXkJxzwHi4MMVOMMd-A3_sA_GV3EIuZmE3eeVncUa_k9zG4ZIiwsibMHfKN5PXeteYtp50V-Q=w1707"

    embed = discord.Embed(
        title="👋 WELCOME TO MISSJEY'S SERVER",
        description=description,
        color=0xAA88FF  # Soft aesthetic purple
    )

    embed.set_thumbnail(url=MISSJEY_AVATAR_URL)
    embed.set_image(url=MISSJEY_BANNER_URL)

    embed.set_footer(
        text="MissJey's Community 💜 • Official Welcome",
        icon_url=MISSJEY_AVATAR_URL
    )
    return embed


def build_socials_embed() -> discord.Embed:
    MISSJEY_AVATAR_URL = "https://yt3.googleusercontent.com/O143rEtFVDnaNLx5zkY4QcYIXpKuUMIWkAN_m7ZJeuE5qCGhPMXJqWzHhiChGeJtWZq_lEFKkQ=s900-c-k-c0x00ffffff-no-rj"
    description = (
        "Stay connected with MissJey across all platforms! Follow for live streams, highlights, stories & daily updates.\n\n"
        "📺 **YouTube** — [MissJey Gaming](https://www.youtube.com/@MissjeyGaming)\n"
        "> Streams, gaming highlights, and shorts!\n\n"
        "📸 **Instagram** — [@missjeyyyyy](https://www.instagram.com/missjeyyyyy/)\n"
        "> Stream updates, photos, and behind-the-scenes!"
    )
    embed = discord.Embed(
        title="🔗 MISSJEY'S OFFICIAL SOCIALS",
        description=description,
        color=0xE1306C  # Instagram / YouTube warm pink-red accent
    )
    embed.set_thumbnail(url=MISSJEY_AVATAR_URL)
    embed.set_footer(text="Official Socials • MissJey 💜", icon_url=MISSJEY_AVATAR_URL)
    return embed


def build_socials_view() -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.link, label="YouTube Channel", emoji="📺", url="https://www.youtube.com/@MissjeyGaming"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.link, label="Instagram", emoji="📸", url="https://www.instagram.com/missjeyyyyy/"))
    return view


class WelcomeCog(commands.Cog, name="Welcome"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_message_id: Optional[int] = None
        self.socials_message_id: Optional[int] = None

    async def cog_load(self):
        logger.info("Welcome cog loaded (Auto-Provisioning Welcome Guide & Socials).")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            channel = self.bot.get_channel(WELCOME_CHANNEL_ID) or discord.utils.get(guild.text_channels, name="welcome")
            if not channel:
                continue

            found_welcome_msg = None
            found_socials_msg = None

            async for msg in channel.history(limit=15):
                if msg.author.id == self.bot.user.id and msg.embeds:
                    title = msg.embeds[0].title or ""
                    if "WELCOME TO MISSJEY'S SERVER" in title:
                        found_welcome_msg = msg
                    elif "OFFICIAL SOCIALS" in title:
                        found_socials_msg = msg

            # 1. Main Welcome Message
            welcome_embed = build_welcome_embed(guild)
            if found_welcome_msg:
                try:
                    await found_welcome_msg.edit(embed=welcome_embed, view=None)
                    logger.info(f"✨ Updated Welcome guide in #{channel.name}")
                except Exception as e:
                    logger.error(f"Error updating welcome guide: {e}")
            elif channel.permissions_for(guild.me).send_messages:
                try:
                    msg = await channel.send(embed=welcome_embed)
                    logger.info(f"✨ Posted clean Welcome guide in #{channel.name} (ID: {msg.id})")
                except Exception as e:
                    logger.error(f"Error posting welcome guide: {e}")

            # 2. Separate Socials & Links Message
            socials_embed = build_socials_embed()
            socials_view = build_socials_view()
            if found_socials_msg:
                try:
                    await found_socials_msg.edit(embed=socials_embed, view=socials_view)
                    logger.info(f"✨ Updated Socials message in #{channel.name}")
                except Exception as e:
                    logger.error(f"Error updating socials message: {e}")
            elif channel.permissions_for(guild.me).send_messages:
                try:
                    msg = await channel.send(embed=socials_embed, view=socials_view)
                    logger.info(f"✨ Posted clean Socials message in #{channel.name} (ID: {msg.id})")
                except Exception as e:
                    logger.error(f"Error posting socials message: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
