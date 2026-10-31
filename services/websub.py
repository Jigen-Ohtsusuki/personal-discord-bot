import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from typing import Callable, Optional, Dict, Any
from aiohttp import web
import aiohttp
import config

logger = logging.getLogger("WebSub")

HUB_URL = "https://pubsubhubbub.appspot.com/subscribe"

class WebSubManager:
    """
    Manages Google PubSubHubbub (WebSub) push notifications for YouTube.
    When a public CALLBACK_URL is provided, YouTube pushes notifications to the bot
    within seconds of a video upload or stream start (Zero Polling Delay).
    """
    def __init__(self, callback_handler: Optional[Callable[[str, str], Any]] = None):
        self.callback_handler = callback_handler
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.callback_url = getattr(config, "CALLBACK_URL", "").strip().rstrip("/")
        self.port = int(getattr(config, "WEBHOOK_PORT", 8080))
        self.secret = getattr(config, "WEBHOOK_SECRET", "").strip()

        # Routes
        self.app.router.add_get("/youtube/webhook", self._handle_get)
        self.app.router.add_post("/youtube/webhook", self._handle_post)
        self.app.router.add_post("/fcm/notify", self._handle_fcm_notify)

    async def start(self):
        """Starts the local aiohttp webhook server to receive push notifications."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await self.site.start()
        logger.info(f"WebSub Webhook Server listening on port {self.port}")
        if self.callback_url:
            logger.info(f"WebSub Public Endpoint: {self.callback_url}/youtube/webhook (Instant Push Active)")
        else:
            logger.info("CALLBACK_URL not set in .env. WebSub server active locally. Polling fallback will operate.")

    async def renew_all_subscriptions(self, channel_ids: list):
        """Automatically renews all active YouTube channel subscriptions before the 10-day lease expires."""
        if not self.callback_url or not channel_ids:
            return
        logger.info(f"🔄 Renewing WebSub push leases for {len(channel_ids)} channels...")
        for cid in channel_ids:
            await self.subscribe_channel(cid)
            await asyncio.sleep(0.5)

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()

    async def subscribe_channel(self, channel_id: str) -> bool:
        """Sends a subscription request to Google's PubSubHubbub hub."""
        if not self.callback_url:
            return False

        topic_url = f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"
        full_callback = f"{self.callback_url}/youtube/webhook"

        payload = {
            "hub.callback": full_callback,
            "hub.mode": "subscribe",
            "hub.topic": topic_url,
            "hub.verify": "async",
            "hub.lease_seconds": "864000"  # 10 days
        }
        if self.secret:
            payload["hub.secret"] = self.secret

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(HUB_URL, data=payload) as resp:
                    if resp.status in [200, 202, 204]:
                        logger.info(f"Sent WebSub subscribe request for channel {channel_id} (Status: {resp.status})")
                        return True
                    else:
                        text = await resp.text()
                        logger.warning(f"WebSub subscribe failed for {channel_id}: {resp.status} - {text}")
        except Exception as e:
            logger.error(f"Error subscribing to WebSub for {channel_id}: {e}")

        return False

    async def unsubscribe_channel(self, channel_id: str) -> bool:
        """Sends an unsubscription request to Google's PubSubHubbub hub."""
        if not self.callback_url:
            return False

        topic_url = f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"
        full_callback = f"{self.callback_url}/youtube/webhook"

        payload = {
            "hub.callback": full_callback,
            "hub.mode": "unsubscribe",
            "hub.topic": topic_url,
            "hub.verify": "async"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(HUB_URL, data=payload) as resp:
                    return resp.status in [200, 202, 204]
        except Exception:
            return False

    async def _handle_get(self, request: web.Request) -> web.Response:
        """
        Handles the Google WebSub verification challenge.
        Google sends a GET request with hub.challenge, which must be echoed back with HTTP 200.
        """
        params = request.query
        challenge = params.get("hub.challenge")
        mode = params.get("hub.mode")
        topic = params.get("hub.topic")

        if challenge:
            logger.info(f"Verified WebSub challenge for topic: {topic} (mode: {mode})")
            return web.Response(text=challenge, status=200, content_type="text/plain")

        return web.Response(text="No challenge provided", status=400)

    async def _handle_post(self, request: web.Request) -> web.Response:
        """
        Handles incoming real-time notifications from Google's hub when a video is published or goes live.
        """
        body = await request.text()
        try:
            # Parse Atom XML
            root = ET.fromstring(body)
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "yt": "http://www.youtube.com/xml/schemas/2015"
            }

            for entry in root.findall("atom:entry", ns):
                video_id_el = entry.find("yt:videoId", ns)
                channel_id_el = entry.find("yt:channelId", ns)

                if video_id_el is not None and video_id_el.text:
                    video_id = video_id_el.text.strip()
                    channel_id = channel_id_el.text.strip() if (channel_id_el is not None and channel_id_el.text) else ""

                    logger.info(f"⚡ Instant WebSub push received: Video {video_id} on Channel {channel_id}")

                    # Dispatch event to Discord bot
                    if self.callback_handler:
                        asyncio.create_task(self.callback_handler(video_id, channel_id))

        except Exception as e:
            logger.error(f"Error parsing incoming WebSub payload: {e}")

        # Always return 200 or 204 to Google to acknowledge receipt
        return web.Response(status=204)

    async def _handle_fcm_notify(self, request: web.Request) -> web.Response:
        """
        Receives instant phone push notifications forwarded from the FCM push receiver client.
        """
        try:
            data = await request.json()
            video_id = data.get("video_id")
            channel_id = data.get("channel_id", "")
            if video_id and self.callback_handler:
                logger.info(f"📱 [FCM Mobile Push] Received video alert: {video_id}")
                asyncio.create_task(self.callback_handler(video_id, channel_id))
                return web.json_response({"status": "received", "video_id": video_id})
        except Exception as e:
            logger.error(f"Error handling incoming FCM notification: {e}")
        return web.json_response({"status": "error"}, status=400)
