/**
 * Jey's Bot 💜 - Cloudflare 24/7 YouTube Notification Worker
 * 100% Free Forever • Zero Polling • Multi-Channel Routing
 */

// Target YouTube Creators
const CHANNELS = {
  "UC12_jnxFlORtx9JjrnHPalg": "MissJey",
  "UCdYi0XUhw5ANO96zeK70YfQ": "SIG07",
  "UCO6Yn9mmANIMTVhpcOeZczQ": "Directioner"
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. Google WebSub Verification Handshake (GET)
    if (request.method === "GET" && (url.pathname.endsWith("/webhook") || url.pathname.endsWith("/youtube/webhook"))) {
      const challenge = url.searchParams.get("hub.challenge");
      if (challenge) {
        return new Response(challenge, {
          status: 200,
          headers: { "Content-Type": "text/plain" }
        });
      }
      return new Response("No challenge provided", { status: 400 });
    }

    // 2. One-Click Subscription Helper (GET /subscribe)
    if (url.pathname.endsWith("/subscribe")) {
      const callbackUrl = `${url.origin}/youtube/webhook`;
      const results = [];
      for (const [channelId, name] of Object.entries(CHANNELS)) {
        const topicUrl = `https://www.youtube.com/xml/feeds/videos.xml?channel_id=${channelId}`;
        const formData = new URLSearchParams({
          "hub.callback": callbackUrl,
          "hub.mode": "subscribe",
          "hub.topic": topicUrl,
          "hub.verify": "async",
          "hub.lease_seconds": "864000" // 10 days
        });
        const res = await fetch("https://pubsubhubbub.appspot.com/subscribe", {
          method: "POST",
          body: formData,
          headers: { "Content-Type": "application/x-www-form-urlencoded" }
        });
        results.push(`${name} (${channelId}): HTTP ${res.status}`);
      }
      return new Response(`⚡ Subscribed to Google WebSub!\n\n` + results.join("\n"), {
        status: 200,
        headers: { "Content-Type": "text/plain" }
      });
    }

    // 3. Incoming Real-Time Push Notification (POST)
    if (request.method === "POST" && (url.pathname.endsWith("/webhook") || url.pathname.endsWith("/youtube/webhook"))) {
      const text = await request.text();
      
      const videoIdMatch = text.match(/<yt:videoId>(.*?)<\/yt:videoId>/);
      const channelIdMatch = text.match(/<yt:channelId>(.*?)<\/yt:channelId>/);
      const titleMatch = text.match(/<title>(.*?)<\/title>/g);

      if (videoIdMatch && channelIdMatch) {
        const videoId = videoIdMatch[1].trim();
        const channelId = channelIdMatch[1].trim();
        const title = titleMatch && titleMatch[1] ? titleMatch[1].replace(/<\/?title>/g, "").trim() : "New Content";
        const creator = CHANNELS[channelId] || "Creator";

        // Dispatch in background
        ctx.waitUntil(handleYouTubeEvent(videoId, channelId, title, creator, env));
      }

      // Always return 204 No Content to Google immediately
      return new Response(null, { status: 204 });
    }

    return new Response(
      "💜 Jey's Bot Cloudflare 24/7 Engine is LIVE!\nVisit /subscribe to register channels with Google WebSub.",
      { status: 200, headers: { "Content-Type": "text/plain" } }
    );
  }
};

async function handleYouTubeEvent(videoId, channelId, rawTitle, creator, env) {
  // Deduplication via Cloudflare Cache API (Zero DB needed!)
  const cacheKey = `https://cache.jeysbot.local/posted/${videoId}`;
  const cache = caches.default;
  const existing = await cache.match(cacheKey);
  if (existing) {
    console.log(`Video ${videoId} already posted. Skipping duplicate.`);
    return;
  }

  // 1. Classify Content (Shorts vs Video vs Live)
  let videoType = "VIDEO";
  let targetWebhook = env.DISCORD_WEBHOOK_VIDEOS;
  let embedColor = 0xCC0000;
  let badge = "🎬 NEW VIDEO";
  let buttonLabel = "▶ Watch Video";
  let videoUrl = `https://www.youtube.com/watch?v=${videoId}`;

  // Check if it's a Short (200 on /shorts/ID, 303 redirect for videos)
  try {
    const shortsRes = await fetch(`https://www.youtube.com/shorts/${videoId}`, { redirect: "manual" });
    if (shortsRes.status === 200) {
      videoType = "SHORTS";
      targetWebhook = env.DISCORD_WEBHOOK_SHORTS;
      embedColor = 0xFF5722;
      badge = "🩳 NEW SHORT";
      buttonLabel = "📱 Open Short";
      videoUrl = `https://www.youtube.com/shorts/${videoId}`;
    }
  } catch (e) {}

  // Check if it's a Live Stream via InnerTube
  if (videoType !== "SHORTS") {
    try {
      const playerRes = await fetch("https://www.youtube.com/youtubei/v1/player", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context: { client: { clientName: "WEB", clientVersion: "2.20241030.01.00" } },
          videoId: videoId
        })
      });
      if (playerRes.ok) {
        const pData = await playerRes.json();
        const liveDetails = pData?.microformat?.playerMicroformatRenderer?.liveBroadcastDetails;
        const isLiveNow = liveDetails?.isLiveNow;
        const isLiveContent = pData?.videoDetails?.isLiveContent;

        if (isLiveNow) {
          videoType = "LIVE";
          targetWebhook = env.DISCORD_WEBHOOK_LIVE;
          embedColor = 0xFF0033;
          badge = "🔴 LIVE NOW";
          buttonLabel = "▶ Watch Live Stream";
        } else if (isLiveContent && !liveDetails?.endTimestamp) {
          videoType = "UPCOMING";
          targetWebhook = env.DISCORD_WEBHOOK_LIVE;
          embedColor = 0xF1C40F;
          badge = "📅 SCHEDULED STREAM";
          buttonLabel = "⏰ Set Reminder / View";
        }
      }
    } catch (e) {}
  }

  if (!targetWebhook) {
    console.error(`No webhook URL configured for type ${videoType}`);
    return;
  }

  // 2. Format Rich Discord Embed
  const embed = {
    title: `${badge} • ${rawTitle}`,
    url: videoUrl,
    color: embedColor,
    author: {
      name: creator,
      url: `https://www.youtube.com/channel/${channelId}`,
      icon_url: "https://i.ytimg.com/vi/" + videoId + "/hqdefault.jpg"
    },
    image: {
      url: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`
    },
    footer: {
      text: "Jey's Bot 💜 • 24/7 Cloudflare Engine",
      icon_url: "https://i.ytimg.com/vi/" + videoId + "/hqdefault.jpg"
    },
    timestamp: new Date().toISOString()
  };

  const discordPayload = {
    username: "Jey's Bot 💜",
    avatar_url: "https://i.ytimg.com/vi/" + videoId + "/hqdefault.jpg",
    content: `🚨 **${creator}** just posted a new **${videoType}**! Check it out below:\n${videoUrl}`,
    embeds: [embed]
  };

  const res = await fetch(targetWebhook, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(discordPayload)
  });

  if (res.ok) {
    // Mark as posted in Cache for 7 days (604800 seconds)
    const cacheResponse = new Response("1", {
      headers: { "Cache-Control": "max-age=604800" }
    });
    await cache.put(cacheKey, cacheResponse);
    console.log(`Successfully posted ${videoId} (${videoType}) to Discord!`);
  } else {
    console.error(`Failed to post to Discord: ${res.status}`);
  }
}
