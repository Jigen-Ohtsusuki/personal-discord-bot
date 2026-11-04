import logging
import asyncio
from typing import Dict, Any, Optional
import discord
from discord.ext import commands
from discord.message import convert_emoji_reaction

logger = logging.getLogger("ColorRoles")

COLOR_DEFINITIONS = [
    {"name": "Red", "emoji": "🔴", "hex": "#ff8890"},
    {"name": "Purple", "emoji": "🟣", "hex": "#aa88ff"},
    {"name": "Green", "emoji": "🟢", "hex": "#88ff90"},
    {"name": "Pink", "emoji": "🌸", "hex": "#fe88ff"},
    {"name": "Orange", "emoji": "🟠", "hex": "#ffa788"},
    {"name": "Yellow", "emoji": "🟡", "hex": "#f5ff88"},
    {"name": "Blue", "emoji": "🔵", "hex": "#88eaff"},
    {"name": "Cyan", "emoji": "🩵", "hex": "#00f5d4"},
    {"name": "Brown", "emoji": "🟤", "hex": "#b07a56"},
    {"name": "White", "emoji": "⚪", "hex": "#ffffff"},
    {"name": "Black", "emoji": "⚫", "hex": "#2b2d31"},
    {"name": "Coral", "emoji": "🔺", "hex": "#ff4757"},
    {"name": "Rose", "emoji": "🔻", "hex": "#ff6b81"},
    {"name": "Amber", "emoji": "🔸", "hex": "#ffa502"},
    {"name": "Aqua", "emoji": "🔹", "hex": "#00d2d3"},
    {"name": "Slate", "emoji": "🔘", "hex": "#70a1ff"},
    {"name": "Cobalt", "emoji": "🔷", "hex": "#1e90ff"},
]

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
        """Ensures Color Roles are placed strictly ABOVE Game & Notification Roles so name colors take priority."""
        if not guild.me.guild_permissions.manage_roles:
            return

        color_names = [c["name"] for c in COLOR_DEFINITIONS]
        game_names = ['Minecraft', 'GTA', 'fortnite', 'Roblox', 'Among Us', 'Skribbl', 'GeoGuessr']
        notif_names = ['Stream Alert', 'Video Alert', 'DC Alert', 'Event Alert', 'Giveaway Alert']

        roles = await guild.fetch_roles()
        role_map = {r.name.lower(): r for r in roles}

        color_roles = [role_map[n.lower()] for n in color_names if n.lower() in role_map]
        other_roles = [role_map[n.lower()] for n in (game_names + notif_names) if n.lower() in role_map]

        if not color_roles or not other_roles:
            return

        min_color_pos = min(r.position for r in color_roles)
        max_other_pos = max(r.position for r in other_roles)

        if min_color_pos > max_other_pos:
            return  # Already perfectly sorted

        positions = {}
        current_pos = 1
        for name in reversed(game_names):
            r = role_map.get(name.lower())
            if r:
                positions[r] = current_pos
                current_pos += 1

        for name in reversed(notif_names):
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
            logger.info(f"✨ Successfully organized role hierarchy (Colors above Notifications & Games) in '{guild.name}'")
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

    def build_color_embed(self) -> discord.Embed:
        desc_lines = [
            "Personalize your appearance in the server! React with an emoji below to change your username color.\n\n"
            "**Available Colors:**"
        ]
        for c in COLOR_DEFINITIONS:
            desc_lines.append(f"{c['emoji']} **{c['name']}** (`{c['hex']}`)")
        desc_lines.append("\n✨ **Exclusive:** You can only have **one color at a time**. Reacting to a new color will automatically remove your old reaction and switch your color!")

        embed = discord.Embed(
            title="🎨 Choose Your Name Color!",
            description="\n".join(desc_lines),
            color=0xAA88FF
        )
        embed.set_footer(text="Jey's Bot 💜 • Exclusive Color Role Engine")
        return embed

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

            found_msg = None
            async for msg in channel.history(limit=15):
                if msg.author.id == self.bot.user.id and msg.embeds and "Choose Your Name Color" in (msg.embeds[0].title or ""):
                    found_msg = msg
                    self.menu_message_id = msg.id
                    logger.info(f"Color Role Reaction Menu found in '{guild.name}' #{channel.name} (ID: {msg.id})")
                    break

            if found_msg:
                # Update existing message with updated embed and missing reactions
                try:
                    await found_msg.edit(embed=self.build_color_embed())
                    existing_reactions = {str(r.emoji) for r in found_msg.reactions}
                    for c in COLOR_DEFINITIONS:
                        if c["emoji"] not in existing_reactions:
                            await found_msg.add_reaction(c["emoji"])
                            await asyncio.sleep(0.3)
                    logger.info(f"✨ Successfully updated color menu and reactions in '{guild.name}'")
                    await self.sync_offline_reactions(guild, found_msg)
                except Exception as e:
                    logger.error(f"Error updating existing color menu: {e}")
            elif channel.permissions_for(guild.me).send_messages:
                await self.post_color_menu(channel)

    async def sync_offline_reactions(self, guild: discord.Guild, message: discord.Message):
        """Reads all reactions on the color menu and assigns missing roles to members who reacted while bot was offline."""
        logger.info(f"🔄 Syncing offline color reactions in '{guild.name}'...")
        try:
            fresh_msg = await message.channel.fetch_message(message.id)
            user_target_colors: Dict[int, Dict[str, Any]] = {}
            user_all_emojis: Dict[int, list] = {}

            for reaction in fresh_msg.reactions:
                emoji_str = str(reaction.emoji)
                target_info = COLOR_LOOKUP.get(emoji_str)
                if not target_info:
                    continue

                async for user in reaction.users():
                    if user.id == self.bot.user.id or user.bot:
                        continue
                    user_target_colors[user.id] = target_info
                    user_all_emojis.setdefault(user.id, []).append(emoji_str)

            for user_id, target_info in user_target_colors.items():
                member = guild.get_member(user_id)
                if not member:
                    try:
                        member = await guild.fetch_member(user_id)
                    except Exception:
                        continue
                if not member or member.bot:
                    continue

                target_role = await self._resolve_target_role(guild, target_info)
                current_roles = list(member.roles)

                roles_being_removed = [
                    r for r in current_roles
                    if r.name.lower() in COLOR_NAMES and (target_role is None or r.id != target_role.id)
                ]

                # Clean up excess emoji reactions if user reacted to multiple
                emojis_user_has = user_all_emojis.get(user_id, [])
                if len(emojis_user_has) > 1:
                    for old_emoji in emojis_user_has:
                        if old_emoji != target_info["emoji"]:
                            try:
                                await self.bot.http.remove_reaction(
                                    message.channel.id,
                                    message.id,
                                    convert_emoji_reaction(old_emoji),
                                    user_id
                                )
                            except Exception:
                                pass

                roles_to_keep = [r for r in current_roles if r not in roles_being_removed]
                final_roles = roles_to_keep + ([target_role] if target_role and target_role not in roles_to_keep else [])

                if set(final_roles) != set(current_roles):
                    try:
                        await member.edit(roles=final_roles, reason=f"Offline Sync: {target_info['name']}")
                        logger.info(f"🎨 [Offline Sync] Set color '{target_info['name']}' for {member.display_name}")
                    except Exception as e:
                        logger.error(f"Error syncing color role for {member.display_name}: {e}")
        except Exception as e:
            logger.error(f"Error during offline reaction sync: {e}")

    async def post_color_menu(self, channel: discord.TextChannel) -> discord.Message:
        """Posts clean color picker embed in the target channel."""
        embed = self.build_color_embed()
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
        """Finds role by name, creating it dynamically if missing."""
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

        # STRICT MESSAGE GATE: Only process reactions on the Color Menu message!
        if not self.menu_message_id or payload.message_id != self.menu_message_id:
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

            # Identify old color roles and emojis to strip (by name)
            roles_being_removed = [
                r for r in current_roles
                if r.name.lower() in COLOR_NAMES
                and (target_role is None or r.id != target_role.id)
            ]
            old_emojis_to_remove = [
                COLOR_NAMES[r.name.lower()]["emoji"]
                for r in roles_being_removed
                if r.name.lower() in COLOR_NAMES
            ]

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

        # STRICT MESSAGE GATE: Only process reactions on the Color Menu message!
        if not self.menu_message_id or payload.message_id != self.menu_message_id:
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
