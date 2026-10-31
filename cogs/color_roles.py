import logging
import asyncio
from typing import Dict, Any, Optional
import discord
from discord.ext import commands

logger = logging.getLogger("ColorRoles")

# Color role definitions in JigenxOhtsusuki
COLOR_DEFINITIONS = [
    {"name": "Red", "id": 1559349426290430055, "emoji": "🔴", "hex": "#ff8890", "alt_keys": ["red", 458639479591403532]},
    {"name": "Purple", "id": 1559349427574022154, "emoji": "🟣", "hex": "#aa88ff", "alt_keys": ["purple", 458640035395272706]},
    {"name": "Green", "id": 1559349428207222944, "emoji": "🟢", "hex": "#88ff90", "alt_keys": ["green", 458640035491610657]},
    {"name": "Pink", "id": 1559349429243346964, "emoji": "🌸", "hex": "#fe88ff", "alt_keys": ["pink", 458640035667902466]},
    {"name": "Orange", "id": 1559349430623404103, "emoji": "🟠", "hex": "#ffa788", "alt_keys": ["orange", 458640035793731614]},
    {"name": "Yellow", "id": 1559349434020790272, "emoji": "🟡", "hex": "#f5ff88", "alt_keys": ["yellow", 458640035907108874]},
    {"name": "Blue", "id": 1559349434909855804, "emoji": "🔵", "hex": "#88eaff", "alt_keys": ["cyan", 458640036238458902]},
]

# Lookup map matching unicode emoji, emoji name, or custom emoji ID to role info
COLOR_LOOKUP: Dict[Any, Dict[str, Any]] = {}
ALL_COLOR_ROLE_IDS = set()

for item in COLOR_DEFINITIONS:
    ALL_COLOR_ROLE_IDS.add(item["id"])
    COLOR_LOOKUP[item["emoji"]] = item
    for alt in item["alt_keys"]:
        COLOR_LOOKUP[alt] = item

ROLES_CHANNEL_ID = 1559330910132764782  # #roles

class ColorRolesCog(commands.Cog, name="Color Roles"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.menu_message_id: Optional[int] = None

    async def cog_load(self):
        logger.info("Color Roles cog loaded.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Auto-provisions the color reaction menu in #roles if not already posted."""
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(ROLES_CHANNEL_ID)
        if not channel:
            return

        # Check if the menu is already posted to avoid duplicates
        async for msg in channel.history(limit=15):
            if msg.author.id == self.bot.user.id and msg.embeds and "Choose Your Name Color" in (msg.embeds[0].title or ""):
                self.menu_message_id = msg.id
                logger.info(f"Found existing Color Role Menu in #{channel.name} (Message ID: {msg.id})")
                return

        # Not posted yet -> post the clean menu
        await self.post_color_menu(channel)

    async def post_color_menu(self, channel: discord.TextChannel) -> discord.Message:
        """Posts the color picker embed with all emoji reactions."""
        embed = discord.Embed(
            title="🎨 Choose Your Name Color!",
            description=(
                "Personalize your appearance in the server! React with an emoji below to change your name color.\n\n"
                "**Available Colors:**\n"
                "🔴 **Red** (`#ff8890`)\n"
                "🟣 **Purple** (`#aa88ff`)\n"
                "🟢 **Green** (`#88ff90`)\n"
                "🌸 **Pink** (`#fe88ff`)\n"
                "🟠 **Orange** (`#ffa788`)\n"
                "🟡 **Yellow** (`#f5ff88`)\n"
                "🔵 **Blue** (`#88eaff`)\n\n"
                "✨ **Exclusive:** You can only have **one color at a time**. Reacting to a new color will automatically remove your old color and reaction!"
            ),
            color=0xAA88FF
        )
        embed.set_footer(text="Jey's Bot 💜 • Exclusive Color Role System")

        msg = await channel.send(embed=embed)
        self.menu_message_id = msg.id

        # React in order with unicode emojis
        for item in COLOR_DEFINITIONS:
            try:
                await msg.add_reaction(item["emoji"])
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.debug(f"Reaction add error: {e}")

        logger.info(f"Posted fresh Color Role Menu in #{channel.name} ({msg.id})")
        return msg

    def _get_color_info(self, emoji: discord.PartialEmoji) -> Optional[Dict[str, Any]]:
        """Resolves an emoji to its color definition."""
        if emoji.id and emoji.id in COLOR_LOOKUP:
            return COLOR_LOOKUP[emoji.id]
        if emoji.name and emoji.name in COLOR_LOOKUP:
            return COLOR_LOOKUP[emoji.name]
        return None

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        Exclusive Color Role Assigner:
        When a member reacts with a color emoji:
        1. Strips any previous color role
        2. Removes the member's previous reaction from the message
        3. Grants the new color role
        """
        if payload.user_id == self.bot.user.id:
            return

        target_info = self._get_color_info(payload.emoji)
        if not target_info:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = payload.member
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception:
                return

        if not member or member.bot:
            return

        target_role = guild.get_role(target_info["id"]) or discord.utils.get(guild.roles, name=target_info["name"])

        # Fetch message to clean up old user reactions
        channel = guild.get_channel(payload.channel_id)
        message = None
        if channel:
            try:
                message = await channel.fetch_message(payload.message_id)
            except Exception:
                pass

        # 1. Identify previous color roles to strip
        roles_to_remove = [r for r in member.roles if r.id in ALL_COLOR_ROLE_IDS and (target_role is None or r.id != target_role.id)]

        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Switched to new name color")
                logger.info(f"Removed previous color roles {[r.name for r in roles_to_remove]} from {member.display_name}")
            except discord.Forbidden:
                logger.warning(
                    f"PERMISSION ERROR: Bot cannot remove roles! Please move 'Jey's Bot 💜' role ABOVE color roles in Server Settings -> Roles and grant 'Manage Roles'."
                )
            except Exception as e:
                logger.error(f"Error removing roles from {member.display_name}: {e}")

        # 2. Remove member's previous color reactions from this message
        if message:
            for r in message.reactions:
                reaction_color = self._get_color_info(r.emoji)
                if reaction_color and reaction_color["id"] != target_info["id"]:
                    try:
                        await message.remove_reaction(r.emoji, member)
                    except discord.Forbidden:
                        logger.warning("PERMISSION ERROR: Bot needs 'Manage Messages' permission to remove old reactions.")
                    except Exception:
                        pass

        # 3. Add the new color role
        if target_role:
            try:
                await member.add_roles(target_role, reason=f"Selected {target_role.name} color")
                logger.info(f"Assigned color role '{target_role.name}' to {member.display_name}")
            except discord.Forbidden:
                logger.warning(
                    f"PERMISSION ERROR: Bot cannot assign '{target_role.name}'! Please move 'Jey's Bot 💜' role ABOVE '{target_role.name}' in Server Settings -> Roles and grant 'Manage Roles'."
                )
            except Exception as e:
                logger.error(f"Error adding role {target_role.name} to {member.display_name}: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """
        When member unreacts from their color:
        Removes the color role, reverting to default username color.
        """
        if payload.user_id == self.bot.user.id:
            return

        target_info = self._get_color_info(payload.emoji)
        if not target_info:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            return

        if not member or member.bot:
            return

        target_role = guild.get_role(target_info["id"]) or discord.utils.get(guild.roles, name=target_info["name"])

        if target_role and target_role in member.roles:
            try:
                await member.remove_roles(target_role, reason="Unreacted from color role")
                logger.info(f"Removed color role '{target_role.name}' from {member.display_name}")
            except discord.Forbidden:
                logger.warning(
                    f"PERMISSION ERROR: Bot cannot remove '{target_role.name}'! Check role hierarchy and 'Manage Roles' permission."
                )
            except Exception as e:
                logger.error(f"Error removing unreacted color role: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ColorRolesCog(bot))
