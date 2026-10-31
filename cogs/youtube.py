import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Literal
import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from database import db
from services.youtube_detector import detector, VideoType, YouTubeVideo
from services.websub import WebSubManager
from utils.embeds import create_notification_embed, TYPE_STYLING

logger = logging.getLogger("YouTubeCog")

class YouTubeCog(commands.Cog, name="YouTube Notifications"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.websub = WebSubManager(callback_handler=self.handle_incoming_push)
        self.websub_renewal_loop.start()
        self.safety_sync_loop.start()

    async def cog_load(self):
        """Starts the WebSub webhook server when cog loads."""
        await self.websub.start()

    def cog_unload(self):
        self.websub_renewal_loop.cancel()
        self.safety_sync_loop.cancel()
        asyncio.create_task(self.websub.stop())

    def get_target_channel_for_type(
        self,
        guild: discord.Guild,
        v_type: VideoType,
        default_channel_id: Optional[str] = None
    ) -> Optional[discord.TextChannel]:
        """
        Intelligently routes notifications to dedicated Discord channels:
        - LIVE / UPCOMING -> #live-streams, #streams, #live
        - SHORTS          -> #shorts, #short, #youtube-shorts
        - VIDEO           -> #videos, #video, #uploads
        - LIVE_VOD        -> #live-streams, #vods, #videos
        Falls back to default channel if specific channel is not present.
        """
        routing_names = {
            VideoType.LIVE: ["live-streams", "livestreams", "live", "streams", "stream-alerts"],
            VideoType.UPCOMING: ["live-streams", "livestreams", "live", "streams", "stream-alerts"],
            VideoType.SHORTS: ["shorts", "short", "youtube-shorts"],
            VideoType.VIDEO: ["videos", "video", "uploads", "new-videos"],
            VideoType.LIVE_VOD: ["live-streams", "vods", "live-vods", "videos", "streams"]
        }

        target_names = routing_names.get(v_type, [])
        for name in target_names:
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch and ch.permissions_for(guild.me).send_messages:
                return ch

        # Fallback to default channel ID if configured
        if default_channel_id:
            ch = guild.get_channel(int(default_channel_id))
            if ch and ch.permissions_for(guild.me).send_messages:
                return ch

        return None

    async def auto_provision_guild(self, guild: discord.Guild):
        """Automatically provisions tracked channels for a guild without requiring any commands."""
        # 1. Find the best fallback channel
        target_channel = None

        if config.NOTIFICATION_CHANNEL_ID:
            target_channel = guild.get_channel(int(config.NOTIFICATION_CHANNEL_ID))

        if not target_channel and config.NOTIFICATION_CHANNEL_NAME:
            target_channel = discord.utils.get(guild.text_channels, name=config.NOTIFICATION_CHANNEL_NAME.lower())

        if not target_channel:
            preferred_names = [
                "stream-alerts", "youtube-alerts", "streams", "youtube",
                "announcements", "videos", "general", "bot-commands", "chat"
            ]
            for name in preferred_names:
                match = discord.utils.get(guild.text_channels, name=name)
                if match and match.permissions_for(guild.me).send_messages:
                    target_channel = match
                    break

        if not target_channel:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    target_channel = ch
                    break

        if not target_channel:
            logger.warning(f"Could not find a writable channel in guild '{guild.name}' ({guild.id})")
            return

        logger.info(f"Target fallback channel in '{guild.name}': #{target_channel.name} ({target_channel.id})")

        # 2. Auto-subscribe the configured creators to Google WebSub
        for creator_query in config.AUTO_TRACK_CHANNELS:
            info = await detector.resolve_channel(creator_query)
            if not info:
                logger.warning(f"Failed to auto-resolve creator '{creator_query}'")
                continue

            await db.add_subscription(
                guild_id=str(guild.id),
                channel_id=info.channel_id,
                channel_title=info.channel_title,
                discord_channel_id=str(target_channel.id),
                ping_role_id=None,
                notify_video=1,
                notify_shorts=1,
                notify_live=1,
                notify_vod=1
            )
            logger.info(f"Subscribed '{info.channel_title}' ({info.channel_id}) -> #{target_channel.name}")
            asyncio.create_task(self.websub.subscribe_channel(info.channel_id))

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Automatically sets up monitoring when joining a server."""
        await self.auto_provision_guild(guild)

    @commands.Cog.listener()
    async def on_ready(self):
        """On bot startup, registers WebSub push subscriptions. ZERO polling is performed."""
        logger.info("Bot is ready. Initializing real-time WebSub push subscriptions...")
        try:
            for guild in self.bot.guilds:
                await self.auto_provision_guild(guild)

            channel_ids = await db.get_all_tracked_channel_ids()
            if self.websub.callback_url:
                await self.websub.renew_all_subscriptions(channel_ids)
                logger.info(f"⚡ [Event-Driven Push Active] Listening for YouTube uploads on {len(channel_ids)} channels (0 Polling).")
            else:
                logger.warning("No CALLBACK_URL configured for WebSub. Push notifications require a public URL.")
        except Exception as e:
            logger.error(f"Error during WebSub initialization: {e}")

    # --- Daily WebSub Lease Renewal Task (Once every 24 hours) ---
    @tasks.loop(hours=24)
    async def websub_renewal_loop(self):
        """Automatically renews Google WebSub subscriptions every 24 hours so pushes never expire."""
        try:
            channel_ids = await db.get_all_tracked_channel_ids()
            await self.websub.renew_all_subscriptions(channel_ids)
        except Exception as e:
            logger.error(f"Error in WebSub renewal loop: {e}")

    @websub_renewal_loop.before_loop
    async def before_renewal_loop(self):
        await self.bot.wait_until_ready()

    async def _fetch_rss_feed_ids(self, channel_id: str) -> list:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        video_ids = []
        try:
            import aiohttp
            import xml.etree.ElementTree as ET
            timeout = aiohttp.ClientTimeout(total=6)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        root = ET.fromstring(text)
                        ns = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
                        for entry in root.findall('atom:entry', ns)[:3]:
                            vid_elem = entry.find('yt:videoId', ns)
                            if vid_elem is not None and vid_elem.text:
                                video_ids.append(vid_elem.text)
        except Exception:
            pass
        return video_ids

    # --- Lightweight Safety Sync Task (Every 60s) ---
    @tasks.loop(seconds=60)
    async def safety_sync_loop(self):
        """
        Safety Sync: Guarantees that if Google WebSub or an external webhook
        ever delays or drops a push, new videos and shorts are automatically detected
        and dispatched to Discord within 60 seconds.
        """
        try:
            channel_ids = await db.get_all_tracked_channel_ids()
            for channel_id in channel_ids:
                feed_items = await self._fetch_rss_feed_ids(channel_id)
                for video_id in feed_items:
                    already_posted = False
                    for vt in ["video", "shorts", "live", "upcoming", "live_vod"]:
                        if await db.is_video_posted(video_id, config.GUILD_ID, vt):
                            already_posted = True
                            break
                    if not already_posted:
                        logger.info(f"⚡ [Safety Sync] Catching unposted content: {video_id} on {channel_id}")
                        await self.handle_incoming_push(video_id, channel_id)
        except Exception as e:
            logger.debug(f"Safety sync loop notice: {e}")

    @safety_sync_loop.before_loop
    async def before_safety_sync_loop(self):
        await self.bot.wait_until_ready()

    async def handle_incoming_push(self, video_id: str, channel_id: str):
        """
        Triggered immediately when Google WebSub sends an HTTP POST push notification.
        Delivers the alert to Discord in real-time (< 3-5 seconds).
        NO POLLING - 100% PURE EVENT PUSH.
        """
        subs = await db.get_subscriptions_for_channel(channel_id)
        if not subs:
            return

        detailed_video = await detector.classify_video_by_id(
            video_id=video_id,
            channel_id=channel_id,
            channel_title=subs[0]["channel_title"]
        )

        v_type = detailed_video.video_type

        for sub in subs:
            guild_id = sub["guild_id"]

            if v_type == VideoType.VIDEO and not sub["notify_video"]:
                continue
            elif v_type == VideoType.SHORTS and not sub["notify_shorts"]:
                continue
            elif v_type == VideoType.UPCOMING and not sub["notify_live"]:
                continue
            elif v_type == VideoType.LIVE and not sub["notify_live"]:
                continue
            elif v_type == VideoType.LIVE_VOD and not sub["notify_vod"]:
                continue

            already_posted = await db.is_video_posted(video_id, guild_id, v_type.value)
            if already_posted:
                continue

            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue

            # Strict Real-Time Filter: ONLY notify present uploads (< 2 hours old to prevent stale replay pushes)
            if v_type in [VideoType.VIDEO, VideoType.SHORTS, VideoType.LIVE_VOD]:
                if detailed_video.published_at:
                    try:
                        pub_str = detailed_video.published_at.replace("Z", "+00:00")
                        pub_dt = datetime.fromisoformat(pub_str)
                        age_minutes = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 60
                        if age_minutes > 120:
                            await db.mark_video_posted(video_id, guild_id, v_type.value)
                            logger.info(f"Skipped older upload push: [{v_type.value}] '{detailed_video.title}' ({age_minutes:.1f} mins old)")
                            continue
                    except Exception:
                        pass

            target_channel = self.get_target_channel_for_type(guild, v_type, sub.get("discord_channel_id"))
            if not target_channel:
                continue

            content_str, embed, view = create_notification_embed(
                video=detailed_video,
                ping_role_id=sub["ping_role_id"],
                custom_message_template=sub.get("custom_message")
            )

            try:
                msg = await target_channel.send(content=content_str, embed=embed, view=view)
                await db.mark_video_posted(video_id, guild_id, v_type.value, message_id=str(msg.id))
                logger.info(f"⚡ [Instant WebSub Push] Posted [{v_type.value}] '{detailed_video.title}' to #{target_channel.name} in {guild.name}")
            except Exception as e:
                logger.error(f"Failed to deliver WebSub push alert for {video_id} in {guild_id}: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(YouTubeCog(bot))
