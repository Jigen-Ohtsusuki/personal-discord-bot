# 💜 Jey's Bot — Event-Driven YouTube Discord Engine

A modern, high-performance, private Discord bot built for streamer & gaming communities (**MissJey / Jey Gaming 💜**).

Engineered from the ground up for **100% Event-Driven Push Notifications** with **Zero Polling Loops**.

---

## 🌟 Key Highlights

- **⚡ Zero Polling, 100% Push Architecture**: No background interval loops checking YouTube every 60 seconds. The bot rests at 0% CPU and only activates when an event is pushed directly to it.
- **🔄 Dual Push Redundancy**:
  1. **Stream 1 (Primary):** Google PubSubHubbub (WebSub) server-to-server webhook push (< 3–5 seconds).
  2. **Stream 2 (Mobile Redundancy):** Android FCM (Firebase Cloud Messaging) client listening on persistent TLS socket to `mtalk.google.com:5228`.
- **🎯 Smart Multi-Channel Routing**: Automatically directs notifications to designated Discord channels:
  - 🔴 **Live Streams & Upcoming** ➔ `#live-streams`
  - 🎬 **Standard Videos** ➔ `#videos`
  - 🩳 **YouTube Shorts** ➔ `#shorts`
- **🚫 Zero Commands Required**: Runs 100% automatically in the background without cluttering Discord with slash commands. Auto-provisions tracked channels on startup.
- **🛡️ Persistent SQLite Deduplication**: Uses a local SQLite database (`bot_database.db`) to ensure that even with dual push streams, Discord only receives **one single clean notification** per upload.
- **✨ Rich Visual Embeds & Interactive Buttons**: Custom branded embeds, dynamic color schemes, status badges, and one-click watch buttons.

---

## 🎨 Content Differentiation & Styling

| Content Category | Destination | Embed Color | Status Badge | Interactive Button |
| :--- | :--- | :--- | :--- | :--- |
| **Active Live Stream** | `#live-streams` | Vibrant Red (`#FF0033`) | `🔴 LIVE NOW` | `▶ Watch Live Stream` |
| **Upcoming Stream** | `#live-streams` | Neon Orange (`#FF5722`) | `⏳ UPCOMING STREAM` | `🔔 View Stream` |
| **YouTube Short** | `#shorts` | Amber Orange (`#FF7A00`) | `🩳 NEW SHORT` | `📱 Open Short` |
| **Standard Video** | `#videos` | Classic Red (`#CC0000`) | `🎬 NEW VIDEO` | `▶ Watch Video` |
| **Stream Replay / VOD** | `#live-streams` | Purple (`#8E24AA`) | `📼 STREAM REPLAY / VOD` | `▶ Watch Stream VOD` |

---

## 🏗️ Architecture & Flow

```
[YouTube Creator Publishes Content]
       │
       ├──► 1. Google WebSub Webhook ──► /youtube/webhook (AioHTTP) ──┐
       │                                                              │
       └──► 2. Android Phone Push    ──► mtalk.google.com:5228        │
                 (Node FCM Client)   ──► /fcm/notify                 ──┤
                                                                      ▼
                                                         [Event-Triggered Classifier]
                                                         • Checks Live / VOD / Shorts
                                                         • Inspects duration & metadata
                                                                      ▼
                                                         [SQLite Deduplication]
                                                         • Already posted? Ignore cleanly
                                                         • First time? Save & proceed
                                                                      ▼
                                                         [Smart Channel Dispatch]
                                                         ├─ Live ──► #live-streams
                                                         ├─ Short ─► #shorts
                                                         └─ Video ─► #videos
```

---

## 📁 Project Structure

```
Discord Bot/
├── cogs/
│   ├── youtube.py            # Event-driven push notification cog & channel router
│   └── general.py            # Utility event listeners
├── database/
│   └── db.py                 # Async SQLite manager (subscriptions, deduplication history)
├── services/
│   ├── fcm_receiver/         # Node.js persistent FCM socket receiver (mtalk.google.com)
│   │   ├── index.js          # Persistent FCM listener & bridge to Discord bot
│   │   └── package.json      # Push receiver dependencies
│   ├── websub.py             # Google WebSub (PubSubHubbub) webhook server
│   └── youtube_detector.py   # Event-triggered classifier (InnerTube JSON & Shorts probe)
├── utils/
│   └── embeds.py             # Rich Discord embeds & action buttons
├── config.py                 # Configuration loader from .env
├── main.py                   # Discord client startup & lifecycle
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
└── README.md
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- **Python 3.10+** (Python 3.14 tested)
- **Node.js 18+** (for the optional FCM push receiver)
- A **Discord Bot Token** ([Discord Developer Portal](https://discord.com/developers/applications))

### 2. Configure Environment (`.env`)
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Fill in your configuration:
```env
# Discord Bot Token
DISCORD_TOKEN=your_token_here

# Target YouTube Creators (comma-separated handles)
AUTO_TRACK_CHANNELS=@MissjeyGaming, @sig07, @DirectionerGaming

# Public Webhook URL (Cloudflare Tunnel or VPS Domain)
CALLBACK_URL=https://your-domain.com
WEBHOOK_PORT=8080
```

### 3. Run the Bot
```powershell
# Activate virtual environment
.\venv\Scripts\activate

# Run Python Bot
python main.py
```

### 4. (Optional) Run the FCM Push Receiver
In a separate terminal or service:
```powershell
cd services/fcm_receiver
npm install
node index.js
```

---

## 🌐 Production & Cloudflare Tunnel Setup

To give your local bot or VPS a permanent, secure HTTPS webhook endpoint:

1. Install Cloudflare Tunnel (`cloudflared`).
2. Run a named tunnel pointing to port 8080:
   ```bash
   cloudflared tunnel run <your-tunnel-name>
   ```
3. Set your public HTTPS address in `.env`:
   ```env
   CALLBACK_URL=https://webhook.yourdomain.com
   ```
Google WebSub will automatically verify the challenge and push events with 99.9% uptime.
