import aiosqlite
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import config

class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path

    async def init_db(self):
        """Initialize database schema with tables for YouTube notifications and settings."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS youtube_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    channel_title TEXT NOT NULL,
                    discord_channel_id TEXT NOT NULL,
                    ping_role_id TEXT,
                    notify_video INTEGER DEFAULT 1,
                    notify_shorts INTEGER DEFAULT 1,
                    notify_live INTEGER DEFAULT 1,
                    notify_vod INTEGER DEFAULT 1,
                    custom_message TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(guild_id, channel_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS posted_videos (
                    video_id TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    video_type TEXT NOT NULL,
                    posted_at TEXT NOT NULL,
                    message_id TEXT,
                    PRIMARY KEY (video_id, guild_id, video_type)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS server_settings (
                    guild_id TEXT PRIMARY KEY,
                    dashboard_enabled INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)

            await db.commit()

    async def add_subscription(
        self,
        guild_id: str,
        channel_id: str,
        channel_title: str,
        discord_channel_id: str,
        ping_role_id: Optional[str] = None,
        notify_video: int = 1,
        notify_shorts: int = 1,
        notify_live: int = 1,
        notify_vod: int = 1,
        custom_message: Optional[str] = None
    ) -> bool:
        """Add or update a YouTube subscription for a guild."""
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO youtube_subscriptions (
                    guild_id, channel_id, channel_title, discord_channel_id,
                    ping_role_id, notify_video, notify_shorts, notify_live, notify_vod,
                    custom_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, channel_id) DO UPDATE SET
                    channel_title = excluded.channel_title,
                    discord_channel_id = excluded.discord_channel_id,
                    ping_role_id = excluded.ping_role_id,
                    notify_video = excluded.notify_video,
                    notify_shorts = excluded.notify_shorts,
                    notify_live = excluded.notify_live,
                    notify_vod = excluded.notify_vod,
                    custom_message = excluded.custom_message
            """, (
                str(guild_id),
                channel_id,
                channel_title,
                str(discord_channel_id),
                str(ping_role_id) if ping_role_id else None,
                notify_video,
                notify_shorts,
                notify_live,
                notify_vod,
                custom_message,
                now
            ))
            await db.commit()
            return True

    async def remove_subscription(self, guild_id: str, channel_id: str) -> bool:
        """Remove a YouTube subscription for a guild."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM youtube_subscriptions 
                WHERE guild_id = ? AND channel_id = ?
            """, (str(guild_id), channel_id))
            await db.commit()
            return cursor.rowcount > 0

    async def get_guild_subscriptions(self, guild_id: str) -> List[Dict[str, Any]]:
        """Get all subscriptions configured for a specific guild."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM youtube_subscriptions WHERE guild_id = ?
            """, (str(guild_id),)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_tracked_channel_ids(self) -> List[str]:
        """Get unique list of YouTube channel IDs tracked across all guilds."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT DISTINCT channel_id FROM youtube_subscriptions") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def get_subscriptions_for_channel(self, channel_id: str) -> List[Dict[str, Any]]:
        """Get all guild subscriptions listening for a specific YouTube channel."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM youtube_subscriptions WHERE channel_id = ?
            """, (channel_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def is_video_posted(self, video_id: str, guild_id: str, video_type: str) -> bool:
        """Check if this video with this specific type has already been posted to this guild."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT 1 FROM posted_videos 
                WHERE video_id = ? AND guild_id = ? AND video_type = ?
            """, (video_id, str(guild_id), video_type)) as cursor:
                row = await cursor.fetchone()
                return row is not None

    async def has_channel_history(self, channel_id: str, guild_id: str) -> bool:
        """Check if we have an existing baseline history for this channel in this guild."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT 1 FROM posted_videos 
                WHERE guild_id = ? LIMIT 1
            """, (str(guild_id),)) as cursor:
                row = await cursor.fetchone()
                return row is not None

    async def mark_video_posted(self, video_id: str, guild_id: str, video_type: str, message_id: Optional[str] = None):
        """Mark video as posted for this guild and video type."""
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO posted_videos (video_id, guild_id, video_type, posted_at, message_id)
                VALUES (?, ?, ?, ?, ?)
            """, (video_id, str(guild_id), video_type, now, str(message_id) if message_id else None))
            await db.commit()

    async def update_toggles(
        self,
        guild_id: str,
        channel_id: str,
        notify_video: Optional[int] = None,
        notify_shorts: Optional[int] = None,
        notify_live: Optional[int] = None,
        notify_vod: Optional[int] = None
    ) -> bool:
        """Update notification toggles for a subscription."""
        updates = []
        params = []
        if notify_video is not None:
            updates.append("notify_video = ?")
            params.append(notify_video)
        if notify_shorts is not None:
            updates.append("notify_shorts = ?")
            params.append(notify_shorts)
        if notify_live is not None:
            updates.append("notify_live = ?")
            params.append(notify_live)
        if notify_vod is not None:
            updates.append("notify_vod = ?")
            params.append(notify_vod)

        if not updates:
            return False

        params.extend([str(guild_id), channel_id])
        query = f"UPDATE youtube_subscriptions SET {', '.join(updates)} WHERE guild_id = ? AND channel_id = ?"
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, tuple(params))
            await db.commit()
            return cursor.rowcount > 0

db = Database()
