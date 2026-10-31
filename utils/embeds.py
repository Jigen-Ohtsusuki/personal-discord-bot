import html
import discord
from typing import Optional, Tuple
from services.youtube_detector import VideoType, YouTubeVideo

# Distinct styling definitions per content type
TYPE_STYLING = {
    VideoType.UPCOMING: {
        "title_badge": "📅 SCHEDULED LIVE STREAM",
        "embed_color": 0xF1C40F,  # Warm Gold / Calendar Yellow
        "default_text": "⏰ **{creator}** just scheduled an upcoming live stream! Mark your calendars:",
        "footer_text": "Jey's Bot 💜 • Scheduled Stream",
        "button_label": "⏰ Set Reminder / View",
        "emoji": "📅"
    },
    VideoType.LIVE: {
        "title_badge": "🔴 LIVE NOW",
        "embed_color": 0xFF0033,  # Vibrant Live Red
        "default_text": "🚨 **{creator}** is **LIVE** right now! Jump in and join the chat!",
        "footer_text": "Jey's Bot 💜 • Live Stream Alert",
        "button_label": "▶ Watch Live Stream",
        "emoji": "🔴"
    },
    VideoType.SHORTS: {
        "title_badge": "🩳 NEW SHORT",
        "embed_color": 0xFF5722,  # Short Orange-Red
        "default_text": "⚡ **{creator}** dropped a new YouTube Short! Check it out below:",
        "footer_text": "Jey's Bot 💜 • YouTube Shorts",
        "button_label": "📱 Open Short",
        "emoji": "🩳"
    },
    VideoType.VIDEO: {
        "title_badge": "🎬 NEW VIDEO",
        "embed_color": 0xCC0000,  # YouTube Red
        "default_text": "🍿 **{creator}** just uploaded a brand new video!",
        "footer_text": "Jey's Bot 💜 • Video Alert",
        "button_label": "▶ Watch Video",
        "emoji": "🎬"
    },
    VideoType.LIVE_VOD: {
        "title_badge": "📼 STREAM REPLAY / VOD",
        "embed_color": 0x8E24AA,  # Stream Purple
        "default_text": "📼 Missed the live stream? The replay for **{creator}**'s stream is ready to watch!",
        "footer_text": "Jey's Bot 💜 • Stream Replay Archive",
        "button_label": "▶ Watch Stream VOD",
        "emoji": "📼"
    }
}

class YouTubeActionView(discord.ui.View):
    """Interactive Discord buttons attached to YouTube notifications."""
    def __init__(self, video_url: str, channel_url: str, button_label: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=button_label, style=discord.ButtonStyle.link, url=video_url))
        self.add_item(discord.ui.Button(label="📺 Visit Channel", style=discord.ButtonStyle.link, url=channel_url))

def create_notification_embed(
    video: YouTubeVideo,
    ping_role_id: Optional[str] = None,
    custom_message_template: Optional[str] = None
) -> Tuple[Optional[str], discord.Embed, YouTubeActionView]:
    """
    Builds the formatted alert message, rich embed, and button view for a YouTube video.
    Returns: (content_ping_str, embed, view)
    """
    style = TYPE_STYLING.get(video.video_type, TYPE_STYLING[VideoType.VIDEO])

    # 1. Format the ping text above the embed
    ping_prefix = f"<@&{ping_role_id}> " if (ping_role_id and ping_role_id != "everyone" and ping_role_id != "@everyone") else ("@everyone " if ping_role_id in ["everyone", "@everyone"] else "")

    if custom_message_template:
        formatted_message = custom_message_template.format(
            creator=video.channel_title,
            title=video.title,
            url=video.url,
            type=style["title_badge"],
            role=ping_prefix.strip()
        )
        content_text = f"{ping_prefix}{formatted_message}" if (ping_prefix and ping_prefix not in formatted_message) else formatted_message
    else:
        content_text = f"{ping_prefix}{style['default_text'].format(creator=video.channel_title)}"

    # 2. Build the Embed
    clean_title = html.unescape(video.title)
    embed = discord.Embed(
        title=clean_title,
        url=video.url,
        color=style["embed_color"]
    )

    # Author header with distinct badge
    embed.set_author(
        name=f"[{style['title_badge']}] {video.channel_title}",
        url=f"https://www.youtube.com/channel/{video.channel_id}",
        icon_url="https://cdn-icons-png.flaticon.com/512/1384/1384060.png"
    )

    # Description excerpt (clean, max 200 chars)
    if video.description:
        desc_clean = html.unescape(video.description.strip())
        if len(desc_clean) > 200:
            desc_clean = desc_clean[:197] + "..."
        embed.description = desc_clean

    # Thumbnail
    if video.thumbnail_url:
        embed.set_image(url=video.thumbnail_url)

    # Fields
    embed.add_field(name="Category", value=f"`{style['title_badge']}`", inline=True)
    embed.add_field(name="Channel", value=f"[{video.channel_title}](https://www.youtube.com/channel/{video.channel_id})", inline=True)
    if video.published_at:
        embed.add_field(name="Published", value=f"`{video.published_at[:10]}`" if len(video.published_at) >= 10 else "Recently", inline=True)

    # Footer
    embed.set_footer(
        text=style["footer_text"],
        icon_url="https://cdn-icons-png.flaticon.com/512/1384/1384060.png"
    )

    # View Buttons
    channel_url = f"https://www.youtube.com/channel/{video.channel_id}"
    view = YouTubeActionView(
        video_url=video.url,
        channel_url=channel_url,
        button_label=style["button_label"]
    )

    return content_text.strip(), embed, view
