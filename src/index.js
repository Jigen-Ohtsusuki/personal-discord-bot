/**
 * Jey's Bot 💜 - 24/7 Cloudflare YouTube Engine
 * 100% Free Forever • Zero Polling • Lively & Production-Grade
 */

// Target YouTube Creators
const CREATORS = {
  "UC12_jnxFlORtx9JjrnHPalg": "MissJey",
  "UCdYi0XUhw5ANO96zeK70YfQ": "SIG07",
  "UCO6Yn9mmANIMTVhpcOeZczQ": "Directioner"
};

// Discord Channel Routing
const DISCORD_CHANNELS = {
  LIVE: "1566020837151211671",    // #live-streams
  VIDEOS: "1566020914787651586",  // #videos
  SHORTS: "1566021006961811586"   // #shorts
};

// Lively, rotating community shoutouts
const LIVELY_MESSAGES = {
  LIVE: [
    "🔥 Wake up community! **{creator}** is **LIVE** right now! Grab your snacks and jump in 💜",
    "🚨 Stop scrolling! **{creator}** just hit the **GO LIVE** button! Get in the chat 🔥",
    "🎮 Game faces on! **{creator}** is streaming live right now! Come hang out and show some love 💜",
    "💜 The stream is LIVE! **{creator}** is in the lobby! Tap the button below to join the hype 🚀"
  ],
  UPCOMING: [
    "⏰ Mark your calendars! **{creator}** just scheduled a new live stream! Set your reminders 🎯",
    "📅 Upcoming stream alert! **{creator}** planned a new stream! Check the countdown below 💜",
    "🔔 Don't miss it! **{creator}** scheduled a live session! Drop a reminder so you are there on time 🔥"
  ],
  SHORTS: [
    "⚡ Quick bite! **{creator}** just dropped a brand new Short! Tap below to watch 📱",
    "🩳 Fresh Short alert! New clip from **{creator}** is out! Go show some love 💜",
    "✨ New Short incoming! Check out what **{creator}** just posted 🔥"
  ],
  VIDEO: [
    "🍿 New video drop! **{creator}** just uploaded a brand new video! Grab your popcorn 🎬",
    "🎬 Fresh upload alert! A brand new video from **{creator}** is out now! Go check it out 💜",
    "🔥 Drop everything! **{creator}** just released a new video! Tap below to watch 🍿"
  ]
};

function getRandomMessage(type, creator) {
  const pool = LIVELY_MESSAGES[type] || LIVELY_MESSAGES.VIDEO;
  const template = pool[Math.floor(Math.random() * pool.length)];
  return template.replace("{creator}", creator);
}

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
      for (const [channelId, name] of Object.entries(CREATORS)) {
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

    // 3. Test Bot Endpoint (GET /test-discord)
    if (url.pathname.endsWith("/test-discord")) {
      const token = env.DISCORD_TOKEN;
      if (!token) {
        return new Response(JSON.stringify({ error: "DISCORD_TOKEN is missing in Cloudflare variables! Please add it." }, null, 2), {
          status: 400,
          headers: { "Content-Type": "application/json" }
        });
      }

      const results = {};
      results.LIVE = (await sendDiscordMessage(token, DISCORD_CHANNELS.LIVE, {
        content: getRandomMessage("LIVE", "MissJey"),
        embeds: [{
          title: "🔴 LIVE NOW • RANKED VALORANT WITH VIEWERS! 💜",
          description: "MissJey is LIVE right now grinding Radiant lobbies! Come hang out, chat, and drop a like!",
          color: 0xFF0033,
          footer: { text: "Jey's Bot 💜 • 24/7 Cloudflare Engine" },
          timestamp: new Date().toISOString()
        }],
        components: [{
          type: 1,
          components: [{ type: 2, style: 5, label: "▶ Watch Live Stream", url: "https://www.youtube.com/@MissjeyGaming/streams" }]
        }]
      })) ? "Delivered ✅" : "Failed ❌";

      results.VIDEOS = (await sendDiscordMessage(token, DISCORD_CHANNELS.VIDEOS, {
        content: getRandomMessage("VIDEO", "MissJey"),
        embeds: [{
          title: "🎬 NEW VIDEO • My Funniest Valorant Highlights! 😂",
          description: "New video just dropped! Grab your snacks, watch the highlights, and leave a comment!",
          color: 0xCC0000,
          footer: { text: "Jey's Bot 💜 • 24/7 Cloudflare Engine" },
          timestamp: new Date().toISOString()
        }],
        components: [{
          type: 1,
          components: [{ type: 2, style: 5, label: "▶ Watch Video", url: "https://www.youtube.com/@MissjeyGaming/videos" }]
        }]
      })) ? "Delivered ✅" : "Failed ❌";

      results.SHORTS = (await sendDiscordMessage(token, DISCORD_CHANNELS.SHORTS, {
        content: getRandomMessage("SHORTS", "MissJey"),
        embeds: [{
          title: "🩳 NEW SHORT • 🏅 #valorant #gamergirl #viral",
          description: "Quick Short just dropped! Tap below to open on mobile or web:",
          color: 0xFF5722,
          footer: { text: "Jey's Bot 💜 • 24/7 Cloudflare Engine" },
          timestamp: new Date().toISOString()
        }],
        components: [{
          type: 1,
          components: [{ type: 2, style: 5, label: "📱 Open Short", url: "https://www.youtube.com/@MissjeyGaming/shorts" }]
        }]
      })) ? "Delivered ✅" : "Failed ❌";

      return new Response(JSON.stringify({ status: "Lively test complete", results }, null, 2), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }

    // 4. Manual Live Check Endpoint (GET /check-live)
    if (url.pathname.endsWith("/check-live")) {
      const results = await checkLiveStreams(env);
      return new Response(JSON.stringify({ status: "Live check complete", results }, null, 2), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }

    // 5. Incoming Real-Time Push Notification (POST)
    if (request.method === "POST" && (url.pathname.endsWith("/webhook") || url.pathname.endsWith("/youtube/webhook"))) {
      const text = await request.text();
      
      const videoIdMatch = text.match(/<yt:videoId>(.*?)<\/yt:videoId>/);
      const channelIdMatch = text.match(/<yt:channelId>(.*?)<\/yt:channelId>/);
      const titleMatch = text.match(/<title>(.*?)<\/title>/g);

      if (videoIdMatch && channelIdMatch) {
        const videoId = videoIdMatch[1].trim();
        const channelId = channelIdMatch[1].trim();
        const title = titleMatch && titleMatch[1] ? titleMatch[1].replace(/<\/?title>/g, "").trim() : "New YouTube Content";
        const creator = CREATORS[channelId] || "Creator";

        // Dispatch asynchronously in background (zero delay to Google)
        ctx.waitUntil(handleYouTubeEvent(videoId, channelId, title, creator, env));
      }

      // Return 204 No Content to Google immediately
      return new Response(null, { status: 204 });
    }

    return new Response(
      "💜 Jey's Bot Cloudflare 24/7 Engine is LIVE!\nVisit /subscribe to register channels with Google WebSub.\nVisit /test-discord to test direct Discord delivery.\nVisit /check-live to run live stream detection.",
      { status: 200, headers: { "Content-Type": "text/plain" } }
    );
  },

  // Cloudflare Serverless Cron Trigger (Runs every 1 min in the cloud)
  async scheduled(event, env, ctx) {
    ctx.waitUntil(checkLiveStreams(env));
  }
};

async function checkLiveStreams(env) {
  const token = env.DISCORD_TOKEN || env.BOT_TOKEN || env.DISCORD_BOT_TOKEN || env.TOKEN;
  const results = {};
  for (const [channelId, creator] of Object.entries(CREATORS)) {
    try {
      const res = await fetch(`https://www.youtube.com/channel/${channelId}/live`, {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
          "Accept-Language": "en-US,en;q=0.9"
        },
        redirect: "follow"
      });

      if (!res.ok) {
        results[creator] = `HTTP ${res.status}`;
        continue;
      }

      const text = await res.text();
      const isLive = text.includes('{"text":" LIVE"}') || text.includes('"isLive":true') || text.includes('"isLiveNow":true');

      if (isLive) {
        let videoId = null;
        const canonicalMatch = text.match(/rel="canonical"\s+href="https:\/\/www\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})"/i)
          || text.match(/href="https:\/\/www\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})"\s+rel="canonical"/i)
          || text.match(/"liveStreamability".*?"videoId":"([a-zA-Z0-9_-]{11})"/s)
          || text.match(/"watchEndpoint":{"videoId":"([a-zA-Z0-9_-]{11})"/);

        if (canonicalMatch) {
          videoId = canonicalMatch[1];
        } else if (res.url && res.url.includes("watch?v=")) {
          videoId = res.url.split("watch?v=")[1].split("&")[0];
        } else {
          const anyVid = text.match(/"videoId":"([a-zA-Z0-9_-]{11})"/);
          if (anyVid) videoId = anyVid[1];
        }

        if (videoId) {
          let title = `${creator} is LIVE right now!`;
          const titleMatch = text.match(/<title>(.*?)<\/title>/);
          if (titleMatch && titleMatch[1]) {
            title = titleMatch[1].replace(" - YouTube", "").trim();
          }
          if (token) {
            await handleYouTubeEvent(videoId, channelId, title, creator, env);
            results[creator] = `LIVE (${videoId}): Dispatched ✅`;
          } else {
            results[creator] = `LIVE (${videoId}): Detected, but DISCORD_TOKEN is missing in Cloudflare Secrets!`;
          }
        } else {
          results[creator] = "LIVE detected but Video ID not resolved";
        }
      } else {
        results[creator] = "Offline";
      }
    } catch (err) {
      console.error(`Error checking live status for ${creator}:`, err);
      results[creator] = `Error: ${err.message}`;
    }
  }
  return results;
}

async function handleYouTubeEvent(videoId, channelId, rawTitle, creator, env) {
  const token = env.DISCORD_TOKEN || env.BOT_TOKEN || env.DISCORD_BOT_TOKEN || env.TOKEN;
  if (!token) {
    console.error("DISCORD_TOKEN is missing in Cloudflare environment!");
    return;
  }

  // 1. Classify Content (Shorts vs Live vs Video)
  let videoType = "VIDEO";
  let targetChannelId = DISCORD_CHANNELS.VIDEOS;
  let embedColor = 0xCC0000;
  let badge = "🎬 NEW VIDEO";
  let buttonLabel = "▶ Watch Video";
  let videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
  let scheduledTimeField = null;
  let videoDescription = "";

  // Check if it's a Short (HTTP 200 on /shorts/ID vs 303 redirect to /watch)
  try {
    const shortsRes = await fetch(`https://www.youtube.com/shorts/${videoId}`, { redirect: "manual" });
    if (shortsRes.status === 200) {
      videoType = "SHORTS";
      targetChannelId = DISCORD_CHANNELS.SHORTS;
      embedColor = 0xFF5722; // Neon Amber-Orange
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
        const shortDesc = pData?.videoDetails?.shortDescription;

        if (shortDesc) {
          // Clean first 200 characters of creator's real description
          videoDescription = shortDesc.split("\n").filter(l => l.trim().length > 0).slice(0, 2).join("\n").slice(0, 200);
        }

        if (isLiveNow) {
          videoType = "LIVE";
          targetChannelId = DISCORD_CHANNELS.LIVE;
          embedColor = 0xFF0033; // Vibrant Live Red
          badge = "🔴 LIVE NOW";
          buttonLabel = "▶ Watch Live Stream";
        } else if (isLiveContent && !liveDetails?.endTimestamp) {
          videoType = "UPCOMING";
          targetChannelId = DISCORD_CHANNELS.LIVE;
          embedColor = 0xF1C40F; // Warm Gold
          badge = "📅 SCHEDULED STREAM";
          buttonLabel = "⏰ Set Reminder / View";

          // Extract real scheduled start time for dynamic countdown
          const rawTime = liveDetails?.startTimestamp || liveDetails?.scheduledStartTime;
          if (rawTime) {
            const unixSec = Math.floor(new Date(rawTime).getTime() / 1000);
            scheduledTimeField = {
              name: "📅 Scheduled Start Time",
              value: `<t:${unixSec}:F>\n👉 **Countdown:** <t:${unixSec}:R>`,
              inline: false
            };
          }
        }
      }
    } catch (e) {}
  }

  // 2. Strict Deduplication per (videoId, videoType) using Cloudflare Cache
  const cacheKey = `https://cache.jeysbot.local/posted/${videoId}_${videoType}`;
  const cache = caches.default;
  const existing = await cache.match(cacheKey);
  if (existing) {
    console.log(`Video ${videoId} [${videoType}] already posted. Skipping duplicate.`);
    return;
  }

  // 3. Format Lively Discord Embed
  const fields = [];
  if (scheduledTimeField) {
    fields.push(scheduledTimeField);
  }

  const embed = {
    title: `${badge} • ${rawTitle}`,
    url: videoUrl,
    description: videoDescription || undefined,
    color: embedColor,
    fields: fields.length > 0 ? fields : undefined,
    author: {
      name: `${creator} 💜`,
      url: `https://www.youtube.com/channel/${channelId}`,
      icon_url: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`
    },
    image: {
      url: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`
    },
    footer: {
      text: "Jey's Bot 💜 • 24/7 Cloudflare Engine",
      icon_url: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`
    },
    timestamp: new Date().toISOString()
  };

  const components = [
    {
      type: 1,
      components: [
        {
          type: 2,
          style: 5, // Link button
          label: buttonLabel,
          url: videoUrl
        }
      ]
    }
  ];

  const payload = {
    content: `${getRandomMessage(videoType, creator)}\n${videoUrl}`,
    embeds: [embed],
    components: components
  };

  const success = await sendDiscordMessage(token, targetChannelId, payload);
  if (success) {
    // Cache for 7 days to deduplicate
    const cacheResponse = new Response("1", {
      headers: { "Cache-Control": "max-age=604800" }
    });
    await cache.put(cacheKey, cacheResponse);
    console.log(`✅ Posted ${videoId} [${videoType}] to Discord channel ${targetChannelId}!`);
  }
}

async function sendDiscordMessage(token, channelId, payload) {
  try {
    const res = await fetch(`https://discord.com/api/v10/channels/${channelId}/messages`, {
      method: "POST",
      headers: {
        "Authorization": `Bot ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    return res.ok;
  } catch (e) {
    console.error(`Error sending message to Discord channel ${channelId}:`, e);
    return false;
  }
}
