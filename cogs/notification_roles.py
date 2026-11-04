import logging
import asyncio
from typing import Dict, Any, Optional
import discord
from discord.ext import commands

logger = logging.getLogger("NotificationRoles")

NOTIFICATION_DEFINITIONS = [
    {"name": "Stream Alerts", "emoji": "🔴", "desc": "Live streams & scheduled stream reminders"},
    {"name": "Video Alerts", "emoji": "🟠", "desc": "New YouTube videos & Shorts uploads"},
    {"name": "DC Alerts", "emoji": "📢", "desc": "Discord server announcements & news"},
    {"name": "Event Alerts", "emoji": "🟢", "desc": "Community game nights & tournaments"},
    {"name": "Giveaway Alerts", "emoji": "🟣", "desc": "Giveaways, drops & special rewards"},
]

NOTIFICATION_EMOJI_LOOKUP: Dict[str, Dict[str, Any]] = {n["emoji"]: n for n in NOTIFICATION_DEFINITIONS}
ROLES_CHANNEL_ID = 1559330910132764782  # #roles


def build_notification_menu_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🔔 Choose Your Notification Alerts!",
        description=(
            "Never miss a moment! React below to get pinged for the alerts you care about.\n\n"
            "🔴 **Stream Alerts** • Get pinged when MissJey goes live or schedules a stream\n"
            "🟠 **Video Alerts** • New YouTube videos and Shorts drops\n"
            "📢 **DC Alerts** • Discord server announcements & community updates\n"
            "🟢 **Event Alerts** • Community game nights, lobbies & tournaments\n"
            "🟣 **Giveaway Alerts** • Exclusive giveaways, nitro drops & rewards\n\n"
            "✨ *React to claim an alert role. Remove your reaction anytime to opt out.*"
        ),
        color=0xFF7700
    )
    embed.set_footer(text="Jey's Bot 💜 • Community Alert Roles")
    return embed


class NotificationRolesCog(commands.Cog, name="Notification Roles"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.menu_message_id: Optional[int] = None

    async def cog_load(self):
        logger.info("Notification Roles cog loaded (with Auto-Provisioning).")

    async def ensure_notification_roles_exist(self, guild: discord.Guild):
        """Automatically creates the 5 notification roles (colorless, mentionable) if missing."""
        if not guild.me.guild_permissions.manage_roles:
            return

        existing_names = {r.name.lower(): r for r in guild.roles}
        for n in NOTIFICATION_DEFINITIONS:
            name_lower = n["name"].lower()
            if name_lower not in existing_names:
                try:
                    new_role = await guild.create_role(
                        name=n["name"],
                        color=discord.Color.default(),
                        mentionable=True,
                        reason="Auto-created by Jey's Bot 💜 for community notifications (colorless)"
                    )
                    logger.info(f"🔔 Auto-created notification role '{new_role.name}' in '{guild.name}'")
                except Exception as e:
                    logger.error(f"Failed to auto-create notification role '{n['name']}': {e}")

    async def _resolve_notification_role(self, guild: discord.Guild, notif_info: Dict[str, Any]) -> Optional[discord.Role]:
        """Finds notification role by name, auto-creating it if missing."""
        role = discord.utils.get(guild.roles, name=notif_info["name"])
        if not role:
            role = next((r for r in guild.roles if r.name.lower() == notif_info["name"].lower()), None)

        if not role and guild.me.guild_permissions.manage_roles:
            try:
                role = await guild.create_role(
                    name=notif_info["name"],
                    color=discord.Color.default(),
                    mentionable=True,
                    reason="Auto-created by Jey's Bot 💜 on reaction (colorless)"
                )
                logger.info(f"🔔 Auto-created notification role '{role.name}' in '{guild.name}'")
            except Exception as e:
                logger.error(f"Error creating notification role on the fly: {e}")
        return role

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Auto-provisions notification roles and menu when joining a new server."""
        await self.ensure_notification_roles_exist(guild)
        channel = self.bot.get_channel(ROLES_CHANNEL_ID) or discord.utils.get(guild.text_channels, name="roles")
        if channel:
            await self.post_notification_menu(channel)

    @commands.Cog.listener()
    async def on_ready(self):
        """Auto-provisions or discovers the notification role menu in #roles."""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            await self.ensure_notification_roles_exist(guild)

            channel = self.bot.get_channel(ROLES_CHANNEL_ID) or discord.utils.get(guild.text_channels, name="roles")
            if not channel:
                continue

            found_msg = None
            async for msg in channel.history(limit=25):
                if msg.author.id == self.bot.user.id and msg.embeds and "Choose Your Notification Alerts" in (msg.embeds[0].title or ""):
                    found_msg = msg
                    self.menu_message_id = msg.id
                    logger.info(f"Notification Role Menu active in '{guild.name}' #{channel.name} (ID: {msg.id})")
                    break

            if found_msg:
                try:
                    await found_msg.edit(embed=build_notification_menu_embed())
                    existing_reactions = {str(r.emoji) for r in found_msg.reactions}
                    for n in NOTIFICATION_DEFINITIONS:
                        if n["emoji"] not in existing_reactions:
                            await found_msg.add_reaction(n["emoji"])
                            await asyncio.sleep(0.3)
                    await self.sync_offline_notification_reactions(guild, found_msg)
                except Exception as e:
                    logger.error(f"Error updating existing notification menu: {e}")
            elif channel.permissions_for(guild.me).send_messages:
                try:
                    await self.post_notification_menu(channel)
                except Exception as e:
                    logger.error(f"Error posting notification menu: {e}")

    async def post_notification_menu(self, channel: discord.TextChannel) -> discord.Message:
        """Posts the clean notification roles menu with all emoji reactions."""
        embed = build_notification_menu_embed()
        msg = await channel.send(embed=embed)
        self.menu_message_id = msg.id

        for n in NOTIFICATION_DEFINITIONS:
            try:
                await msg.add_reaction(n["emoji"])
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.debug(f"Notification reaction error: {e}")

        logger.info(f"Posted fresh Notification Role Menu in #{channel.name} ({msg.id})")
        return msg

    async def sync_offline_notification_reactions(self, guild: discord.Guild, message: discord.Message):
        """Scans reactions on the notification roles menu and gives missing roles to members who reacted while bot was offline."""
        logger.info(f"🔄 Syncing offline notification reactions in '{guild.name}'...")
        try:
            fresh_msg = await message.channel.fetch_message(message.id)
            for reaction in fresh_msg.reactions:
                emoji_str = str(reaction.emoji)
                notif_info = NOTIFICATION_EMOJI_LOOKUP.get(emoji_str)
                if not notif_info:
                    continue

                target_role = await self._resolve_notification_role(guild, notif_info)
                if not target_role:
                    continue

                async for user in reaction.users():
                    if user.id == self.bot.user.id or user.bot:
                        continue
                    member = guild.get_member(user.id)
                    if not member:
                        try:
                            member = await guild.fetch_member(user.id)
                        except Exception:
                            continue
                    if not member or member.bot:
                        continue

                    if target_role not in member.roles:
                        try:
                            await member.add_roles(target_role, reason=f"Offline Sync: {notif_info['name']}")
                            logger.info(f"🔔 [Offline Sync] Assigned notification role '{target_role.name}' to {member.display_name}")
                        except Exception as e:
                            logger.error(f"Error syncing notification role {target_role.name} for {member.display_name}: {e}")
        except Exception as e:
            logger.error(f"Error during offline notification reaction sync: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Adds notification role when user reacts."""
        if payload.user_id == self.bot.user.id:
            return

        emoji_str = str(payload.emoji.name)
        notif_info = NOTIFICATION_EMOJI_LOOKUP.get(emoji_str)
        if not notif_info:
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

        target_role = await self._resolve_notification_role(guild, notif_info)
        if target_role and target_role not in member.roles:
            try:
                await member.add_roles(target_role, reason=f"Selected {notif_info['name']} alert role")
                logger.info(f"🔔 Assigned notification role '{target_role.name}' to {member.display_name}")
            except discord.Forbidden:
                logger.warning(f"PERMISSION ERROR: Cannot assign '{target_role.name}'. Check bot role hierarchy.")
            except Exception as e:
                logger.error(f"Error adding notification role {target_role.name}: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Removes notification role when user unreacts."""
        if payload.user_id == self.bot.user.id:
            return

        emoji_str = str(payload.emoji.name)
        notif_info = NOTIFICATION_EMOJI_LOOKUP.get(emoji_str)
        if not notif_info:
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

        target_role = await self._resolve_notification_role(guild, notif_info)
        if target_role and target_role in member.roles:
            try:
                await member.remove_roles(target_role, reason=f"Unselected {notif_info['name']} alert role")
                logger.info(f"🔔 Removed notification role '{target_role.name}' from {member.display_name}")
            except discord.Forbidden:
                logger.warning(f"PERMISSION ERROR: Cannot remove '{target_role.name}'. Check bot role hierarchy.")
            except Exception as e:
                logger.error(f"Error removing notification role {target_role.name}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(NotificationRolesCog(bot))
