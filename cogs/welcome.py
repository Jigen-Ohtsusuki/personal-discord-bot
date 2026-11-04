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

    embed = discord.Embed(
        title="👋 WELCOME TO MISSJEY'S SERVER",
        description=description,
        color=0xAA88FF  # Soft aesthetic purple
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.set_footer(
        text="MissJey's Community 💜 • Official Welcome",
        icon_url=guild.icon.url if guild.icon else None
    )
    return embed


class WelcomeCog(commands.Cog, name="Welcome"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_message_id: Optional[int] = None

    async def cog_load(self):
        logger.info("Welcome cog loaded (Auto-Provisioning Welcome Guide).")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            channel = self.bot.get_channel(WELCOME_CHANNEL_ID) or discord.utils.get(guild.text_channels, name="welcome")
            if not channel:
                continue

            found_msg = None
            async for msg in channel.history(limit=15):
                if msg.author.id == self.bot.user.id and msg.embeds and "WELCOME TO MISSJEY'S SERVER" in (msg.embeds[0].title or ""):
                    found_msg = msg
                    self.welcome_message_id = msg.id
                    break

            embed = build_welcome_embed(guild)
            if found_msg:
                try:
                    await found_msg.edit(embed=embed)
                    logger.info(f"✨ Updated Welcome guide in #{channel.name}")
                except Exception as e:
                    logger.error(f"Error updating welcome guide: {e}")
            elif channel.permissions_for(guild.me).send_messages:
                try:
                    msg = await channel.send(embed=embed)
                    self.welcome_message_id = msg.id
                    logger.info(f"✨ Posted clean Welcome guide in #{channel.name} (ID: {msg.id})")
                except Exception as e:
                    logger.error(f"Error posting welcome guide: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
