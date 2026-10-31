import logging
import asyncio
from typing import Dict, Any, Optional
import discord
from discord.ext import commands
from discord.message import convert_emoji_reaction

logger = logging.getLogger("ColorRoles")

COLOR_DEFINITIONS = [
    {"name": "Red", "id": 1559349426290430055, "emoji": "🔴", "hex": "#ff8890"},
    {"name": "Purple", "id": 1559349427574022154, "emoji": "🟣", "hex": "#aa88ff"},
    {"name": "Green", "id": 1559349428207222944, "emoji": "🟢", "hex": "#88ff90"},
    {"name": "Pink", "id": 1559349429243346964, "emoji": "🌸", "hex": "#fe88ff"},
    {"name": "Orange", "id": 1559349430623404103, "emoji": "🟠", "hex": "#ffa788"},
    {"name": "Yellow", "id": 1559349434020790272, "emoji": "🟡", "hex": "#f5ff88"},
    {"name": "Blue", "id": 1559349434909855804, "emoji": "🔵", "hex": "#88eaff"},
]

ALL_COLOR_ROLE_IDS = {c["id"] for c in COLOR_DEFINITIONS}
ROLE_ID_TO_UNICODE = {c["id"]: c["emoji"] for c in COLOR_DEFINITIONS}
COLOR_LOOKUP: Dict[str, Dict[str, Any]] = {c["emoji"]: c for c in COLOR_DEFINITIONS}
ROLES_CHANNEL_ID = 1559330910132764782  # #roles


class ColorRolesCog(commands.Cog, name="Color Roles"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.menu_message_id: Optional[int] = None
        self._user_locks: Dict[int, asyncio.Lock] = {}

    def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]

    async def cog_load(self):
        logger.info("Color Roles cog loaded (Exclusive Reaction Engine).")

    @commands.Cog.listener()
    async def on_ready(self):
        """Discovers existing menu in #roles."""
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(ROLES_CHANNEL_ID)
        if not channel:
            return

        async for msg in channel.history(limit=15):
            if msg.author.id == self.bot.user.id and msg.embeds and "Choose Your Name Color" in (msg.embeds[0].title or ""):
                self.menu_message_id = msg.id
                logger.info(f"Color Role Reaction Menu active on message ID: {msg.id}")
                return

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        Instant Reaction Handler:
        - Fires instant HTTP removal for the old reaction (removes blue highlight immediately)
        - Updates roles atomically via member.edit
        """
        if payload.user_id == self.bot.user.id:
            return

        emoji_str = str(payload.emoji.name)
        target_info = COLOR_LOOKUP.get(emoji_str)
        if not target_info:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = payload.member or guild.get_member(payload.user_id)
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception:
                return

        if not member or member.bot:
            return

        async with self._get_user_lock(member.id):
            target_role = guild.get_role(target_info["id"])
            current_roles = list(member.roles)

            # Identify old color roles and emojis to strip
            roles_being_removed = [r for r in current_roles if r.id in ALL_COLOR_ROLE_IDS and (target_role is None or r.id != target_role.id)]
            old_emojis_to_remove = [ROLE_ID_TO_UNICODE[r.id] for r in roles_being_removed if r.id in ROLE_ID_TO_UNICODE]

            # 1. Instantly remove previous reaction to clear old blue highlight
            for old_emoji in old_emojis_to_remove:
                if old_emoji != target_info["emoji"]:
                    asyncio.create_task(
                        self.bot.http.remove_reaction(
                            payload.channel_id,
                            payload.message_id,
                            convert_emoji_reaction(old_emoji),
                            member.id
                        )
                    )

            # 2. Update role in one atomic call
            roles_to_keep = [r for r in current_roles if r.id not in ALL_COLOR_ROLE_IDS]
            final_roles = roles_to_keep + ([target_role] if target_role else [])

            if set(final_roles) != set(current_roles):
                try:
                    await member.edit(roles=final_roles, reason=f"Exclusive Color: {target_info['name']}")
                    logger.info(f"🎨 Set color '{target_info['name']}' for {member.display_name}")
                except discord.Forbidden:
                    logger.warning("PERMISSION ERROR: Check role hierarchy / Manage Roles permission.")
                except Exception as e:
                    logger.error(f"Error updating roles: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Revert to default color when unreacting."""
        if payload.user_id == self.bot.user.id:
            return

        emoji_str = str(payload.emoji.name)
        target_info = COLOR_LOOKUP.get(emoji_str)
        if not target_info:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception:
                return

        if not member or member.bot:
            return

        target_role = guild.get_role(target_info["id"])
        if target_role and target_role in member.roles:
            try:
                await member.remove_roles(target_role, reason="Unreacted color role")
                logger.info(f"⚪ Reverted color for {member.display_name}")
            except Exception as e:
                logger.error(f"Error removing role on unreact: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ColorRolesCog(bot))
