import logging
import asyncio
from typing import Optional
import discord
from discord.ext import commands

logger = logging.getLogger("RulesCog")

RULES_CHANNEL_ID = 1559330881640996956  # #rules
MISSJEY_AVATAR_URL = "https://yt3.googleusercontent.com/O143rEtFVDnaNLx5zkY4QcYIXpKuUMIWkAN_m7ZJeuE5qCGhPMXJqWzHhiChGeJtWZq_lEFKkQ=s900-c-k-c0x00ffffff-no-rj"


def build_rules_embed() -> discord.Embed:
    description = (
        "Welcome to **MissJey's Server**! We're here to enjoy games, make friends, and build a friendly community. "
        "Please follow these rules to keep the server comfortable for everyone.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "### 01 — RESPECT EVERYONE\n"
        "Treat all members with respect. Harassment, bullying, discrimination, hate speech, threats, and personal attacks are not tolerated.\n\n"
        "### 02 — NO SPAM OR FLOODING\n"
        "Avoid message flooding, repeated messages, excessive mentions, emoji spam, and unnecessary tagging.\n\n"
        "### 03 — KEEP IT APPROPRIATE\n"
        "No NSFW, explicit, disturbing, or otherwise inappropriate content. Keep conversations suitable for a general community.\n\n"
        "### 04 — USE THE RIGHT CHANNELS\n"
        "Post messages, media, clips, and discussions in their respective channels. Keep conversations organised.\n\n"
        "### 05 — NO UNAUTHORIZED ADVERTISING\n"
        "Do not advertise servers, social accounts, products, or services without permission from the staff team.\n\n"
        "### 06 — RESPECT VOICE CHANNELS\n"
        "Don't shout, mic spam, play disruptive audio, or intentionally disturb others. Respect people already using a voice channel.\n\n"
        "### 07 — NO CHEATING OR MALICIOUS ACTIVITY\n"
        "Don't share malicious links, scams, account-stealing tools, or harmful files. Don't exploit or encourage harmful behaviour towards other members.\n\n"
        "### 08 — RESPECT PRIVACY\n"
        "Never share someone's personal information, private messages, or recordings without their permission.\n\n"
        "### 09 — FOLLOW DISCORD'S TERMS\n"
        "All members must follow Discord's Terms of Service and Community Guidelines.\n\n"
        "### 10 — LISTEN TO THE STAFF TEAM\n"
        "Follow reasonable moderator instructions. Do not evade punishments, impersonate staff, or interfere with moderation.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "### ⚖️ MODERATION & ENFORCEMENT\n\n"
        "Breaking the rules may result in:\n"
        "• Verbal warning\n"
        "• Message deletion\n"
        "• Timeout\n"
        "• Kick\n"
        "• Temporary or permanent ban\n\n"
        "*The severity of the action depends on the situation. Serious violations may result in immediate action without a prior warning.*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "### ✦ FINAL NOTE\n\n"
        "Be respectful, have fun, make friends, and help us keep MissJey's community welcoming.\n\n"
        "**By participating in this server, you agree to follow these rules.**\n\n"
        "*♡ — MissJey's Team*"
    )

    embed = discord.Embed(
        title="📜 SERVER RULES & GUIDELINES",
        description=description,
        color=0xAA88FF  # Soft aesthetic purple
    )

    embed.set_thumbnail(url=MISSJEY_AVATAR_URL)
    embed.set_footer(
        text="MissJey's Community 💜 • Server Rules & Guidelines",
        icon_url=MISSJEY_AVATAR_URL
    )
    return embed


class RulesCog(commands.Cog, name="Rules"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.rules_message_id: Optional[int] = None

    async def cog_load(self):
        logger.info("Rules cog loaded (Auto-Provisioning Rules & Guidelines).")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            channel = self.bot.get_channel(RULES_CHANNEL_ID) or discord.utils.get(guild.text_channels, name="rules")
            if not channel:
                continue

            found_msg = None
            async for msg in channel.history(limit=15):
                if msg.author.id == self.bot.user.id and msg.embeds and "SERVER RULES & GUIDELINES" in (msg.embeds[0].title or ""):
                    found_msg = msg
                    self.rules_message_id = msg.id
                    break

            embed = build_rules_embed()
            if found_msg:
                try:
                    await found_msg.edit(embed=embed)
                    logger.info(f"✨ Updated Rules & Guidelines in #{channel.name}")
                except Exception as e:
                    logger.error(f"Error updating rules: {e}")
            elif channel.permissions_for(guild.me).send_messages:
                try:
                    msg = await channel.send(embed=embed)
                    self.rules_message_id = msg.id
                    logger.info(f"✨ Posted clean Rules & Guidelines in #{channel.name} (ID: {msg.id})")
                except Exception as e:
                    logger.error(f"Error posting rules: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(RulesCog(bot))
