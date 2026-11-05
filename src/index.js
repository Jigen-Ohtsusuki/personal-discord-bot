/**
 * Jey's Bot 💜 - 24/7 Cloudflare YouTube Engine
 * 100% Free Forever • Zero Polling • Lively & Production-Grade
 */

// Target YouTube Creators
const CREATORS = {
  "UC12_jnxFlORtx9JjrnHPalg": "MissJey"
};

// Discord Channel Routing
const DISCORD_CHANNELS = {
  LIVE: "1566020837151211671",    // #live-streams
  VIDEOS: "1566020914787651586",  // #videos
  SHORTS: "1566021006961811586"   // #shorts
};

// Natural, casual community messages (no AI/corporate hype)
const LIVELY_MESSAGES = {
  LIVE: [
    "hey everyone, **{creator}** is live rn! come chill 💜",
    "**{creator}** just went live! hop in the stream 🎮",
    "stream is live! come hang out with **{creator}** 💜",
    "we live! come say hi in chat 🔥"
  ],
  STREAM_ENDED: [
    "stream is ended! missed it? watch the full vod here 👇",
    "**{creator}**'s stream ended! missed it? catch the vod below 💜",
    "stream's over! missed the stream? watch the vod here 🎬",
    "that's a wrap! missed it? you can watch the vod right here 👇"
  ],
  UPCOMING: [
    "**{creator}** scheduled a stream! set your reminders ⏰",
    "new stream scheduled by **{creator}**! check the time below 💜"
  ],
  SHORTS: [
    "new short is out from **{creator}**! 📱",
    "**{creator}** just posted a new short! 🩳",
    "quick short just dropped by **{creator}** ✨"
  ],
  VIDEO: [
    "new video is up! go check it out 🎬",
    "**{creator}** just uploaded a new video! 🍿",
    "fresh video drop from **{creator}** 💜"
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

    // 5. Admin Sync Live Stream Endpoint (GET /sync-live?videoId=...&msgId=...)
    if (url.pathname.endsWith("/sync-live")) {
      const vId = url.searchParams.get("videoId") || "SfQXXWDTFLY";
      const mId = url.searchParams.get("msgId") || "1567780862043623529";
      const cId = url.searchParams.get("channelId") || "UC12_jnxFlORtx9JjrnHPalg";
      if (env.JEYSBOT_CACHE) {
        await env.JEYSBOT_CACHE.put(`live_msgid_${vId}`, mId, { expirationTtl: 604800 });
        await env.JEYSBOT_CACHE.put(`active_live_stream_${cId}`, vId, { expirationTtl: 86400 });
        await env.JEYSBOT_CACHE.put(`posted_${vId}_LIVE`, "1", { expirationTtl: 604800 });
        await env.JEYSBOT_CACHE.delete(`posted_${vId}_VIDEO`);
        return new Response(JSON.stringify({ status: "Synced active live stream", videoId: vId, messageId: mId }, null, 2), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      return new Response("No JEYSBOT_CACHE binding found", { status: 500 });
    }

    // 6. Incoming Real-Time Push Notification (POST)
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
      
      // Strict check: Must have canonical watch URL OR redirect URL to watch?v=
      let videoId = null;
      const canonicalMatch = text.match(/rel="canonical"\s+href="https:\/\/www\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})"/i)
        || text.match(/href="https:\/\/www\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})"\s+rel="canonical"/i)
        || text.match(/<link\s+rel="canonical"\s+href="https:\/\/www\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})"/i);

      if (canonicalMatch) {
        videoId = canonicalMatch[1];
      } else if (res.url && res.url.includes("watch?v=")) {
        videoId = res.url.split("watch?v=")[1].split("&")[0];
      }

      // Robust check: YouTube indicates live status through several keys on /live page
      const isLiveNow = videoId && (
        text.includes('"isLive":true') ||
        text.includes('"isLiveContent":true') ||
        text.includes('"liveStreamability"') ||
        text.includes('"isLiveNow":true') ||
        text.includes('"status":"LIVE"') ||
        text.includes('liveIndicatorText')
      );

      if (isLiveNow && videoId) {
        let title = `${creator} is LIVE rn!`;
        const titleMatch = text.match(/<title>(.*?)<\/title>/);
        if (titleMatch && titleMatch[1]) {
          title = titleMatch[1].replace(" - YouTube", "").trim();
        }
        if (token) {
          // Pass onlyLive=true so it ONLY posts if confirmed to be an active live stream
          await handleYouTubeEvent(videoId, channelId, title, creator, env, true);
          results[creator] = `LIVE (${videoId}): Dispatched ✅`;
        } else {
          results[creator] = `LIVE (${videoId}): Detected, but token missing`;
        }
      } else {
        // Channel is currently Offline — check if a live stream just ended
        if (env.JEYSBOT_CACHE) {
          const activeVideoId = await env.JEYSBOT_CACHE.get(`active_live_stream_${channelId}`);
          if (activeVideoId) {
            const alreadyEnded = await env.JEYSBOT_CACHE.get(`posted_${activeVideoId}_STREAM_ENDED`);
            if (!alreadyEnded) {
              console.log(`Live stream ${activeVideoId} for ${creator} ended. Triggering STREAM_ENDED edit...`);
              await handleYouTubeEvent(activeVideoId, channelId, `${creator}'s Stream`, creator, env, false, true);
            }
            await env.JEYSBOT_CACHE.delete(`active_live_stream_${channelId}`);
          }
        }
        results[creator] = "Offline";
      }
    } catch (err) {
      console.error(`Error checking live status for ${creator}:`, err);
      results[creator] = `Error: ${err.message}`;
    }
  }
  return results;
}

async function handleYouTubeEvent(videoId, channelId, rawTitle, creator, env, onlyLive = false, forceStreamEnded = false) {
  const token = env.DISCORD_TOKEN || env.BOT_TOKEN || env.DISCORD_BOT_TOKEN || env.TOKEN;
  if (!token) {
    console.error("DISCORD_TOKEN is missing in Cloudflare environment!");
    return;
  }

  // 0. Hard gate: channelId must be one of our tracked creators
  if (!CREATORS[channelId]) {
    console.warn(`Received event for unknown channel ${channelId}. Dropping.`);
    return;
  }

  // 1. Classify Content (Shorts vs Live vs Video vs Stream Ended)
  let videoType = null;
  let targetChannelId = DISCORD_CHANNELS.VIDEOS;
  let embedColor = 0xCC0000;
  let badge = "🎬 NEW VIDEO";
  let buttonLabel = "▶ Watch Video";
  let videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
  let scheduledTimeField = null;
  let videoDescription = "";

  if (forceStreamEnded) {
    videoType = "STREAM_ENDED";
    targetChannelId = DISCORD_CHANNELS.LIVE;
    embedColor = 0x7289DA;
    badge = "📼 STREAM ENDED";
    buttonLabel = "▶ Watch VOD";
  }

  // Check if it's a Short (HTTP 200 on /shorts/ID vs 303 redirect to /watch)
  if (!videoType) {
    try {
      const shortsRes = await fetch(`https://www.youtube.com/shorts/${videoId}`, { redirect: "manual" });
      if (shortsRes.status === 200) {
        videoType = "SHORTS";
        targetChannelId = DISCORD_CHANNELS.SHORTS;
        embedColor = 0xFF5722;
        badge = "🩳 NEW SHORT";
        buttonLabel = "📱 Watch Short";
        videoUrl = `https://www.youtube.com/shorts/${videoId}`;
      }
    } catch (e) {}
  }

  // Deep inspection for Livestreams, Upcoming, VODs, and regular Videos
  if (!videoType) {
    let pData = null;
    let htmlText = "";

    // Method A: InnerTube Player API
    try {
      const playerRes = await fetch("https://www.youtube.com/youtubei/v1/player", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
          "X-YouTube-Client-Name": "1",
          "X-YouTube-Client-Version": "2.20241030.01.00"
        },
        body: JSON.stringify({
          context: {
            client: {
              clientName: "WEB",
              clientVersion: "2.20241030.01.00",
              hl: "en",
              gl: "US"
            }
          },
          videoId: videoId
        })
      });
      if (playerRes.ok) {
        pData = await playerRes.json();
      }
    } catch (e) {
      console.warn(`InnerTube player check error for ${videoId}:`, e);
    }

    // Method B: Direct HTML Fetch (100% resilient fallback)
    try {
      const watchRes = await fetch(`https://www.youtube.com/watch?v=${videoId}`, {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
          "Accept-Language": "en-US,en;q=0.9"
        }
      });
      if (watchRes.ok) {
        htmlText = await watchRes.text();
      }
    } catch (e) {
      console.warn(`HTML watch page check error for ${videoId}:`, e);
    }

    // Strict channel verification: The video MUST belong to the tracked creator!
    const actualChannelId = pData?.videoDetails?.channelId;
    if (actualChannelId && actualChannelId !== channelId) {
      console.warn(`Video ${videoId} belongs to ${actualChannelId}, not ${channelId}. Skipping.`);
      return;
    }

    const liveDetails = pData?.microformat?.playerMicroformatRenderer?.liveBroadcastDetails;
    const isLiveNow = Boolean(
      liveDetails?.isLiveNow ||
      pData?.videoDetails?.isLive ||
      htmlText.includes('"isLive":true') ||
      htmlText.includes('"isLiveNow":true') ||
      htmlText.includes('"liveStreamability"') ||
      htmlText.includes('liveIndicatorText')
    );

    const isLiveContent = Boolean(
      pData?.videoDetails?.isLiveContent ||
      pData?.videoDetails?.isLive ||
      htmlText.includes('"isLiveContent":true') ||
      htmlText.includes('"isLive":true')
    );

    const lengthSeconds = parseInt(pData?.videoDetails?.lengthSeconds || "0", 10);
    const hasEnded = Boolean(
      liveDetails?.endTimestamp ||
      htmlText.includes('"endTimestamp":')
    );

    const shortDesc = pData?.videoDetails?.shortDescription;
    if (shortDesc) {
      videoDescription = shortDesc.split("\n").filter(l => l.trim().length > 0).slice(0, 2).join("\n").slice(0, 200);
    }

    if (hasEnded && isLiveContent) {
      // Completed livestream VOD
      videoType = "STREAM_ENDED";
      targetChannelId = DISCORD_CHANNELS.LIVE;
      embedColor = 0x7289DA;
      badge = "📼 STREAM ENDED";
      buttonLabel = "▶ Watch VOD";
    } else if (isLiveNow || (isLiveContent && lengthSeconds === 0)) {
      // Actively broadcasting Live Stream
      videoType = "LIVE";
      targetChannelId = DISCORD_CHANNELS.LIVE;
      embedColor = 0xFF0033;
      badge = "🔴 LIVE";
      buttonLabel = "▶ Watch Live Stream";
    } else if (isLiveContent) {
      // Scheduled / Upcoming stream
      const rawTime = liveDetails?.startTimestamp || liveDetails?.scheduledStartTime;
      videoType = "UPCOMING";
      targetChannelId = DISCORD_CHANNELS.LIVE;
      embedColor = 0xF1C40F;
      badge = "📅 SCHEDULED STREAM";
      buttonLabel = "⏰ Set Reminder";
      if (rawTime) {
        const unixSec = Math.floor(new Date(rawTime).getTime() / 1000);
        scheduledTimeField = {
          name: "📅 Scheduled Start Time",
          value: `<t:${unixSec}:F>\n👉 **Countdown:** <t:${unixSec}:R>`,
          inline: false
        };
      }
    } else {
      // Standard regular video
      videoType = "VIDEO";
      targetChannelId = DISCORD_CHANNELS.VIDEOS;
      embedColor = 0xCC0000;
      badge = "🎬 NEW VIDEO";
      buttonLabel = "▶ Watch Video";
    }
  }

  // If called from live-stream prober, NEVER post if not actively live!
  if (onlyLive && videoType !== "LIVE") {
    console.log(`Video ${videoId} is not an active live stream (type: ${videoType}). Skipping.`);
    return;
  }

  // 2. Strict Deduplication using Cloudflare KV
  // Use a shared base key per videoId so LIVE/UPCOMING/VIDEO don't all post for the same stream.
  // Rule: once ANY type has been posted for a videoId, block all further types for that video.
  const kvKey = `posted_${videoId}_${videoType}`;
  const kvBaseKey = `posted_${videoId}`; // shared across all types for this video
  if (env.JEYSBOT_CACHE) {
    // Block if this exact type was already posted
    const existing = await env.JEYSBOT_CACHE.get(kvKey);
    if (existing) {
      console.log(`Video ${videoId} [${videoType}] already posted (KV). Skipping duplicate.`);
      return;
    }
    // Block UPCOMING if LIVE was already posted for this videoId (stream went live before scheduled post)
    if (videoType === "UPCOMING") {
      const liveAlreadyPosted = await env.JEYSBOT_CACHE.get(`posted_${videoId}_LIVE`);
      if (liveAlreadyPosted) {
        console.log(`Video ${videoId}: LIVE already posted, skipping UPCOMING duplicate.`);
        return;
      }
    }
    // Block VIDEO if LIVE was already posted (stream VOD showing up in WebSub after ending)
    // Also block VIDEO if UPCOMING was already posted (means this video IS a live stream, not a regular video)
    if (videoType === "VIDEO") {
      const liveAlreadyPosted = await env.JEYSBOT_CACHE.get(`posted_${videoId}_LIVE`);
      const upcomingAlreadyPosted = await env.JEYSBOT_CACHE.get(`posted_${videoId}_UPCOMING`);
      if (liveAlreadyPosted || upcomingAlreadyPosted) {
        console.log(`Video ${videoId}: Stream already tracked (LIVE/UPCOMING posted), skipping VIDEO. Dropping.`);
        return;
      }
    }
    // Only post STREAM_ENDED if we actually tracked LIVE or UPCOMING for this video
    if (videoType === "STREAM_ENDED") {
      const liveAlreadyPosted = await env.JEYSBOT_CACHE.get(`posted_${videoId}_LIVE`);
      const upcomingAlreadyPosted = await env.JEYSBOT_CACHE.get(`posted_${videoId}_UPCOMING`);
      if (!liveAlreadyPosted && !upcomingAlreadyPosted) {
        console.log(`Video ${videoId}: No LIVE or UPCOMING post found, skipping orphan STREAM_ENDED.`);
        return;
      }
    }
  } else {
    console.warn("JEYSBOT_CACHE KV namespace not bound — deduplication skipped! Bind it in Cloudflare dashboard.");
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
      text: "Jey's Bot 💜",
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

  // Dedicated Alert Role Pings
  const ALERT_ROLE_IDS = {
    LIVE: "1567464086151761981",       // @Stream Alert
    UPCOMING: "1567464086151761981",   // @Stream Alert
    VIDEO: "1567464087779278921",      // @Video Alert
    SHORTS: "1567464087779278921"      // @Video Alert
  };

  const rolePing = ALERT_ROLE_IDS[videoType] ? `<@&${ALERT_ROLE_IDS[videoType]}> ` : "";

  const payload = {
    content: `${rolePing}${getRandomMessage(videoType, creator)}\n${videoUrl}`,
    embeds: [embed],
    components: components
  };

  // If LIVE is firing and we have a stored UPCOMING message, edit that message instead of posting a new one
  if (videoType === "LIVE" && env.JEYSBOT_CACHE) {
    const upcomingMsgId = await env.JEYSBOT_CACHE.get(`upcoming_msgid_${videoId}`);
    if (upcomingMsgId) {
      const edited = await editDiscordMessage(token, DISCORD_CHANNELS.LIVE, upcomingMsgId, payload);
      if (edited) {
        await env.JEYSBOT_CACHE.put(kvKey, "1", { expirationTtl: 604800 });
        await env.JEYSBOT_CACHE.put(`live_msgid_${videoId}`, upcomingMsgId, { expirationTtl: 604800 });
        await env.JEYSBOT_CACHE.put(`active_live_stream_${channelId}`, videoId, { expirationTtl: 86400 });

        // Send a fresh notification buzz so members with @Stream Alerts hear the ping when stream goes live
        await sendDiscordMessage(token, DISCORD_CHANNELS.LIVE, {
          content: `<@&1567464086151761981> **${creator} is now LIVE!** 🔴 Come chill: ${videoUrl}`
        });

        console.log(`✅ Edited UPCOMING → LIVE for ${videoId} (msg ${upcomingMsgId}) and sent stream alert ping`);
        return;
      }
      // If edit fails (message deleted etc.), fall through to send a new message
    }
  }

  // If STREAM_ENDED is firing, EDIT the original stream notification to show VOD
  if (videoType === "STREAM_ENDED" && env.JEYSBOT_CACHE) {
    const liveMsgId = await env.JEYSBOT_CACHE.get(`live_msgid_${videoId}`);
    if (liveMsgId) {
      const edited = await editDiscordMessage(token, DISCORD_CHANNELS.LIVE, liveMsgId, payload);
      if (edited) {
        await env.JEYSBOT_CACHE.put(kvKey, "1", { expirationTtl: 604800 });
        await env.JEYSBOT_CACHE.delete(`active_live_stream_${channelId}`);
        console.log(`✅ Edited LIVE → STREAM_ENDED for ${videoId} (msg ${liveMsgId})`);
        return;
      }
      // If edit fails, fall through to post a new message
    }
  }

  const msgData = await sendDiscordMessage(token, targetChannelId, payload);
  if (msgData) {
    // Write to KV so every edge PoP knows this was already posted (7 day TTL)
    if (env.JEYSBOT_CACHE) {
      await env.JEYSBOT_CACHE.put(kvKey, "1", { expirationTtl: 604800 });
      if (videoType === "UPCOMING") {
        const msgId = msgData.id;
        if (msgId) {
          await env.JEYSBOT_CACHE.put(`upcoming_msgid_${videoId}`, msgId, { expirationTtl: 604800 });
          await env.JEYSBOT_CACHE.put(`live_msgid_${videoId}`, msgId, { expirationTtl: 604800 });
          console.log(`📌 Stored UPCOMING message ID ${msgId} for video ${videoId}`);
        }
      } else if (videoType === "LIVE") {
        const msgId = msgData.id;
        if (msgId) {
          await env.JEYSBOT_CACHE.put(`live_msgid_${videoId}`, msgId, { expirationTtl: 604800 });
          await env.JEYSBOT_CACHE.put(`active_live_stream_${channelId}`, videoId, { expirationTtl: 86400 });
          console.log(`📌 Stored LIVE message ID ${msgId} for video ${videoId}`);
        }
      } else if (videoType === "STREAM_ENDED") {
        await env.JEYSBOT_CACHE.delete(`active_live_stream_${channelId}`);
      }
    }
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
    if (!res.ok) {
      const err = await res.text();
      console.error(`Error sending message to Discord channel ${channelId}:`, res.status, err);
      return null;
    }
    const data = await res.json();
    return data;
  } catch (e) {
    console.error(`Error sending message to Discord channel ${channelId}:`, e);
    return null;
  }
}

async function editDiscordMessage(token, channelId, messageId, payload) {
  try {
    const res = await fetch(`https://discord.com/api/v10/channels/${channelId}/messages/${messageId}`, {
      method: "PATCH",
      headers: {
        "Authorization": `Bot ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.text();
      console.warn(`Failed to edit message ${messageId}: ${res.status} ${err}`);
    }
    return res.ok;
  } catch (e) {
    console.error(`Error editing message ${messageId}:`, e);
    return false;
  }
}

async function getLastMessageId(token, channelId) {
  try {
    const res = await fetch(`https://discord.com/api/v10/channels/${channelId}/messages?limit=1`, {
      headers: { "Authorization": `Bot ${token}` }
    });
    if (!res.ok) return null;
    const msgs = await res.json();
    return msgs?.[0]?.id || null;
  } catch (e) {
    return null;
  }
}
