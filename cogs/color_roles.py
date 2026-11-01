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
COLOR_NAMES = {c["name"].lower(): c for c in COLOR_DEFINITIONS}
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
        logger.info("Color Roles cog loaded (Exclusive Reaction Engine with Auto-Provisioning).")

    async def ensure_color_roles_exist(self, guild: discord.Guild):
        """Automatically creates the 7 color roles with their custom hex colors if missing."""
        if not guild.me.guild_permissions.manage_roles:
            return

        existing_names = {r.name.lower(): r for r in guild.roles}
        for c in COLOR_DEFINITIONS:
            name_lower = c["name"].lower()
            if name_lower not in existing_names:
                try:
                    hex_int = int(c["hex"].lstrip("#"), 16)
                    new_role = await guild.create_role(
                        name=c["name"],
                        color=discord.Color(hex_int),
                        mentionable=False,
                        reason="Auto-created by Jey's Bot 💜 for community color customization"
                    )
                    logger.info(f"✨ Auto-created color role '{new_role.name}' ({c['hex']}) in '{guild.name}'")
                except Exception as e:
                    logger.error(f"Failed to auto-create color role '{c['name']}': {e}")

    async def organize_role_hierarchy(self, guild: discord.Guild):
        """Ensures Color Roles are placed strictly ABOVE Game Roles so name colors take priority."""
        if not guild.me.guild_permissions.manage_roles:
            return

        color_names = ['Red', 'Purple', 'Green', 'Pink', 'Orange', 'Yellow', 'Blue']
        game_names = ['Minecraft', 'GTA', 'fortnite', 'Roblox', 'Among Us', 'Skribbl', 'GeoGuessr']

        roles = await guild.fetch_roles()
        role_map = {r.name.lower(): r for r in roles}

        color_roles = [role_map[n.lower()] for n in color_names if n.lower() in role_map]
        game_roles = [role_map[n.lower()] for n in game_names if n.lower() in role_map]

        if not color_roles or not game_roles:
            return

        min_color_pos = min(r.position for r in color_roles)
        max_game_pos = max(r.position for r in game_roles)

        if min_color_pos > max_game_pos:
            return  # Already perfectly sorted

        positions = {}
        current_pos = 1
        for name in reversed(game_names):
            r = role_map.get(name.lower())
            if r:
                positions[r] = current_pos
                current_pos += 1

        for name in reversed(color_names):
            r = role_map.get(name.lower())
            if r:
                positions[r] = current_pos
                current_pos += 1

        try:
            await guild.edit_role_positions(positions=positions)
            logger.info(f"✨ Successfully organized role hierarchy (Colors above Games) in '{guild.name}'")
        except Exception as e:
            logger.debug(f"Hierarchy organize notice: {e}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Auto-provisions color roles and menu when joining a new server."""
        await self.ensure_color_roles_exist(guild)
        await self.organize_role_hierarchy(guild)
        channel = await self.get_or_create_roles_channel(guild)
        if channel:
            await self.post_color_menu(channel)

    async def get_or_create_roles_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Finds #roles or creates it automatically if permissions allow."""
        channel = self.bot.get_channel(ROLES_CHANNEL_ID) or discord.utils.get(guild.text_channels, name="roles")
        if not channel and guild.me.guild_permissions.manage_channels:
            try:
                channel = await guild.create_text_channel(
                    name="roles",
                    topic="Personalize your name color and game roles! 💜",
                    reason="Auto-created by Jey's Bot 💜 for role assignment"
                )
                logger.info(f"✨ Auto-created #roles channel in '{guild.name}'")
            except Exception as e:
                logger.error(f"Error creating #roles channel: {e}")
        return channel

    @commands.Cog.listener()
    async def on_ready(self):
        """Discovers or auto-provisions menu in #roles across any connected server."""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            await self.ensure_color_roles_exist(guild)
            await self.organize_role_hierarchy(guild)

            channel = await self.get_or_create_roles_channel(guild)
            if not channel:
                continue

            found = False
            async for msg in channel.history(limit=15):
                if msg.author.id == self.bot.user.id and msg.embeds and "Choose Your Name Color" in (msg.embeds[0].title or ""):
                    self.menu_message_id = msg.id
                    found = True
                    logger.info(f"Color Role Reaction Menu active in '{guild.name}' #{channel.name} (ID: {msg.id})")
                    break

            if not found and channel.permissions_for(guild.me).send_messages:
                await self.post_color_menu(channel)

    async def post_color_menu(self, channel: discord.TextChannel) -> discord.Message:
        """Posts clean color picker embed in the target channel."""
        embed = discord.Embed(
            title="🎨 Choose Your Name Color!",
            description=(
                "Personalize your appearance in the server! React with an emoji below to change your username color.\n\n"
                "**Available Colors:**\n"
                "🔴 **Red** (`#ff8890`)\n"
                "🟣 **Purple** (`#aa88ff`)\n"
                "🟢 **Green** (`#88ff90`)\n"
                "🌸 **Pink** (`#fe88ff`)\n"
                "🟠 **Orange** (`#ffa788`)\n"
                "🟡 **Yellow** (`#f5ff88`)\n"
                "🔵 **Blue** (`#88eaff`)\n\n"
                "✨ **Exclusive:** You can only have **one color at a time**. Reacting to a new color will automatically remove your old reaction and switch your color!"
            ),
            color=0xAA88FF
        )
        embed.set_footer(text="Jey's Bot 💜 • Exclusive Color Role Engine")
        msg = await channel.send(embed=embed)
        self.menu_message_id = msg.id

        for c in COLOR_DEFINITIONS:
            try:
                await msg.add_reaction(c["emoji"])
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.debug(f"Reaction error: {e}")
        return msg

    async def _resolve_target_role(self, guild: discord.Guild, target_info: Dict[str, Any]) -> Optional[discord.Role]:
        """Finds role by ID or name, creating it dynamically if missing."""
        role = guild.get_role(target_info["id"])
        if not role:
            role = discord.utils.get(guild.roles, name=target_info["name"])
        if not role and guild.me.guild_permissions.manage_roles:
            try:
                hex_int = int(target_info["hex"].lstrip("#"), 16)
                role = await guild.create_role(
                    name=target_info["name"],
                    color=discord.Color(hex_int),
                    mentionable=False,
                    reason="Auto-created by Jey's Bot 💜 on reaction"
                )
                logger.info(f"✨ Auto-created color role '{role.name}' in {guild.name}")
            except Exception as e:
                logger.error(f"Error creating role on the fly: {e}")
        return role

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
            target_role = await self._resolve_target_role(guild, target_info)
            current_roles = list(member.roles)

            # Identify old color roles and emojis to strip (by ID or by name)
            roles_being_removed = [
                r for r in current_roles
                if (r.id in ALL_COLOR_ROLE_IDS or r.name.lower() in COLOR_NAMES)
                and (target_role is None or r.id != target_role.id)
            ]
            old_emojis_to_remove = []
            for r in roles_being_removed:
                if r.id in ROLE_ID_TO_UNICODE:
                    old_emojis_to_remove.append(ROLE_ID_TO_UNICODE[r.id])
                elif r.name.lower() in COLOR_NAMES:
                    old_emojis_to_remove.append(COLOR_NAMES[r.name.lower()]["emoji"])

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
            roles_to_keep = [r for r in current_roles if r not in roles_being_removed]
            final_roles = roles_to_keep + ([target_role] if target_role and target_role not in roles_to_keep else [])

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

        target_role = await self._resolve_target_role(guild, target_info)
        if target_role and target_role in member.roles:
            try:
                await member.remove_roles(target_role, reason="Unreacted color role")
                logger.info(f"⚪ Reverted color for {member.display_name}")
            except Exception as e:
                logger.error(f"Error removing role on unreact: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ColorRolesCog(bot))
