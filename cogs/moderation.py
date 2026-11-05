import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Button, UserSelect, select

import config
from database import db

logger = logging.getLogger("ModerationCog")

MOD_LOG_CHANNEL_NAMES = ["mod-logs", "mod-log", "moderation-logs", "audit-log", "audit-logs", "logs"]
MISSJEY_PURPLE = 0xAA88FF

def parse_duration(duration_str: str) -> Optional[timedelta]:
    """Parses duration strings like 10m, 1h, 1d, 7d into a timedelta."""
    if not duration_str:
        return timedelta(minutes=10)
    s = duration_str.strip().lower()
    
    if s.isdigit():
        return timedelta(minutes=int(s))
        
    pattern = r'^(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?$'
    match = re.match(pattern, s)
    if not match or not any(match.groups()):
        return None
        
    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = int(match.group(4) or 0)
    
    td = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    if td.total_seconds() <= 0 or td > timedelta(days=28):
        return None
    return td

def format_duration(td: timedelta) -> str:
    """Formats a timedelta into a clean human-readable string."""
    total_seconds = int(td.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 and not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts) or "10m"


class TimeoutModal(Modal):
    def __init__(self, target: discord.Member, cog: "ModerationCog"):
        super().__init__(title=f"⏳ Timeout @{target.display_name[:20]}")
        self.target = target
        self.cog = cog

        self.duration_input = TextInput(
            label="Duration (e.g. 10m, 1h, 1d, 7d)",
            placeholder="10m",
            default="10m",
            required=True,
            max_length=20
        )
        self.add_item(self.duration_input)

        self.reason_input = TextInput(
            label="Reason",
            style=discord.TextStyle.paragraph,
            placeholder="Specify reason for timing out this member...",
            required=True,
            max_length=500
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        td = parse_duration(self.duration_input.value)
        if not td:
            await interaction.followup.send("❌ **Invalid duration!** Please use format like `10m`, `2h`, `1d`, or `7d` (max 28 days).", ephemeral=True)
            return

        reason = self.reason_input.value.strip()
        dur_str = format_duration(td)

        # Apply timeout
        try:
            # DM Target
            await self.cog.send_user_dm(
                self.target,
                action_name="Timed Out",
                color=0xFEE75C,
                reason=reason,
                extra_field=("⏳ Duration", dur_str)
            )

            await self.target.timeout(td, reason=f"[{interaction.user}] {reason}")
            
            # Log action
            case_id = await db.log_mod_action(
                guild_id=str(interaction.guild_id),
                action="TIMEOUT",
                target_id=str(self.target.id),
                target_name=str(self.target),
                moderator_id=str(interaction.user.id),
                moderator_name=str(interaction.user),
                reason=reason,
                duration=dur_str
            )

            await self.cog.send_audit_log(
                guild=interaction.guild,
                action_name="⏳ Member Timed Out",
                color=0xFEE75C,
                target=self.target,
                moderator=interaction.user,
                reason=reason,
                duration=dur_str,
                case_id=case_id
            )

            embed = discord.Embed(
                title="✅ Member Successfully Timed Out",
                description=f"**Target:** {self.target.mention} (`{self.target.id}`)\n"
                            f"**Duration:** `{dur_str}`\n"
                            f"**Reason:** {reason}\n"
                            f"**Case ID:** `#{case_id}`",
                color=0x57F287
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ **Permission Denied by Discord!**\n"
                "Please check two things in **Server Settings ➔ Roles**:\n"
                "1. **Permissions:** Grant the `Jey's Bot 💜` role the **Timeout Members** (or **Administrator**) permission.\n"
                "2. **Hierarchy:** Drag the `Jey's Bot 💜` role **above** member roles in the list.\n"
                "*(Note: Discord's API strictly forbids bots from timing out the Server Owner).* ",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error executing timeout: {e}", exc_info=True)
            await interaction.followup.send(f"❌ **Error executing timeout:** {e}", ephemeral=True)


class KickModal(Modal):
    def __init__(self, target: discord.Member, cog: "ModerationCog"):
        super().__init__(title=f"👢 Kick @{target.display_name[:20]}")
        self.target = target
        self.cog = cog

        self.reason_input = TextInput(
            label="Reason",
            style=discord.TextStyle.paragraph,
            placeholder="Specify reason for kicking this member...",
            required=True,
            max_length=500
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        reason = self.reason_input.value.strip()

        try:
            # DM Target before kicking
            await self.cog.send_user_dm(
                self.target,
                action_name="Kicked",
                color=0xE67E22,
                reason=reason
            )

            await self.target.kick(reason=f"[{interaction.user}] {reason}")

            case_id = await db.log_mod_action(
                guild_id=str(interaction.guild_id),
                action="KICK",
                target_id=str(self.target.id),
                target_name=str(self.target),
                moderator_id=str(interaction.user.id),
                moderator_name=str(interaction.user),
                reason=reason
            )

            await self.cog.send_audit_log(
                guild=interaction.guild,
                action_name="👢 Member Kicked",
                color=0xE67E22,
                target=self.target,
                moderator=interaction.user,
                reason=reason,
                case_id=case_id
            )

            embed = discord.Embed(
                title="✅ Member Successfully Kicked",
                description=f"**Target:** {self.target.mention} (`{self.target.id}`)\n"
                            f"**Reason:** {reason}\n"
                            f"**Case ID:** `#{case_id}`",
                color=0x57F287
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ **Permission Denied by Discord!**\n"
                "Please check two things in **Server Settings ➔ Roles**:\n"
                "1. **Permissions:** Grant the `Jey's Bot 💜` role the **Kick Members** (or **Administrator**) permission.\n"
                "2. **Hierarchy:** Drag the `Jey's Bot 💜` role **above** member roles in the list.\n"
                "*(Note: Discord does not permit kicking the Server Owner).* ",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error kicking member: {e}", exc_info=True)
            await interaction.followup.send(f"❌ **Error kicking member:** {e}", ephemeral=True)


class BanModal(Modal):
    def __init__(self, target: discord.Member, cog: "ModerationCog"):
        super().__init__(title=f"🔨 Ban @{target.display_name[:20]}")
        self.target = target
        self.cog = cog

        self.delete_days_input = TextInput(
            label="Delete Message History (Days: 0 - 7)",
            placeholder="0",
            default="0",
            required=False,
            max_length=1
        )
        self.add_item(self.delete_days_input)

        self.reason_input = TextInput(
            label="Reason",
            style=discord.TextStyle.paragraph,
            placeholder="Specify reason for banning this member...",
            required=True,
            max_length=500
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        reason = self.reason_input.value.strip()
        
        del_days_val = self.delete_days_input.value.strip() or "0"
        delete_days = int(del_days_val) if del_days_val.isdigit() and 0 <= int(del_days_val) <= 7 else 0

        try:
            # DM Target before banning
            await self.cog.send_user_dm(
                self.target,
                action_name="Permanently Banned",
                color=0xED4245,
                reason=reason
            )

            await self.target.ban(delete_message_days=delete_days, reason=f"[{interaction.user}] {reason}")

            case_id = await db.log_mod_action(
                guild_id=str(interaction.guild_id),
                action="BAN",
                target_id=str(self.target.id),
                target_name=str(self.target),
                moderator_id=str(interaction.user.id),
                moderator_name=str(interaction.user),
                reason=reason,
                duration=f"Del history: {delete_days}d"
            )

            await self.cog.send_audit_log(
                guild=interaction.guild,
                action_name="🔨 Member Banned",
                color=0xED4245,
                target=self.target,
                moderator=interaction.user,
                reason=reason,
                case_id=case_id
            )

            embed = discord.Embed(
                title="✅ Member Successfully Banned",
                description=f"**Target:** {self.target.mention} (`{self.target.id}`)\n"
                            f"**Delete History:** `{delete_days} days`\n"
                            f"**Reason:** {reason}\n"
                            f"**Case ID:** `#{case_id}`",
                color=0x57F287
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ **Permission Denied by Discord!**\n"
                "Please check two things in **Server Settings ➔ Roles**:\n"
                "1. **Permissions:** Grant the `Jey's Bot 💜` role the **Ban Members** (or **Administrator**) permission.\n"
                "2. **Hierarchy:** Drag the `Jey's Bot 💜` role **above** member roles in the list.\n"
                "*(Note: Discord does not permit banning the Server Owner).* ",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error banning member: {e}", exc_info=True)
            await interaction.followup.send(f"❌ **Error banning member:** {e}", ephemeral=True)


class WarnModal(Modal):
    def __init__(self, target: discord.Member, cog: "ModerationCog"):
        super().__init__(title=f"⚠️ Warn @{target.display_name[:20]}")
        self.target = target
        self.cog = cog

        self.reason_input = TextInput(
            label="Warning Reason",
            style=discord.TextStyle.paragraph,
            placeholder="Specify reason for warning this member...",
            required=True,
            max_length=500
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        reason = self.reason_input.value.strip()

        try:
            # DM Target
            dm_sent = await self.cog.send_user_dm(
                self.target,
                action_name="Warned",
                color=0xF1C40F,
                reason=reason
            )

            warn_id = await db.add_warning(
                guild_id=str(interaction.guild_id),
                user_id=str(self.target.id),
                moderator_id=str(interaction.user.id),
                reason=reason
            )

            case_id = await db.log_mod_action(
                guild_id=str(interaction.guild_id),
                action="WARN",
                target_id=str(self.target.id),
                target_name=str(self.target),
                moderator_id=str(interaction.user.id),
                moderator_name=str(interaction.user),
                reason=reason
            )

            all_warns = await db.get_warnings(str(interaction.guild_id), str(self.target.id))
            warn_count = len(all_warns)

            await self.cog.send_audit_log(
                guild=interaction.guild,
                action_name="⚠️ Member Warned",
                color=0xF1C40F,
                target=self.target,
                moderator=interaction.user,
                reason=reason,
                case_id=case_id,
                extra_field=("Total Warnings", f"`{warn_count}`")
            )

            dm_status = "Direct message delivered ✅" if dm_sent else "DMs closed ⚠️"
            embed = discord.Embed(
                title="✅ Warning Successfully Issued",
                description=f"**Target:** {self.target.mention} (`{self.target.id}`)\n"
                            f"**Reason:** {reason}\n"
                            f"**Total Warnings:** `{warn_count}`\n"
                            f"**DM Status:** {dm_status}\n"
                            f"**Case ID:** `#{case_id}`",
                color=0x57F287
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error warning member: {e}", exc_info=True)
            await interaction.followup.send(f"❌ **Error issuing warning:** {e}", ephemeral=True)


class MemberActionView(View):
    def __init__(self, target: discord.Member, moderator: discord.Member, cog: "ModerationCog"):
        super().__init__(timeout=180)
        self.target = target
        self.moderator = moderator
        self.cog = cog

        # If member is currently timed out, show Unmute button
        if target.is_timed_out():
            unmute_btn = Button(
                label="Remove Timeout",
                emoji="🔊",
                style=discord.ButtonStyle.secondary,
                custom_id="btn_unmute"
            )
            unmute_btn.callback = self.on_unmute
            self.add_item(unmute_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message("❌ This moderation menu belongs to another moderator.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Timeout / Mute", emoji="⏳", style=discord.ButtonStyle.primary, row=0)
    async def btn_timeout(self, interaction: discord.Interaction, button: Button):
        modal = TimeoutModal(self.target, self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Warn", emoji="⚠️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_warn(self, interaction: discord.Interaction, button: Button):
        modal = WarnModal(self.target, self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Kick", emoji="👢", style=discord.ButtonStyle.danger, row=0)
    async def btn_kick(self, interaction: discord.Interaction, button: Button):
        modal = KickModal(self.target, self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Ban", emoji="🔨", style=discord.ButtonStyle.danger, row=0)
    async def btn_ban(self, interaction: discord.Interaction, button: Button):
        modal = BanModal(self.target, self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Select Another Member", emoji="🔄", style=discord.ButtonStyle.secondary, row=1)
    async def btn_change(self, interaction: discord.Interaction, button: Button):
        panel_view = ModerationPanelView(self.moderator, self.cog)
        embed = discord.Embed(
            title="🛡️ Moderation Control Center",
            description="Use the dropdown menu below to **search or select** a server member to moderate.",
            color=MISSJEY_PURPLE
        )
        await interaction.response.edit_message(embed=embed, view=panel_view)

    async def on_unmute(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.target.timeout(None, reason=f"Timeout removed by [{interaction.user}]")
            case_id = await db.log_mod_action(
                guild_id=str(interaction.guild_id),
                action="UNTIMEOUT",
                target_id=str(self.target.id),
                target_name=str(self.target),
                moderator_id=str(interaction.user.id),
                moderator_name=str(interaction.user),
                reason="Timeout manually removed by moderator."
            )
            await self.cog.send_audit_log(
                guild=interaction.guild,
                action_name="🔊 Timeout Removed",
                color=0x57F287,
                target=self.target,
                moderator=interaction.user,
                reason="Timeout manually removed by moderator.",
                case_id=case_id
            )
            await interaction.followup.send(f"✅ Removed timeout for {self.target.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to remove timeout: {e}", ephemeral=True)


class ModerationPanelView(View):
    def __init__(self, moderator: discord.Member, cog: "ModerationCog"):
        super().__init__(timeout=180)
        self.moderator = moderator
        self.cog = cog

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message("❌ This moderation menu belongs to another moderator.", ephemeral=True)
            return False
        return True

    @discord.ui.select(
        cls=UserSelect,
        placeholder="🔍 Search or select a server member...",
        min_values=1,
        max_values=1
    )
    async def select_user(self, interaction: discord.Interaction, select_menu: UserSelect):
        target = select_menu.values[0]
        if not isinstance(target, discord.Member):
            # Fetch member if only User object returned
            target = interaction.guild.get_member(target.id) or await interaction.guild.fetch_member(target.id)

        # Check hierarchy & safety
        error_msg = self.cog.can_moderate(interaction.user, target, interaction.guild)
        if error_msg:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return

        embed = self.cog.build_target_profile_embed(target)
        view = MemberActionView(target, interaction.user, self.cog)
        await interaction.response.edit_message(embed=embed, view=view)


class ModerationCog(commands.Cog, name="Moderation"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Context menu command (Right-click user -> Apps -> Moderate Member)
        self.ctx_menu = app_commands.ContextMenu(
            name="Moderate Member",
            callback=self.context_moderate_user
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    def can_moderate(self, moderator: discord.Member, target: discord.Member, guild: discord.Guild) -> Optional[str]:
        """Validates permissions and role hierarchy before moderation."""
        if target.id == moderator.id:
            return "❌ You cannot moderate yourself!"
        if target.id == guild.owner_id:
            return "❌ You cannot moderate the Server Owner! (Discord strictly protects the owner from timeouts/kicks/bans)."
        if target.id == self.bot.user.id:
            return "❌ You cannot moderate the bot!"
        
        # Check bot permissions
        bot_perms = guild.me.guild_permissions
        if not (bot_perms.administrator or bot_perms.moderate_members or bot_perms.kick_members or bot_perms.ban_members):
            return (
                "❌ **Bot Missing Permissions!**\n"
                "In **Server Settings ➔ Roles**, please grant **`Jey's Bot 💜`** the **Timeout Members**, **Kick Members**, and **Ban Members** permissions (or **Administrator**)."
            )

        # Check hierarchy if moderator is not owner
        if moderator.id != guild.owner_id and target.top_role >= moderator.top_role:
            return f"❌ You cannot moderate {target.mention} because their role (`{target.top_role.name}`) is equal to or higher than yours!"
            
        # Check if bot can moderate
        if target.top_role >= guild.me.top_role:
            return (
                f"❌ I cannot moderate {target.mention} because their role (`{target.top_role.name}`) is higher than or equal to my highest role (`{guild.me.top_role.name}`)!\n"
                f"👉 Please drag **`Jey's Bot 💜`** higher in **Server Settings ➔ Roles**."
            )
            
        return None

    def build_target_profile_embed(self, target: discord.Member) -> discord.Embed:
        """Constructs an informative member profile card for moderation."""
        embed = discord.Embed(
            title=f"🛡️ Moderate Member: {target.display_name}",
            color=MISSJEY_PURPLE
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        status_str = "⏳ **Currently in Timeout**" if target.is_timed_out() else "✅ Normal"
        joined_str = f"<t:{int(target.joined_at.timestamp())}:R>" if target.joined_at else "Unknown"
        created_str = f"<t:{int(target.created_at.timestamp())}:R>"
        
        roles_list = [r.mention for r in reversed(target.roles[1:])][:6]
        roles_str = " ".join(roles_list) if roles_list else "*No roles*"

        embed.add_field(name="User Info", value=f"• **Username:** {target}\n• **ID:** `{target.id}`\n• **Status:** {status_str}", inline=False)
        embed.add_field(name="Account Timestamps", value=f"• **Account Created:** {created_str}\n• **Joined Server:** {joined_str}", inline=False)
        embed.add_field(name="Roles", value=roles_str, inline=False)
        embed.set_footer(text="Choose a moderation action below to open the modal dialog 👇")
        return embed

    async def send_user_dm(self, target: discord.Member, action_name: str, color: int, reason: str, extra_field: tuple = None) -> bool:
        """Politely informs the punished member via direct message."""
        try:
            embed = discord.Embed(
                title=f"Notice from {target.guild.name}",
                description=f"You have been **{action_name}** in **{target.guild.name}**.",
                color=color,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
            if extra_field:
                embed.add_field(name=extra_field[0], value=extra_field[1], inline=False)
            embed.set_footer(text="If you believe this was a mistake, please reach out to server staff.")
            await target.send(embed=embed)
            return True
        except Exception:
            return False

    async def send_audit_log(
        self,
        guild: discord.Guild,
        action_name: str,
        color: int,
        target: discord.Member,
        moderator: discord.Member,
        reason: str,
        duration: Optional[str] = None,
        case_id: Optional[int] = None,
        extra_field: tuple = None
    ):
        """Dispatches structured audit record to #mod-logs channel."""
        channel = None
        for name in MOD_LOG_CHANNEL_NAMES:
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch and ch.permissions_for(guild.me).send_messages:
                channel = ch
                break

        if not channel:
            return

        embed = discord.Embed(
            title=f"{action_name} | Case #{case_id or '—'}",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Target Member", value=f"{target.mention}\n`{target}` (`{target.id}`)", inline=True)
        embed.add_field(name="Moderator", value=f"{moderator.mention}\n`{moderator}`", inline=True)
        if duration:
            embed.add_field(name="Duration", value=f"`{duration}`", inline=True)
        embed.add_field(name="Reason", value=reason or "*No reason specified*", inline=False)
        if extra_field:
            embed.add_field(name=extra_field[0], value=extra_field[1], inline=True)
        embed.set_footer(text=f"User ID: {target.id}")

        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to post to audit log channel: {e}")

    # --- Slash Command: /moderate [member] ---
    @app_commands.command(name="moderate", description="🛡️ Open the interactive moderation control panel with dialog modals.")
    @app_commands.describe(member="Optional: The member you want to moderate directly")
    @app_commands.default_permissions(moderate_members=True)
    async def moderate(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """Interactive moderation command."""
        # Check permissions
        perms = interaction.user.guild_permissions
        if not (perms.moderate_members or perms.kick_members or perms.ban_members or perms.administrator):
            await interaction.response.send_message("❌ **Access Denied!** You do not have permission to moderate members.", ephemeral=True)
            return

        if member:
            err = self.can_moderate(interaction.user, member, interaction.guild)
            if err:
                await interaction.response.send_message(err, ephemeral=True)
                return
            embed = self.build_target_profile_embed(member)
            view = MemberActionView(member, interaction.user, self)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            embed = discord.Embed(
                title="🛡️ Moderation Control Center",
                description="Use the dropdown menu below to **search or select** a server member to moderate.",
                color=MISSJEY_PURPLE
            )
            embed.set_footer(text="MissJey's Community 💜 • Staff Moderation Hub")
            view = ModerationPanelView(interaction.user, self)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # --- Context Menu Callback: Right-Click Member -> Apps -> Moderate Member ---
    async def context_moderate_user(self, interaction: discord.Interaction, member: discord.Member):
        perms = interaction.user.guild_permissions
        if not (perms.moderate_members or perms.kick_members or perms.ban_members or perms.administrator):
            await interaction.response.send_message("❌ **Access Denied!** You do not have permission to moderate members.", ephemeral=True)
            return

        err = self.can_moderate(interaction.user, member, interaction.guild)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        embed = self.build_target_profile_embed(member)
        view = MemberActionView(member, interaction.user, self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
