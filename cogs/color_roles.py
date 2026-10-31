import logging
import asyncio
from typing import Dict, Any, Optional, List
import discord
from discord.ext import commands
from discord.message import convert_emoji_reaction

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

# Fast in-memory lookup tables
COLOR_LOOKUP: Dict[Any, Dict[str, Any]] = {}
ALL_COLOR_ROLE_IDS = set()
ROLE_ID_TO_EMOJIS: Dict[int, List[str]] = {}

for item in COLOR_DEFINITIONS:
    role_id = item["id"]
    ALL_COLOR_ROLE_IDS.add(role_id)
    COLOR_LOOKUP[item["emoji"]] = item

    emojis_for_role = [item["emoji"]]
    for alt in item["alt_keys"]:
        COLOR_LOOKUP[alt] = item
        if isinstance(alt, int):
            # Custom emoji format name:id
            custom_name = next((k for k in item["alt_keys"] if isinstance(k, str)), "emoji")
            emojis_for_role.append(f"{custom_name}:{alt}")
        elif isinstance(alt, str):
            emojis_for_role.append(alt)

    ROLE_ID_TO_EMOJIS[role_id] = emojis_for_role

ROLES_CHANNEL_ID = 1559330910132764782  # #roles


class ColorRolesCog(commands.Cog, name="Color Roles"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.menu_message_id: Optional[int] = None
        self._user_locks: Dict[int, asyncio.Lock] = {}

    def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        """Prevents race conditions if a user spam-clicks reactions."""
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]

    async def cog_load(self):
        logger.info("Color Roles cog loaded.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Auto-provisions the color reaction menu in #roles if not already posted."""
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(ROLES_CHANNEL_ID)
        if not channel:
            return

        async for msg in channel.history(limit=15):
            if msg.author.id == self.bot.user.id and msg.embeds and "Choose Your Name Color" in (msg.embeds[0].title or ""):
                self.menu_message_id = msg.id
                logger.info(f"Found existing Color Role Menu in #{channel.name} (ID: {msg.id})")
                return

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

        for item in COLOR_DEFINITIONS:
            try:
                await msg.add_reaction(item["emoji"])
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.debug(f"Reaction add error: {e}")

        logger.info(f"Posted fresh Color Role Menu in #{channel.name} ({msg.id})")
        return msg

    def _get_color_info(self, emoji: Any) -> Optional[Dict[str, Any]]:
        """Resolves an emoji (str, PartialEmoji, or Emoji) to its color definition."""
        if isinstance(emoji, str):
            return COLOR_LOOKUP.get(emoji)

        emoji_id = getattr(emoji, "id", None)
        if emoji_id and emoji_id in COLOR_LOOKUP:
            return COLOR_LOOKUP[emoji_id]

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
        Hyper-Optimized Exclusive Color Role Assigner:
        - Atomic 1-call role swap (member.edit)
        - Direct parallel reaction deletion (0ms message fetch)
        - Instant cache lookup
        """
        if payload.user_id == self.bot.user.id:
            return

        target_info = self._get_color_info(payload.emoji)
        if not target_info:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        # Fast cache lookup for member
        member = payload.member or guild.get_member(payload.user_id)
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception:
                return

        if not member or member.bot:
            return

        async with self._get_user_lock(member.id):
            target_role = guild.get_role(target_info["id"]) or discord.utils.get(guild.roles, name=target_info["name"])

            # 1. Calculate atomic role update
            current_roles = list(member.roles)
            roles_to_keep = [r for r in current_roles if r.id not in ALL_COLOR_ROLE_IDS]
            
            # Roles being removed
            roles_being_removed = [r for r in current_roles if r.id in ALL_COLOR_ROLE_IDS and (target_role is None or r.id != target_role.id)]

            if target_role and target_role not in roles_to_keep:
                final_roles = roles_to_keep + [target_role]
            else:
                final_roles = roles_to_keep

            # Prepare parallel operations
            tasks = []

            # A. Update Discord roles in ONE single atomic API call
            if set(final_roles) != set(current_roles):
                tasks.append(
                    member.edit(roles=final_roles, reason=f"Exclusive Color: {target_info['name']}")
                )

            # B. Directly delete previous reaction(s) without needing to fetch the message
            for removed_role in roles_being_removed:
                emojis_to_delete = ROLE_ID_TO_EMOJIS.get(removed_role.id, [])
                for em in emojis_to_delete:
                    try:
                        em_str = convert_emoji_reaction(em)
                        tasks.append(
                            self.bot.http.remove_reaction(
                                payload.channel_id,
                                payload.message_id,
                                em_str,
                                member.id
                            )
                        )
                    except Exception:
                        pass

            # Execute role change and reaction cleanup in PARALLEL
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, Exception) and not isinstance(res, discord.NotFound):
                        logger.debug(f"Fast role/reaction operation notice: {res}")

            logger.info(f"⚡ [Super-Fast] Assigned {target_info['name']} & removed previous roles/reactions for {member.display_name}")

            # C. Background cleanup for any lingering reactions
            asyncio.create_task(self._cleanup_other_reactions(payload.channel_id, payload.message_id, member, target_info["id"]))

    async def _cleanup_other_reactions(self, channel_id: int, message_id: int, member: discord.Member, active_role_id: int):
        """Asynchronously cleans up any stray reactions without delaying the user response."""
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return
            message = discord.utils.get(self.bot.cached_messages, id=message_id) or await channel.fetch_message(message_id)
            if not message:
                return

            cleanup_tasks = []
            for r in message.reactions:
                r_info = self._get_color_info(r.emoji)
                if r_info and r_info["id"] != active_role_id:
                    em_str = convert_emoji_reaction(r.emoji)
                    cleanup_tasks.append(
                        self.bot.http.remove_reaction(channel_id, message_id, em_str, member.id)
                    )
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """
        When member unreacts from their color:
        Removes the color role, reverting to default username color with 0ms latency.
        """
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

        target_role = guild.get_role(target_info["id"]) or discord.utils.get(guild.roles, name=target_info["name"])

        if target_role and target_role in member.roles:
            try:
                await member.remove_roles(target_role, reason="Unreacted from color role")
                logger.info(f"⚡ [Super-Fast] Removed color role '{target_role.name}' from {member.display_name}")
            except Exception as e:
                logger.error(f"Error removing unreacted color role: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ColorRolesCog(bot))
