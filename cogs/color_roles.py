import logging
import asyncio
from typing import Dict, Any, Optional
import discord
from discord.ext import commands

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
ROLES_CHANNEL_ID = 1559330910132764782  # #roles


def build_menu_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎨 Choose Your Name Color!",
        description=(
            "Personalize your appearance in the server! Click any color button below to instantly change your username color.\n\n"
            "**Available Colors:**\n"
            "🔴 **Red** (`#ff8890`)\n"
            "🟣 **Purple** (`#aa88ff`)\n"
            "🟢 **Green** (`#88ff90`)\n"
            "🌸 **Pink** (`#fe88ff`)\n"
            "🟠 **Orange** (`#ffa788`)\n"
            "🟡 **Yellow** (`#f5ff88`)\n"
            "🔵 **Blue** (`#88eaff`)\n\n"
            "⚡ **Exclusive:** You can only have **one color at a time**. Clicking another color swaps it instantly! Click **Default Color** to reset."
        ),
        color=0xAA88FF
    )
    embed.set_footer(text="Jey's Bot 💜 • Instant Color Role Engine")
    return embed


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

        # Toggle off if clicking same color
        if target_role in current_roles:
            await member.edit(roles=roles_to_keep, reason=f"Removed {self.color_info['name']} color")
            await interaction.response.defer()
            return

        # Instant atomic 1-call swap
        final_roles = roles_to_keep + [target_role]
        await member.edit(roles=final_roles, reason=f"Selected {self.color_info['name']} color")

        # Silent acknowledgement (no chat message/popup sent to anyone)
        await interaction.response.defer()


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
        await interaction.response.defer()


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

    async def cog_load(self):
        # Register persistent view so buttons work across restarts
        self.bot.add_view(ColorRoleView())
        logger.info("Color Roles cog loaded with 100% button-driven engine.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Auto-provisions or updates the color menu in #roles."""
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(ROLES_CHANNEL_ID)
        if not channel:
            return

        embed = build_menu_embed()
        view = ColorRoleView()

        # Look for existing menu
        async for msg in channel.history(limit=15):
            if msg.author.id == self.bot.user.id and msg.embeds and "Choose Your Name Color" in (msg.embeds[0].title or ""):
                self.menu_message_id = msg.id
                logger.info(f"Found existing Color Role Menu ({msg.id}). Clearing reactions & updating buttons...")
                try:
                    await msg.clear_reactions()
                except Exception:
                    pass
                await msg.edit(embed=embed, view=view)
                return

        # Not posted yet -> post fresh menu with buttons
        await self.post_color_menu(channel)

    async def post_color_menu(self, channel: discord.TextChannel) -> discord.Message:
        """Posts the pure button-driven color picker embed."""
        embed = build_menu_embed()
        view = ColorRoleView()
        msg = await channel.send(embed=embed, view=view)
        self.menu_message_id = msg.id
        logger.info(f"Posted fresh Button Color Menu in #{channel.name} ({msg.id})")
        return msg


async def setup(bot: commands.Bot):
    await bot.add_cog(ColorRolesCog(bot))
