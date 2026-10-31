const fs = require('fs');
const path = require('path');
const { register, listen } = require('push-receiver');
const axios = require('axios');

const CREDENTIALS_FILE = path.join(__dirname, 'fcm_credentials.json');
const DISCORD_BOT_ENDPOINT = process.env.BOT_FCM_CALLBACK || 'http://127.0.0.1:8080/fcm/notify';
// Google / YouTube WebPush Sender ID (Project Number for Chrome WebPush / YouTube)
const SENDER_ID = process.env.FCM_SENDER_ID || '289895240974';

function extractVideoId(payload) {
  if (!payload) return null;
  const str = typeof payload === 'string' ? payload : JSON.stringify(payload);
  
  // Look for direct videoId fields
  const idMatch = str.match(/"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"/);
  if (idMatch) return idMatch[1];

  // Look for youtube URLs (watch?v= or shorts/)
  const urlMatch = str.match(/(?:watch\?v=|shorts\/)([a-zA-Z0-9_-]{11})/);
  if (urlMatch) return urlMatch[1];

  return null;
}

async function startFCMReceiver() {
  let credentials;

  if (fs.existsSync(CREDENTIALS_FILE)) {
    try {
      credentials = JSON.parse(fs.readFileSync(CREDENTIALS_FILE, 'utf8'));
      console.log('[FCM] Loaded existing persistent device credentials.');
    } catch (e) {
      console.error('[FCM] Error parsing credentials file, re-registering:', e.message);
    }
  }

  if (!credentials) {
    console.log('[FCM] Registering new Android GCM/FCM device identity with Google...');
    try {
      credentials = await register(SENDER_ID);
      fs.writeFileSync(CREDENTIALS_FILE, JSON.stringify(credentials, null, 2), 'utf8');
      console.log('[FCM] Successfully registered device with Google Play / FCM.');
      console.log('[FCM] Android ID:', credentials.keys ? credentials.keys.auth : 'OK');
      console.log('[FCM] Push Endpoint:', credentials.fcm ? credentials.fcm.token : 'OK');
    } catch (err) {
      console.error('[FCM] Fatal error registering with Google FCM:', err);
      process.exit(1);
    }
  }

  // Connect to persistent mtalk socket
  console.log('[FCM] Connecting persistent TLS socket to mtalk.google.com:5228...');
  const client = await listen(credentials, async ({ notification }) => {
    console.log('[FCM] 🔔 Push Notification Received from Google!');
    console.log('[FCM] Raw payload:', JSON.stringify(notification));

    const videoId = extractVideoId(notification);
    if (videoId) {
      console.log(`[FCM] 🎯 Extracted YouTube Video ID: ${videoId}`);
      try {
        await axios.post(DISCORD_BOT_ENDPOINT, {
          video_id: videoId,
          source: 'fcm',
          timestamp: new Date().toISOString()
        }, { timeout: 5000 });
        console.log(`[FCM] Successfully dispatched ${videoId} to Discord Bot!`);
      } catch (err) {
        console.error(`[FCM] Failed to deliver notification to Discord Bot: ${err.message}`);
      }
    } else {
      console.log('[FCM] Received non-video FCM push payload.');
    }
  });

  console.log('[FCM] ✅ Persistent connection to mtalk.google.com established. Listening for phone pushes (0 Polling).');

  // Handle process shutdown
  process.on('SIGINT', () => {
    console.log('[FCM] Disconnecting from mtalk...');
    process.exit(0);
  });
}

startFCMReceiver().catch(err => {
  console.error('[FCM] Top-level error:', err);
});
