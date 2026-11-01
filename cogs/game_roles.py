import logging
import asyncio
from typing import Dict, Any, Optional
import discord
from discord.ext import commands

logger = logging.getLogger("GameRoles")

GAME_DEFINITIONS = [
    {"name": "Minecraft", "id": 1559352088364978226, "emoji": "⛏️", "hex": "#11806a", "desc": "Sandbox & Survival"},
    {"name": "GTA", "id": 1559352200696823908, "emoji": "🚗", "hex": "#e67e22", "desc": "Grand Theft Auto & RP"},
    {"name": "fortnite", "id": 1559352276324192356, "emoji": "🪂", "hex": "#3498db", "desc": "Battle Royale & Creative"},
    {"name": "Roblox", "id": 1559352394624536626, "emoji": "🤖", "hex": "#607d8b", "desc": "Roblox Games & Minigames"},
    {"name": "Among Us", "id": 1559352458420162650, "emoji": "🚀", "hex": "#e91e63", "desc": "Crewmates & Impostors"},
    {"name": "Skribbl", "id": 1559352495417851974, "emoji": "✏️", "hex": "#f1c40f", "desc": "Drawing & Guessing"},
    {"name": "GeoGuessr", "id": 1559352540502691910, "emoji": "🌍", "hex": "#206694", "desc": "World Exploration & Geography"},
]

GAME_EMOJI_LOOKUP: Dict[str, Dict[str, Any]] = {g["emoji"]: g for g in GAME_DEFINITIONS}
ROLES_CHANNEL_ID = 1559330910132764782  # #roles


def build_game_menu_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎮 Choose Your Games!",
        description=(
            "Select the games you play to get notified for community matches and find teammates!\n\n"
            "React to claim a role. Remove your reaction anytime to remove the role.\n"
            "✨ **You can select multiple games!**\n\n"
            "⛏️ **Minecraft** • Sandbox & Survival\n"
            "🚗 **GTA** • Grand Theft Auto & RP\n"
            "🪂 **Fortnite** • Battle Royale & Creative\n"
            "🤖 **Roblox** • Roblox Minigames\n"
            "🚀 **Among Us** • Crewmates & Impostors\n"
            "✏️ **Skribbl** • Drawing & Fun\n"
            "🌍 **GeoGuessr** • World Geography\n"
        ),
        color=0xAA88FF
    )
    embed.set_footer(text="Jey's Bot 💜 • Community Game Roles")
    return embed


class GameRolesCog(commands.Cog, name="Game Roles"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.menu_message_id: Optional[int] = None

    async def cog_load(self):
        logger.info("Game Roles cog loaded (with Auto-Provisioning).")

    async def ensure_game_roles_exist(self, guild: discord.Guild):
        """Automatically creates the 7 game roles with custom colors if missing."""
        if not guild.me.guild_permissions.manage_roles:
            return

        existing_names = {r.name.lower(): r for r in guild.roles}
        for g in GAME_DEFINITIONS:
            name_lower = g["name"].lower()
            if name_lower not in existing_names:
                try:
                    hex_int = int(g["hex"].lstrip("#"), 16)
                    new_role = await guild.create_role(
                        name=g["name"],
                        color=discord.Color(hex_int),
                        mentionable=True,
                        reason="Auto-created by Jey's Bot 💜 for game matchmaking"
                    )
                    logger.info(f"🎮 Auto-created game role '{new_role.name}' ({g['hex']}) in '{guild.name}'")
                except Exception as e:
                    logger.error(f"Failed to auto-create game role '{g['name']}': {e}")

    async def _resolve_game_role(self, guild: discord.Guild, game_info: Dict[str, Any]) -> Optional[discord.Role]:
        """Finds game role by ID or by name, auto-creating it if missing."""
        role = guild.get_role(game_info["id"])
        if not role:
            role = discord.utils.get(guild.roles, name=game_info["name"])
        if not role:
            role = next((r for r in guild.roles if r.name.lower() == game_info["name"].lower()), None)

        if not role and guild.me.guild_permissions.manage_roles:
            try:
                hex_int = int(game_info["hex"].lstrip("#"), 16)
                role = await guild.create_role(
                    name=game_info["name"],
                    color=discord.Color(hex_int),
                    mentionable=True,
                    reason="Auto-created by Jey's Bot 💜 on reaction"
                )
                logger.info(f"🎮 Auto-created game role '{role.name}' in '{guild.name}'")
            except Exception as e:
                logger.error(f"Error creating game role on the fly: {e}")
        return role

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Auto-provisions game roles and menu when joining a new server."""
        await self.ensure_game_roles_exist(guild)
        channel = self.bot.get_channel(ROLES_CHANNEL_ID) or discord.utils.get(guild.text_channels, name="roles")
        if channel:
            await self.post_game_menu(channel)

    @commands.Cog.listener()
    async def on_ready(self):
        """Auto-provisions or discovers the game role menu in #roles."""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            await self.ensure_game_roles_exist(guild)

            channel = self.bot.get_channel(ROLES_CHANNEL_ID) or discord.utils.get(guild.text_channels, name="roles")
            if not channel:
                continue

            found = False
            async for msg in channel.history(limit=15):
                if msg.author.id == self.bot.user.id and msg.embeds and "Choose Your Games" in (msg.embeds[0].title or ""):
                    self.menu_message_id = msg.id
                    found = True
                    logger.info(f"Game Role Menu active in '{guild.name}' #{channel.name} (ID: {msg.id})")
                    break

            if not found and channel.permissions_for(guild.me).send_messages:
                try:
                    await self.post_game_menu(channel)
                except Exception as e:
                    logger.error(f"Error posting game menu: {e}")

    async def post_game_menu(self, channel: discord.TextChannel) -> discord.Message:
        """Posts the clean game roles menu with all emoji reactions."""
        embed = build_game_menu_embed()
        msg = await channel.send(embed=embed)
        self.menu_message_id = msg.id

        for g in GAME_DEFINITIONS:
            try:
                await msg.add_reaction(g["emoji"])
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.debug(f"Game reaction error: {e}")

        logger.info(f"Posted fresh Game Role Menu in #{channel.name} ({msg.id})")
        return msg

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Adds game role when user reacts."""
        if payload.user_id == self.bot.user.id:
            return

        emoji_str = str(payload.emoji.name)
        game_info = GAME_EMOJI_LOOKUP.get(emoji_str)
        if not game_info:
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

        target_role = await self._resolve_game_role(guild, game_info)
        if target_role and target_role not in member.roles:
            try:
                await member.add_roles(target_role, reason=f"Selected {game_info['name']} game role")
                logger.info(f"🎮 Assigned game role '{target_role.name}' to {member.display_name}")
            except discord.Forbidden:
                logger.warning(f"PERMISSION ERROR: Cannot assign '{target_role.name}'. Check bot role hierarchy.")
            except Exception as e:
                logger.error(f"Error adding game role {target_role.name}: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Removes game role when user unreacts."""
        if payload.user_id == self.bot.user.id:
            return

        emoji_str = str(payload.emoji.name)
        game_info = GAME_EMOJI_LOOKUP.get(emoji_str)
        if not game_info:
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

        target_role = await self._resolve_game_role(guild, game_info)
        if target_role and target_role in member.roles:
            try:
                await member.remove_roles(target_role, reason=f"Unselected {game_info['name']} game role")
                logger.info(f"🎮 Removed game role '{target_role.name}' from {member.display_name}")
            except discord.Forbidden:
                logger.warning(f"PERMISSION ERROR: Cannot remove '{target_role.name}'. Check bot role hierarchy.")
            except Exception as e:
                logger.error(f"Error removing game role {target_role.name}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(GameRolesCog(bot))
