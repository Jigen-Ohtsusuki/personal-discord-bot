import asyncio
import logging
import time
import hashlib
import re
from typing import Callable, Optional, Dict, Any, List
import aiohttp
import config

logger = logging.getLogger("AccountStream")

class YouTubeAccountStream:
    """
    Listens to YouTube's authenticated notification bell feed for the configured account.
    Serves as an independent secondary stream alongside WebSub.
    """
    def __init__(self, callback_handler: Optional[Callable[[str, str], Any]] = None):
        self.callback_handler = callback_handler
        self.cookie = getattr(config, "YOUTUBE_COOKIE", "").strip()
        self.sapisid = self._extract_sapisid(self.cookie)
        self.task: Optional[asyncio.Task] = None
        self.running = False

    def _extract_sapisid(self, cookie: str) -> Optional[str]:
        m = re.search(r'(?:SAPISID|__Secure-3PAPISID)=([^;]+)', cookie)
        return m.group(1).strip() if m else None

    def _get_auth_headers(self) -> Dict[str, str]:
        if not self.sapisid or not self.cookie:
            return {}
        origin = 'https://www.youtube.com'
        curr_time = str(int(time.time()))
        sapisid_hash = hashlib.sha1(f'{curr_time} {self.sapisid} {origin}'.encode()).hexdigest()
        auth_header = f'SAPISIDHASH {curr_time}_{sapisid_hash}'
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Cookie': self.cookie,
            'Authorization': auth_header,
            'X-Origin': origin,
            'Content-Type': 'application/json',
            'X-YouTube-Client-Name': '1',
            'X-YouTube-Client-Version': '2.20241030.01.00'
        }

    async def start(self):
        if not self.cookie or not self.sapisid:
            logger.info("YOUTUBE_COOKIE not set. Account notification stream disabled.")
            return
        self.running = True
        logger.info("🔔 Authenticated YouTube Account Bell Stream active.")

    async def stop(self):
        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()

    async def fetch_latest_bell_notifications(self) -> List[Dict[str, str]]:
        """
        Fetches incoming notifications from YouTube's get_notification_menu endpoint.
        Returns a list of dicts with video_id, channel_id, and title.
        """
        headers = self._get_auth_headers()
        if not headers:
            return []

        url = "https://www.youtube.com/youtubei/v1/notification/get_notification_menu"
        payload = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20241030.01.00",
                    "hl": "en",
                    "gl": "US"
                }
            },
            "notificationsMenuRequestType": "NOTIFICATIONS_MENU_REQUEST_TYPE_REGULAR"
        }

        events: List[Dict[str, str]] = []
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        actions = data.get("actions", [])
                        for a in actions:
                            menu = a.get("openPopupAction", {}).get("popup", {}).get("multiPageMenuRenderer", {})
                            sections = menu.get("sections", [])
                            for sec in sections:
                                items = sec.get("multiPageMenuNotificationSectionRenderer", {}).get("items", [])
                                for it in items:
                                    nr = it.get("notificationRenderer", {})
                                    cmd = nr.get("navigationEndpoint", {}).get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", "")
                                    v_match = re.search(r'(?:watch\?v=|shorts/)([a-zA-Z0-9_-]{11})', cmd)
                                    if v_match:
                                        vid = v_match.group(1)
                                        title = "".join([r.get("text", "") for r in nr.get("shortMessage", {}).get("runs", [])])
                                        events.append({"video_id": vid, "title": title, "url": cmd})
        except Exception as e:
            logger.debug(f"Error fetching account notification menu: {e}")

        return events
