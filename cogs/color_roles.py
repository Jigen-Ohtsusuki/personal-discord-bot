import logging
import asyncio
from typing import Dict, Any, Optional, List
import discord
from discord.ext import commands
from discord.message import convert_emoji_reaction

logger = logging.getLogger("ColorRoles")

COLOR_DEFINITIONS = [
    {"name": "Red", "id": 1559349426290430055, "emoji": "🔴", "hex": "#ff8890", "row": 0},
    {"name": "Purple", "id": 1559349427574022154, "emoji": "🟣", "hex": "#aa88ff", "row": 0},
    {"name": "Green", "id": 1559349428207222944, "emoji": "🟢", "hex": "#88ff90", "row": 0},
    {"name": "Pink", "id": 1559349429243346964, "emoji": "🌸", "hex": "#fe88ff", "row": 0},
    {"name": "Orange", "id": 1559349430623404103, "emoji": "🟠", "hex": "#ffa788", "row": 1},
    {"name": "Yellow", "id": 1559349434020790272, "emoji": "🟡", "hex": "#f5ff88", "row": 1},
    {"name": "Blue", "id": 1559349434909855804, "emoji": "🔵", "hex": "#88eaff", "row": 1},
]

ALL_COLOR_ROLE_IDS = {c["id"] for c in COLOR_DEFINITIONS}
ROLE_ID_TO_UNICODE = {c["id"]: c["emoji"] for c in COLOR_DEFINITIONS}
ROLE_ID_TO_NAME = {c["id"]: c["name"] for c in COLOR_DEFINITIONS}

COLOR_LOOKUP: Dict[Any, Dict[str, Any]] = {}
for item in COLOR_DEFINITIONS:
    COLOR_LOOKUP[item["emoji"]] = item
    COLOR_LOOKUP[item["name"].lower()] = item

ROLES_CHANNEL_ID = 1559330910132764782  # #roles


class ColorButton(discord.ui.Button):
    def __init__(self, color_info: Dict[str, Any]):
        super().__init__(
            label=color_info["name"],
            emoji=color_info["emoji"],
            style=discord.ButtonStyle.secondary,
            custom_id=f"btn_color_{color_info['id']}",
            row=color_info["row"]
        )
        self.color_info = color_info

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        if not guild or not isinstance(member, discord.Member):
            return

        target_role = guild.get_role(self.color_info["id"])
        if not target_role:
            await interaction.response.send_message("❌ Role not found on server.", ephemeral=True)
            return

        current_roles = list(member.roles)
        roles_to_keep = [r for r in current_roles if r.id not in ALL_COLOR_ROLE_IDS]

        # Check if user already has this exact color (toggle off)
        if target_role in current_roles:
            await member.edit(roles=roles_to_keep, reason=f"Removed {self.color_info['name']} color")
            await interaction.response.send_message(
                f"⚪ Removed **{self.color_info['name']}** color. Your name color is reset!",
                ephemeral=True
            )
            return

        # Swap to new color in 1 single atomic call
        final_roles = roles_to_keep + [target_role]
        await member.edit(roles=final_roles, reason=f"Selected {self.color_info['name']} color")

        await interaction.response.send_message(
            f"🎨 Your name color has been updated to **{self.color_info['name']}**!",
            ephemeral=True
        )


class ResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Default Color",
            emoji="⚪",
            style=discord.ButtonStyle.danger,
            custom_id="btn_color_reset",
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        if not isinstance(member, discord.Member):
            return

        current_roles = list(member.roles)
        roles_to_keep = [r for r in current_roles if r.id not in ALL_COLOR_ROLE_IDS]

        if len(roles_to_keep) != len(current_roles):
            await member.edit(roles=roles_to_keep, reason="Reset color to default")
            await interaction.response.send_message("⚪ Reverted to default username color!", ephemeral=True)
        else:
            await interaction.response.send_message("You already have the default name color!", ephemeral=True)


class ColorRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for item in COLOR_DEFINITIONS:
            self.add_item(ColorButton(item))
        self.add_item(ResetButton())


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
        # Register persistent view so buttons work across restarts
        self.bot.add_view(ColorRoleView())
        logger.info("Color Roles cog loaded with persistent interactive buttons.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Auto-provisions or updates the color menu in #roles."""
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(ROLES_CHANNEL_ID)
        if not channel:
            return

        # Look for existing menu
        async for msg in channel.history(limit=15):
            if msg.author.id == self.bot.user.id and msg.embeds and "Choose Your Name Color" in (msg.embeds[0].title or ""):
                self.menu_message_id = msg.id
                logger.info(f"Found existing Color Role Menu ({msg.id}). Attaching interactive buttons...")
                # Update with interactive buttons view
                await msg.edit(view=ColorRoleView())
                return

        # Not posted yet -> post fresh menu with buttons and reactions
        await self.post_color_menu(channel)

    async def post_color_menu(self, channel: discord.TextChannel) -> discord.Message:
        """Posts the color picker embed with interactive buttons & reactions."""
        embed = discord.Embed(
            title="🎨 Choose Your Name Color!",
            description=(
                "Personalize your appearance in the server! Click a **Button** below or react with an emoji to change your name color.\n\n"
                "**Available Colors:**\n"
                "🔴 **Red** (`#ff8890`)\n"
                "🟣 **Purple** (`#aa88ff`)\n"
                "🟢 **Green** (`#88ff90`)\n"
                "🌸 **Pink** (`#fe88ff`)\n"
                "🟠 **Orange** (`#ffa788`)\n"
                "🟡 **Yellow** (`#f5ff88`)\n"
                "🔵 **Blue** (`#88eaff`)\n\n"
                "⚡ **Instant:** You can only have **one color at a time**. Selecting another color swaps it instantly!"
            ),
            color=0xAA88FF
        )
        embed.set_footer(text="Jey's Bot 💜 • Instant Color Role Engine")

        view = ColorRoleView()
        msg = await channel.send(embed=embed, view=view)
        self.menu_message_id = msg.id

        for item in COLOR_DEFINITIONS:
            try:
                await msg.add_reaction(item["emoji"])
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.debug(f"Reaction add error: {e}")

        logger.info(f"Posted fresh Color Role Menu in #{channel.name} ({msg.id})")
        return msg

    def _get_color_info(self, emoji: Any) -> Optional[Dict[str, Any]]:
        """Resolves an emoji to its color definition."""
        if isinstance(emoji, str):
            return COLOR_LOOKUP.get(emoji)

        emoji_name = getattr(emoji, "name", None)
        if emoji_name and emoji_name in COLOR_LOOKUP:
            return COLOR_LOOKUP[emoji_name]

        emoji_str = str(emoji)
        if emoji_str in COLOR_LOOKUP:
            return COLOR_LOOKUP[emoji_str]

        return None

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        Instant Reaction Handler:
        - 1 atomic API call for roles
        - Only deletes the single exact previous emoji (0 redundant calls, zero rate-limit)
        """
        if payload.user_id == self.bot.user.id:
            return

        target_info = self._get_color_info(payload.emoji)
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
            roles_to_keep = [r for r in current_roles if r.id not in ALL_COLOR_ROLE_IDS]
            
            # Roles being removed
            roles_being_removed = [r for r in current_roles if r.id in ALL_COLOR_ROLE_IDS and (target_role is None or r.id != target_role.id)]

            final_roles = roles_to_keep + ([target_role] if target_role else [])

            tasks = []

            # 1. Atomic role change
            if set(final_roles) != set(current_roles):
                tasks.append(
                    member.edit(roles=final_roles, reason=f"Color role: {target_info['name']}")
                )

            # 2. Delete ONLY the exact single unicode emoji of the previous color
            for removed_role in roles_being_removed:
                old_unicode = ROLE_ID_TO_UNICODE.get(removed_role.id)
                if old_unicode and old_unicode != target_info["emoji"]:
                    try:
                        tasks.append(
                            self.bot.http.remove_reaction(
                                payload.channel_id,
                                payload.message_id,
                                convert_emoji_reaction(old_unicode),
                                member.id
                            )
                        )
                    except Exception:
                        pass

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            logger.info(f"⚡ [Instant Role] Set {target_info['name']} for {member.display_name}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Instant removal on unreact."""
        if payload.user_id == self.bot.user.id:
            return

        target_info = self._get_color_info(payload.emoji)
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
                await member.remove_roles(target_role, reason="Unreacted from color role")
                logger.info(f"⚡ [Instant Role] Removed '{target_role.name}' from {member.display_name}")
            except Exception as e:
                logger.error(f"Error removing color role: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ColorRolesCog(bot))
