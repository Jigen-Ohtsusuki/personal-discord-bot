import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
GUILD_ID = os.getenv("GUILD_ID", "").strip()  # MissJey's Discord Server ID (for instant sync & private mode)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "bot_database.db"))

# Auto-Tracked YouTube Creators (Zero Commands Required)
AUTO_TRACK_CHANNELS = [
    c.strip() for c in os.getenv("AUTO_TRACK_CHANNELS", "@MissjeyGaming").split(",")
    if c.strip()
]

# Destination Discord Channel (leave blank to auto-detect #stream-alerts, #announcements, or #general)
NOTIFICATION_CHANNEL_ID = os.getenv("NOTIFICATION_CHANNEL_ID", "").strip()
NOTIFICATION_CHANNEL_NAME = os.getenv("NOTIFICATION_CHANNEL_NAME", "").strip()

# WebSub Real-Time Push Settings (Zero-Delay Webhook)
CALLBACK_URL = os.getenv("CALLBACK_URL", "").strip().rstrip("/")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

# Dashboard & Discord OAuth2 Authentication
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "1566009195675914260").strip()
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "").strip()
DASHBOARD_PIN = os.getenv("DASHBOARD_PIN", "jey2026").strip()
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))
