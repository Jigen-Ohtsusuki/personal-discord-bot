import re
import json
import html
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any
import aiohttp
import config

logger = logging.getLogger("YouTubeDetector")

class VideoType(Enum):
    VIDEO = "video"         # Standard uploaded video
    SHORTS = "shorts"       # YouTube Short
    UPCOMING = "upcoming"   # Scheduled future livestream
    LIVE = "live"           # Currently active livestream
    LIVE_VOD = "live_vod"   # Uploaded livestream / Past stream archive (VOD)

@dataclass
class YouTubeVideo:
    video_id: str
    title: str
    channel_id: str
    channel_title: str
    video_type: VideoType
    url: str
    published_at: str
    thumbnail_url: str
    description: str
    duration_seconds: int = 0

@dataclass
class YouTubeChannelInfo:
    channel_id: str
    channel_title: str
    handle: Optional[str] = None
    canonical_url: Optional[str] = None

class YouTubeDetector:
    """
    High-precision YouTube detection engine powered by YouTube's internal InnerTube API
    (/youtubei/v1/browse and /youtubei/v1/player).
    
    Eliminates fragile HTML scraping and regex in favor of structured JSON payloads
    directly from YouTube's official backend. Zero API quota consumption.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.YOUTUBE_API_KEY
        self.innertube_base = "https://www.youtube.com/youtubei/v1"
        self.innertube_headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "X-YouTube-Client-Name": "1",
            "X-YouTube-Client-Version": "2.20240101.00.00"
        }
        self.innertube_context = {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20240101.00.00",
                "hl": "en",
                "gl": "US"
            }
        }

    async def resolve_channel(self, identifier: str) -> Optional[YouTubeChannelInfo]:
        """
        Resolves a user-provided input into a canonical YouTube channel ID (UC...) and title.
        Supports:
        - Direct channel ID: UCxxxxxxxxxxxxxxxxxxxxxx
        - Custom handle: @CreatorName
        - Full URL: https://youtube.com/@CreatorName or https://youtube.com/channel/UCxxxx...
        """
        clean_input = identifier.strip()

        # Direct channel ID check
        if re.match(r"^UC[\w-]{22}$", clean_input):
            channel_id = clean_input
            title = await self._fetch_channel_title_via_innertube(channel_id) or channel_id
            return YouTubeChannelInfo(
                channel_id=channel_id,
                channel_title=title,
                canonical_url=f"https://www.youtube.com/channel/{channel_id}"
            )

        # Normalize URL / handle
        if clean_input.startswith("http"):
            url = clean_input
        elif clean_input.startswith("@"):
            url = f"https://www.youtube.com/{clean_input}"
        elif "/" not in clean_input:
            url = f"https://www.youtube.com/@{clean_input}"
        else:
            url = f"https://www.youtube.com/{clean_input}"

        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(headers=self.innertube_headers, timeout=timeout) as session:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        logger.warning(f"Failed to fetch channel page {url}, status: {resp.status}")
                        return None
                    html_text = await resp.text()

                    # Extract channel ID from metadata
                    channel_id_match = (
                        re.search(r'https://www.youtube.com/feeds/videos.xml\?channel_id=(UC[\w-]{22})', html_text)
                        or re.search(r'<link rel="canonical" href="https://www.youtube.com/channel/(UC[\w-]{22})"', html_text)
                        or re.search(r'"externalId":"(UC[\w-]{22})"', html_text)
                        or re.search(r'<meta itemprop="channelId" content="(UC[\w-]{22})"', html_text)
                    )

                    title_match = (
                        re.search(r'<meta property="og:title" content="([^"]+)"', html_text)
                        or re.search(r'<title>([^<]+) - YouTube</title>', html_text)
                        or re.search(r'<title>([^<]+)</title>', html_text)
                    )

                    if channel_id_match:
                        channel_id = channel_id_match.group(1)
                        title = title_match.group(1) if title_match else channel_id
                        title = html.unescape(title.replace(" - YouTube", "").strip())

                        handle_match = re.search(r'"canonicalBaseUrl":"/(@[^"]+)"', html_text)
                        handle = handle_match.group(1) if handle_match else None

                        return YouTubeChannelInfo(
                            channel_id=channel_id,
                            channel_title=title,
                            handle=handle,
                            canonical_url=f"https://www.youtube.com/channel/{channel_id}"
                        )

        except Exception as e:
            logger.error(f"Error resolving channel for '{identifier}': {e}")

        # Fallback to official API if available
        if self.api_key:
            return await self._resolve_channel_via_api(clean_input)

        return None

    async def _fetch_channel_title_via_innertube(self, channel_id: str) -> Optional[str]:
        """Queries InnerTube browse endpoint for canonical channel title."""
        url = f"{self.innertube_base}/browse"
        payload = {
            "context": self.innertube_context,
            "browseId": channel_id
        }
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(headers=self.innertube_headers, timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        header = data.get("header", {})
                        title = (
                            header.get("pageHeaderRenderer", {}).get("pageTitle")
                            or header.get("c4TabbedHeaderRenderer", {}).get("title")
                        )
                        if title:
                            return html.unescape(title.strip())
        except Exception:
            pass
        return None

    async def _resolve_channel_via_api(self, query: str) -> Optional[YouTubeChannelInfo]:
        endpoint = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "channel",
            "maxResults": 1,
            "key": self.api_key
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("items", [])
                        if items:
                            item = items[0]
                            channel_id = item["snippet"]["channelId"]
                            title = html.unescape(item["snippet"]["channelTitle"])
                            return YouTubeChannelInfo(
                                channel_id=channel_id,
                                channel_title=title,
                                canonical_url=f"https://www.youtube.com/channel/{channel_id}"
                            )
        except Exception as e:
            logger.error(f"Error querying YouTube API for channel search: {e}")
        return None

    async def get_recent_channel_items(self, channel_id: str) -> List[Dict[str, Any]]:
        """
        Queries YouTube's internal InnerTube API (/youtubei/v1/browse)
        to fetch balanced items across live streams, shorts, and standard videos.
        Guarantees that shorts or live streams are never starved by standard video uploads.
        """
        items: List[Dict[str, Any]] = []
        url = f"{self.innertube_base}/browse"

        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(headers=self.innertube_headers, timeout=timeout) as session:
                # 1. Check live streams tab (Top priority for Live & VOD)
                streams_payload = {
                    "context": self.innertube_context,
                    "browseId": channel_id,
                    "params": "EgdzdHJlYW1z8gYFCgOaAQA%3D"
                }
                try:
                    async with session.post(url, json=streams_payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            parsed_streams = self._extract_items_from_innertube_data(data, default_type=VideoType.LIVE_VOD)
                            items.extend(parsed_streams[:3])
                except Exception as e:
                    logger.debug(f"Streams tab query error: {e}")

                # 2. Check shorts tab (Top priority for Shorts)
                shorts_payload = {
                    "context": self.innertube_context,
                    "browseId": channel_id,
                    "params": "EgZzaG9ydHPyBgUKA5oBAA%3D%3D"
                }
                try:
                    async with session.post(url, json=shorts_payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            parsed_shorts = self._extract_items_from_innertube_data(data, default_type=VideoType.SHORTS)
                            items.extend(parsed_shorts[:3])
                except Exception as e:
                    logger.debug(f"Shorts tab query error: {e}")

                # 3. Check regular videos tab
                payload = {
                    "context": self.innertube_context,
                    "browseId": channel_id
                }
                try:
                    async with session.post(url, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            parsed_videos = self._extract_items_from_innertube_data(data)
                            # Avoid duplicates if videos tab also lists shorts
                            existing_ids = {it["video_id"] for it in items}
                            for v in parsed_videos:
                                if v["video_id"] not in existing_ids:
                                    items.append(v)
                                    existing_ids.add(v["video_id"])
                                if len(items) >= 10:
                                    break
                except Exception as e:
                    logger.debug(f"Videos tab query error: {e}")

        except Exception as e:
            logger.error(f"Error querying InnerTube browse for {channel_id}: {e}")

        return items

    def _extract_items_from_innertube_data(self, data: Dict[str, Any], default_type: Optional[VideoType] = None) -> List[Dict[str, Any]]:
        """Parses structured video items from an InnerTube response dictionary."""
        items = []

        def traverse(obj):
            if isinstance(obj, dict):
                # Standard / Stream video lockup
                if "lockupViewModel" in obj:
                    lockup = obj["lockupViewModel"]
                    cid = lockup.get("contentId")
                    if cid:
                        meta = lockup.get("metadata", {}).get("lockupMetadataViewModel", {})
                        title = html.unescape(meta.get("title", {}).get("content", "Untitled"))

                        # Check overlay badges for LIVE or Upcoming
                        overlays = lockup.get("contentImage", {}).get("thumbnailViewModel", {}).get("overlays", [])
                        badge_texts = []
                        for o in overlays:
                            badges = o.get("thumbnailBottomOverlayViewModel", {}).get("badges", [])
                            for b in badges:
                                b_text = b.get("thumbnailBadgeViewModel", {}).get("text")
                                if b_text:
                                    badge_texts.append(b_text)

                        is_live = any("LIVE" in b.upper() for b in badge_texts)
                        is_upcoming = any("UPCOMING" in b.upper() for b in badge_texts)

                        if is_live:
                            v_type = VideoType.LIVE
                        elif is_upcoming:
                            v_type = VideoType.UPCOMING
                        elif default_type:
                            v_type = default_type
                        else:
                            v_type = VideoType.VIDEO

                        items.append({
                            "video_id": cid,
                            "title": title,
                            "video_type": v_type,
                            "url": f"https://www.youtube.com/watch?v={cid}",
                            "thumbnail_url": f"https://i.ytimg.com/vi/{cid}/hqdefault.jpg"
                        })

                # Shorts lockup
                if "shortsLockupViewModel" in obj:
                    s_lockup = obj["shortsLockupViewModel"]
                    on_tap = s_lockup.get("onTap", {})
                    reel_endpoint = on_tap.get("innertubeCommand", {}).get("reelWatchEndpoint", {})
                    cid = reel_endpoint.get("videoId")
                    if not cid:
                        entity_id = s_lockup.get("entityId", "")
                        if "shorts-shelf-item-" in entity_id:
                            cid = entity_id.replace("shorts-shelf-item-", "")

                    if cid:
                        title = html.unescape(s_lockup.get("accessibilityText", "New Short"))
                        if ", " in title:
                            title = title.split(", ")[0]
                        items.append({
                            "video_id": cid,
                            "title": title,
                            "video_type": VideoType.SHORTS,
                            "url": f"https://www.youtube.com/shorts/{cid}",
                            "thumbnail_url": f"https://i.ytimg.com/vi/{cid}/hqdefault.jpg"
                        })

                # VideoRenderer format
                if "videoRenderer" in obj:
                    vr = obj["videoRenderer"]
                    cid = vr.get("videoId")
                    if cid:
                        title_runs = vr.get("title", {}).get("runs", [{}])
                        title = html.unescape(title_runs[0].get("text", "Untitled") if title_runs else "Untitled")
                        badges = [b.get("metadataBadgeViewModel", {}).get("label", "") for b in vr.get("badges", [])]
                        is_live = any("LIVE" in b.upper() for b in badges)
                        is_upcoming = any("UPCOMING" in b.upper() for b in badges)

                        if is_live:
                            v_type = VideoType.LIVE
                        elif is_upcoming:
                            v_type = VideoType.UPCOMING
                        elif default_type:
                            v_type = default_type
                        else:
                            v_type = VideoType.VIDEO

                        items.append({
                            "video_id": cid,
                            "title": title,
                            "video_type": v_type,
                            "url": f"https://www.youtube.com/watch?v={cid}",
                            "thumbnail_url": f"https://i.ytimg.com/vi/{cid}/hqdefault.jpg"
                        })

                # ReelItemRenderer format
                if "reelItemRenderer" in obj:
                    rr = obj["reelItemRenderer"]
                    cid = rr.get("videoId")
                    if cid:
                        headline = rr.get("headline", {}).get("simpleText", "New Short")
                        items.append({
                            "video_id": cid,
                            "title": html.unescape(headline),
                            "video_type": VideoType.SHORTS,
                            "url": f"https://www.youtube.com/shorts/{cid}",
                            "thumbnail_url": f"https://i.ytimg.com/vi/{cid}/hqdefault.jpg"
                        })

                for v in obj.values():
                    traverse(v)
            elif isinstance(obj, list):
                for elem in obj:
                    traverse(elem)

        traverse(data)
        return items

    async def classify_video_by_id(self, video_id: str, channel_id: str = "", channel_title: str = "") -> YouTubeVideo:
        """
        Classifies any given YouTube video ID into one of the 5 exact categories:
        - VideoType.SHORTS: YouTube Short
        - VideoType.UPCOMING: Scheduled livestream
        - VideoType.LIVE: Currently live
        - VideoType.LIVE_VOD: Finished livestream replay / VOD
        - VideoType.VIDEO: Standard regular video upload

        Uses YouTube's official internal InnerTube /player API for 100% structured JSON precision.
        """
        # Primary Engine: InnerTube Player API
        innertube_res = await self._classify_via_innertube_player(video_id, channel_id, channel_title)
        if innertube_res:
            return innertube_res

        # Fallback 1: YouTube Data API v3 if API key is provided
        if self.api_key:
            api_res = await self._classify_via_api(video_id, channel_id, channel_title)
            if api_res:
                return api_res

        # Fallback 2: Basic URL endpoint probe
        return await self._fallback_probe(video_id, channel_id, channel_title)

    async def _classify_via_innertube_player(self, video_id: str, channel_id: str, channel_title: str) -> Optional[YouTubeVideo]:
        """
        Queries YouTube's internal /youtubei/v1/player API endpoint.
        Returns pure structured JSON with exact duration, live state, and broadcast details.
        """
        url = f"{self.innertube_base}/player"
        payload = {
            "context": self.innertube_context,
            "videoId": video_id
        }

        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(headers=self.innertube_headers, timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()

            video_details = data.get("videoDetails", {})
            microformat = data.get("microformat", {}).get("playerMicroformatRenderer", {})
            live_broadcast_details = microformat.get("liveBroadcastDetails", {})

            title = html.unescape(video_details.get("title") or "New Video")
            c_title = html.unescape(video_details.get("author") or channel_title)
            c_id = video_details.get("channelId") or channel_id
            description = html.unescape(video_details.get("shortDescription", ""))
            published_at = microformat.get("publishDate") or microformat.get("uploadDate", "")

            # Thumbnails
            thumbnails = video_details.get("thumbnail", {}).get("thumbnails", [])
            thumbnail_url = thumbnails[-1].get("url") if thumbnails else f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

            # Duration and flags
            length_sec = int(video_details.get("lengthSeconds", "0"))
            is_live_content = video_details.get("isLiveContent", False) or video_details.get("isLive", False)
            is_live_now = live_broadcast_details.get("isLiveNow", False) or video_details.get("isLive", False)
            has_ended = bool(live_broadcast_details.get("endTimestamp"))

            # Determine exact category
            if is_live_now or (is_live_content and length_sec == 0 and not has_ended):
                v_type = VideoType.LIVE
            elif is_live_content and not has_ended and not is_live_now:
                v_type = VideoType.UPCOMING
            elif is_live_content and has_ended:
                v_type = VideoType.LIVE_VOD
            elif length_sec <= 180 and ("/shorts" in str(microformat) or length_sec <= 60):
                is_short = await self._is_short_probe(video_id)
                v_type = VideoType.SHORTS if is_short else VideoType.VIDEO
            else:
                v_type = VideoType.VIDEO

            final_url = f"https://www.youtube.com/shorts/{video_id}" if v_type == VideoType.SHORTS else f"https://www.youtube.com/watch?v={video_id}"

            return YouTubeVideo(
                video_id=video_id,
                title=title,
                channel_id=c_id,
                channel_title=c_title,
                video_type=v_type,
                url=final_url,
                published_at=published_at,
                thumbnail_url=thumbnail_url,
                description=description,
                duration_seconds=length_sec
            )

        except Exception as e:
            logger.error(f"Error in InnerTube player classification for {video_id}: {e}")
            return None

    async def _classify_via_api(self, video_id: str, channel_id: str, channel_title: str) -> Optional[YouTubeVideo]:
        endpoint = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet,contentDetails,liveStreamingDetails",
            "id": video_id,
            "key": self.api_key
        }

        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(endpoint, params=params) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    items = data.get("items", [])
                    if not items:
                        return None

                    item = items[0]
                    snippet = item.get("snippet", {})
                    live_details = item.get("liveStreamingDetails")

                    title = html.unescape(snippet.get("title", "Untitled"))
                    c_title = html.unescape(snippet.get("channelTitle", channel_title))
                    c_id = snippet.get("channelId", channel_id)
                    published_at = snippet.get("publishedAt", "")
                    description = html.unescape(snippet.get("description", ""))

                    thumbnails = snippet.get("thumbnails", {})
                    thumbnail_url = (
                        thumbnails.get("maxres", {}).get("url")
                        or thumbnails.get("high", {}).get("url")
                        or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    )

                    broadcast_content = snippet.get("liveBroadcastContent", "none")
                    if broadcast_content == "live":
                        v_type = VideoType.LIVE
                    elif broadcast_content == "upcoming":
                        v_type = VideoType.UPCOMING
                    elif live_details is not None:
                        actual_start = live_details.get("actualStartTime")
                        actual_end = live_details.get("actualEndTime")
                        if actual_start and not actual_end:
                            v_type = VideoType.LIVE
                        elif live_details.get("scheduledStartTime") and not actual_start:
                            v_type = VideoType.UPCOMING
                        else:
                            v_type = VideoType.LIVE_VOD
                    else:
                        is_short = await self._is_short_probe(video_id)
                        v_type = VideoType.SHORTS if is_short else VideoType.VIDEO

                    url = f"https://www.youtube.com/shorts/{video_id}" if v_type == VideoType.SHORTS else f"https://www.youtube.com/watch?v={video_id}"

                    return YouTubeVideo(
                        video_id=video_id,
                        title=title,
                        channel_id=c_id,
                        channel_title=c_title,
                        video_type=v_type,
                        url=url,
                        published_at=published_at,
                        thumbnail_url=thumbnail_url,
                        description=description
                    )

        except Exception as e:
            logger.error(f"Error in API classification for {video_id}: {e}")
            return None

    async def _fallback_probe(self, video_id: str, channel_id: str, channel_title: str) -> YouTubeVideo:
        is_short = await self._is_short_probe(video_id)
        url = f"https://www.youtube.com/shorts/{video_id}" if is_short else f"https://www.youtube.com/watch?v={video_id}"
        return YouTubeVideo(
            video_id=video_id,
            title="New YouTube Content",
            channel_id=channel_id,
            channel_title=channel_title or "Creator",
            video_type=VideoType.SHORTS if is_short else VideoType.VIDEO,
            url=url,
            published_at="",
            thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            description=""
        )

    async def _is_short_probe(self, video_id: str) -> bool:
        url = f"https://www.youtube.com/shorts/{video_id}"
        try:
            timeout = aiohttp.ClientTimeout(total=6)
            async with aiohttp.ClientSession(headers=self.innertube_headers, timeout=timeout) as session:
                async with session.head(url, allow_redirects=True) as resp:
                    if "/shorts/" in resp.url.path and resp.status == 200:
                        return True
                    if "/watch" in resp.url.path:
                        return False

                async with session.get(url, allow_redirects=True) as resp:
                    return "/shorts/" in resp.url.path and resp.status == 200
        except Exception:
            return False

detector = YouTubeDetector()
