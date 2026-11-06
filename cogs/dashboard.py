import os
import sys
import time
import json
import psutil
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Set

import discord
from discord.ext import commands
from aiohttp import web, ClientSession

import config
from database import db
from cogs.moderation import parse_duration, format_duration

logger = logging.getLogger("DashboardCog")

DASHBOARD_PORT = config.DASHBOARD_PORT
DASHBOARD_PIN = config.DASHBOARD_PIN
DISCORD_CLIENT_ID = config.DISCORD_CLIENT_ID
DISCORD_CLIENT_SECRET = config.DISCORD_CLIENT_SECRET
START_TIME = time.time()

MISSJEY_AVATAR = "https://yt3.googleusercontent.com/O143rEtFVDnaNLx5zkY4QcYIXpKuUMIWkAN_m7ZJeuE5qCGhPMXJqWzHhiChGeJtWZq_lEFKkQ=s900-c-k-c0x00ffffff-no-rj"

# In-memory session store: token -> {user, allowed_guild_ids, is_master, expires}
SESSIONS: Dict[str, Dict[str, Any]] = {}

HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Jey's Bot 💜 • Multi-Server Control Center</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #09090d;
      --card-bg: #12121a;
      --card-border: #1f1f2e;
      --accent: #AA88FF;
      --accent-hover: #9872ff;
      --accent-glow: rgba(170, 136, 255, 0.22);
      --text: #f0f0f5;
      --text-muted: #8e8ea6;
      --success: #4ade80;
      --danger: #f87171;
      --warning: #fbbf24;
      --radius: 14px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; }
    
    header { background: #0f0f17; border-bottom: 1px solid var(--card-border); padding: 14px 28px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 50; }
    .brand-section { display: flex; align-items: center; gap: 20px; }
    .brand { display: flex; align-items: center; gap: 12px; }
    .brand img { width: 42px; height: 42px; border-radius: 50%; border: 2px solid var(--accent); box-shadow: 0 0 14px var(--accent-glow); }
    .brand h1 { font-size: 1.15rem; font-weight: 800; background: linear-gradient(135deg, #fff, var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .brand span { font-size: 0.75rem; color: var(--text-muted); display: block; }
    
    /* Server Selector */
    .server-selector-wrap { display: flex; align-items: center; gap: 8px; background: #161622; padding: 6px 14px; border-radius: 12px; border: 1px solid var(--card-border); }
    .server-selector-wrap label { font-size: 0.75rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase; }
    .server-select { background: transparent; color: #fff; border: none; font-size: 0.9rem; font-weight: 700; outline: none; cursor: pointer; max-width: 220px; }
    .server-select option { background: #12121a; color: #fff; }

    .nav-tabs { display: flex; gap: 6px; }
    .tab-btn { background: transparent; border: none; color: var(--text-muted); font-size: 0.88rem; font-weight: 600; padding: 8px 16px; border-radius: 10px; cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center; gap: 8px; }
    .tab-btn:hover { color: #fff; background: rgba(255,255,255,0.05); }
    .tab-btn.active { color: #fff; background: var(--accent); box-shadow: 0 0 14px var(--accent-glow); }

    .header-right { display: flex; align-items: center; gap: 14px; }
    .user-pill { display: flex; align-items: center; gap: 10px; background: #161622; border: 1px solid var(--card-border); padding: 5px 12px 5px 6px; border-radius: 30px; font-size: 0.82rem; font-weight: 600; }
    .user-pill img { width: 28px; height: 28px; border-radius: 50%; }
    .logout-btn { background: none; border: none; color: var(--danger); cursor: pointer; font-size: 0.78rem; font-weight: 700; margin-left: 6px; }

    main { flex: 1; max-width: 1240px; width: 100%; margin: 24px auto; padding: 0 20px; }
    .tab-pane { display: none; }
    .tab-pane.active { display: block; }
    
    .grid-4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 18px; margin-bottom: 24px; }
    .stat-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 20px; transition: transform 0.2s, border-color 0.2s; position: relative; overflow: hidden; }
    .stat-card:hover { transform: translateY(-2px); border-color: rgba(170, 136, 255, 0.4); }
    .stat-card .label { font-size: 0.78rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-card .value { font-size: 1.7rem; font-weight: 800; margin-top: 8px; color: #fff; }
    .stat-card .sub { font-size: 0.76rem; color: var(--text-muted); margin-top: 6px; }

    .panel-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 24px; margin-bottom: 24px; }
    .panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--card-border); }
    .panel-header h2 { font-size: 1.15rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 10px; }
    
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th { text-align: left; padding: 12px 14px; color: var(--text-muted); font-weight: 600; border-bottom: 1px solid var(--card-border); }
    td { padding: 14px; border-bottom: 1px solid rgba(255,255,255,0.03); }
    tr:hover td { background: rgba(255,255,255,0.02); }
    .tag { display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; }
    .tag-timeout { background: rgba(251, 191, 36, 0.15); color: var(--warning); border: 1px solid rgba(251, 191, 36, 0.3); }
    .tag-kick { background: rgba(248, 113, 113, 0.15); color: var(--danger); border: 1px solid rgba(248, 113, 113, 0.3); }
    .tag-ban { background: rgba(239, 68, 68, 0.25); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); }
    .tag-warn { background: rgba(170, 136, 255, 0.15); color: var(--accent); border: 1px solid rgba(170, 136, 255, 0.3); }

    .btn { background: var(--accent); color: #fff; border: none; padding: 10px 20px; border-radius: 10px; font-size: 0.88rem; font-weight: 700; cursor: pointer; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 8px; }
    .btn:hover { background: var(--accent-hover); box-shadow: 0 0 16px var(--accent-glow); }
    .btn-secondary { background: #222230; color: #fff; }
    .btn-secondary:hover { background: #2c2c3d; box-shadow: none; }
    .btn-danger { background: var(--danger); }
    .btn-discord { background: #5865F2; color: #fff; }
    .btn-discord:hover { background: #4752c4; box-shadow: 0 0 16px rgba(88, 101, 242, 0.4); }

    .form-group { margin-bottom: 18px; }
    .form-group label { display: block; font-size: 0.82rem; font-weight: 600; color: var(--text-muted); margin-bottom: 8px; }
    .form-control { width: 100%; background: #0b0b12; border: 1px solid var(--card-border); color: #fff; padding: 12px 14px; border-radius: 10px; font-size: 0.9rem; outline: none; transition: border-color 0.2s; }
    .form-control:focus { border-color: var(--accent); }
    
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    @media (max-width: 800px) {
      .grid-2 { grid-template-columns: 1fr; }
      header { flex-direction: column; gap: 14px; align-items: flex-start; }
      .header-right { width: 100%; justify-content: space-between; }
    }

    /* Modal */
    .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.8); backdrop-filter: blur(6px); display: none; align-items: center; justify-content: center; z-index: 999; }
    .modal-overlay.active { display: flex; }
    .modal-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 32px; max-width: 460px; width: 92%; box-shadow: 0 20px 60px rgba(0,0,0,0.8); text-align: center; }
    .modal-card h3 { font-size: 1.35rem; font-weight: 800; margin-bottom: 10px; }
    .modal-card p { font-size: 0.86rem; color: var(--text-muted); margin-bottom: 24px; line-height: 1.5; }
    .auth-divider { display: flex; align-items: center; gap: 14px; margin: 20px 0; color: var(--text-muted); font-size: 0.78rem; }
    .auth-divider::before, .auth-divider::after { content: ''; flex: 1; height: 1px; background: var(--card-border); }
  </style>
</head>
<body>
  <header>
    <div class="brand-section">
      <div class="brand">
        <img src="https://yt3.googleusercontent.com/O143rEtFVDnaNLx5zkY4QcYIXpKuUMIWkAN_m7ZJeuE5qCGhPMXJqWzHhiChGeJtWZq_lEFKkQ=s900-c-k-c0x00ffffff-no-rj" alt="MissJey">
        <div>
          <h1>Jey's Bot 💜</h1>
          <span>Multi-Server Control Center</span>
        </div>
      </div>
      
      <!-- Multi-Server Dropdown -->
      <div class="server-selector-wrap" id="server-selector-container">
        <label>Server:</label>
        <select id="server-select" class="server-select" onchange="onServerChanged()">
          <option value="" disabled selected>Loading servers...</option>
        </select>
      </div>
    </div>

    <nav class="nav-tabs">
      <button class="tab-btn active" onclick="switchTab('overview')">📊 Overview</button>
      <button class="tab-btn" onclick="switchTab('moderation')">🛡️ Moderation</button>
      <button class="tab-btn" onclick="switchTab('settings')">⚙️ Server Channels</button>
      <button class="tab-btn" onclick="switchTab('embeds')">📜 Welcome & Rules</button>
    </nav>

    <div class="header-right">
      <div class="user-pill" id="user-pill">
        <img id="user-avatar" src="https://cdn.discordapp.com/embed/avatars/0.png" alt="User">
        <span id="user-name">Guest</span>
        <button class="logout-btn" onclick="logout()">Logout</button>
      </div>
    </div>
  </header>

  <main>
    <!-- OVERVIEW TAB -->
    <div id="tab-overview" class="tab-pane active">
      <div class="grid-4">
        <div class="stat-card">
          <div class="label">Server Members</div>
          <div class="value" id="stat-members">—</div>
          <div class="sub" id="stat-guild-name">Selected Server</div>
        </div>
        <div class="stat-card">
          <div class="label">Bot Latency</div>
          <div class="value" id="stat-ping">— ms</div>
          <div class="sub">Discord Gateway</div>
        </div>
        <div class="stat-card">
          <div class="label">VPS Memory Usage</div>
          <div class="value" id="stat-ram">—</div>
          <div class="sub">Ubuntu 24.04 LTS (NVMe)</div>
        </div>
        <div class="stat-card">
          <div class="label">Bot Uptime</div>
          <div class="value" id="stat-uptime">—</div>
          <div class="sub">Continuous 24/7 Hosting</div>
        </div>
      </div>

      <div class="panel-card">
        <div class="panel-header">
          <h2>🛡️ Active Server Protection</h2>
          <span class="tag tag-warn" id="server-badge">Authorized Admin Session</span>
        </div>
        <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.6;">
          You are currently viewing and controlling <strong id="server-display-name" style="color: #fff;">...</strong>.
          All data, moderation events, and channel configurations are strictly isolated per-server.
          Only authenticated users with <strong>Administrator</strong> or <strong>Manage Server</strong> permissions on this Discord server are granted access.
        </p>
      </div>
    </div>

    <!-- MODERATION TAB -->
    <div id="tab-moderation" class="tab-pane">
      <div class="grid-2">
        <div class="panel-card">
          <div class="panel-header">
            <h2>⚖️ Take Moderation Action</h2>
          </div>
          <form id="mod-form" onsubmit="executeModAction(event)">
            <div class="form-group">
              <label>Select Server Member</label>
              <select id="mod-target" class="form-control" required>
                <option value="" disabled selected>Select a member...</option>
              </select>
            </div>
            <div class="form-group">
              <label>Action</label>
              <select id="mod-action" class="form-control" onchange="toggleDurationField()">
                <option value="TIMEOUT">⏳ Timeout (Mute)</option>
                <option value="REMOVE_TIMEOUT">🔊 Remove Timeout</option>
                <option value="WARN">⚠️ Warn Member</option>
                <option value="KICK">👢 Kick Member</option>
                <option value="BAN">🔨 Ban Member</option>
              </select>
            </div>
            <div class="form-group" id="duration-group">
              <label>Duration</label>
              <select id="mod-duration" class="form-control">
                <option value="5m">5 Minutes</option>
                <option value="10m" selected>10 Minutes</option>
                <option value="1h">1 Hour</option>
                <option value="1d">1 Day</option>
                <option value="1w">1 Week</option>
              </select>
            </div>
            <div class="form-group">
              <label>Reason</label>
              <input type="text" id="mod-reason" class="form-control" placeholder="E.g. Disruptive behavior, spamming" required>
            </div>
            <button type="submit" class="btn" id="btn-submit-action">Execute Action</button>
          </form>
        </div>

        <div class="panel-card">
          <div class="panel-header">
            <h2>📜 Server Audit History</h2>
            <button class="btn btn-secondary" onclick="loadModLogs()" style="padding: 6px 14px; font-size: 0.78rem;">🔄 Refresh</button>
          </div>
          <div style="overflow-x: auto; max-height: 480px; overflow-y: auto;">
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Action</th>
                  <th>Target</th>
                  <th>Moderator</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody id="logs-table-body">
                <tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Loading logs...</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- SERVER SETTINGS TAB -->
    <div id="tab-settings" class="tab-pane">
      <div class="panel-card" style="max-width: 720px; margin: 0 auto;">
        <div class="panel-header">
          <h2>⚙️ Configure Server Channels</h2>
        </div>
        <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 20px;">
          Customize which channels on <strong id="settings-guild-name">this server</strong> receive notifications, welcome guides, and rules.
        </p>
        <form id="settings-form" onsubmit="saveServerSettings(event)">
          <div class="form-group">
            <label>Welcome Channel</label>
            <select id="setting-welcome-channel" class="form-control">
              <option value="">(None / Auto-detect #welcome)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Rules Channel</label>
            <select id="setting-rules-channel" class="form-control">
              <option value="">(None / Auto-detect #rules)</option>
            </select>
          </div>
          <div class="form-group">
            <label>YouTube Live Stream Alert Channel</label>
            <select id="setting-stream-channel" class="form-control">
              <option value="">(None / Auto-detect #live-streams)</option>
            </select>
          </div>
          <div class="form-group">
            <label>YouTube Videos & Shorts Channel</label>
            <select id="setting-video-channel" class="form-control">
              <option value="">(None / Auto-detect #videos)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Stream Ping Role</label>
            <select id="setting-ping-role" class="form-control">
              <option value="">(None / Auto-detect @Stream Alert)</option>
            </select>
          </div>
          <button type="submit" class="btn">💾 Save Server Settings</button>
        </form>
      </div>
    </div>

    <!-- EMBEDS TAB -->
    <div id="tab-embeds" class="tab-pane">
      <div class="grid-2">
        <div class="panel-card">
          <div class="panel-header">
            <h2>👋 Welcome Embed</h2>
            <button class="btn btn-secondary" onclick="syncEmbed('welcome')">🔄 Sync to Discord</button>
          </div>
          <pre id="welcome-preview" style="background: #0b0b12; padding: 16px; border-radius: 10px; font-size: 0.82rem; color: #d0d0e0; white-space: pre-wrap; max-height: 400px; overflow-y: auto;">Loading welcome embed...</pre>
        </div>
        <div class="panel-card">
          <div class="panel-header">
            <h2>📜 Rules Embed</h2>
            <button class="btn btn-secondary" onclick="syncEmbed('rules')">🔄 Sync to Discord</button>
          </div>
          <pre id="rules-preview" style="background: #0b0b12; padding: 16px; border-radius: 10px; font-size: 0.82rem; color: #d0d0e0; white-space: pre-wrap; max-height: 400px; overflow-y: auto;">Loading rules embed...</pre>
        </div>
      </div>
    </div>
  </main>

  <!-- AUTH MODAL -->
  <div class="modal-overlay" id="auth-modal">
    <div class="modal-card">
      <img src="https://yt3.googleusercontent.com/O143rEtFVDnaNLx5zkY4QcYIXpKuUMIWkAN_m7ZJeuE5qCGhPMXJqWzHhiChGeJtWZq_lEFKkQ=s900-c-k-c0x00ffffff-no-rj" alt="MissJey" style="width: 60px; height: 60px; border-radius: 50%; border: 2px solid var(--accent); margin-bottom: 14px;">
      <h3>Admin Authentication</h3>
      <p>Log in with your Discord account to view and manage servers you have Administrator or Manage Server permissions in.</p>

      <div id="discord-oauth-section">
        <a id="discord-login-btn" href="/auth/discord" class="btn btn-discord" style="width: 100%; justify-content: center; text-decoration: none; padding: 12px; font-size: 0.95rem;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.894.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>
          Login with Discord
        </a>
      </div>

      <div class="auth-divider">OR USE MASTER PASSCODE</div>

      <form onsubmit="loginWithPin(event)">
        <input type="password" id="pin-input" class="form-control" placeholder="Enter Master Admin PIN" style="margin-bottom: 14px; text-align: center;" required>
        <button type="submit" class="btn btn-secondary" style="width: 100%; justify-content: center;">Authenticate with PIN</button>
      </form>
    </div>
  </div>

  <script>
    let authorizedGuilds = [];
    let currentGuildId = "";

    async function init() {
      try {
        const res = await fetch('/api/auth/me');
        const data = await res.json();
        
        if (!data.authenticated) {
          document.getElementById('auth-modal').classList.add('active');
          return;
        }

        document.getElementById('auth-modal').classList.remove('active');
        document.getElementById('user-name').textContent = data.user.name;
        document.getElementById('user-avatar').src = data.user.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png';

        authorizedGuilds = data.guilds || [];
        const selector = document.getElementById('server-select');
        selector.innerHTML = '';

        if (authorizedGuilds.length === 0) {
          selector.innerHTML = '<option value="">No authorized servers found</option>';
          alert("You are not an Administrator in any server where Jey's Bot is installed!");
          return;
        }

        authorizedGuilds.forEach(g => {
          const opt = document.createElement('option');
          opt.value = g.id;
          opt.textContent = g.name + (g.is_owner ? ' 👑' : '');
          selector.appendChild(opt);
        });

        // Restore last selected server or choose first
        const savedGuildId = localStorage.getItem('jeysbot_current_guild');
        if (savedGuildId && authorizedGuilds.find(g => g.id === savedGuildId)) {
          currentGuildId = savedGuildId;
          selector.value = currentGuildId;
        } else {
          currentGuildId = authorizedGuilds[0].id;
          selector.value = currentGuildId;
        }

        onServerChanged();
      } catch (e) {
        console.error("Init failed:", e);
      }
    }

    function onServerChanged() {
      const selector = document.getElementById('server-select');
      currentGuildId = selector.value;
      localStorage.setItem('jeysbot_current_guild', currentGuildId);
      
      const guild = authorizedGuilds.find(g => g.id === currentGuildId);
      if (guild) {
        document.getElementById('server-display-name').textContent = guild.name;
        document.getElementById('stat-guild-name').textContent = guild.name;
        document.getElementById('settings-guild-name').textContent = guild.name;
      }

      loadStats();
      loadMembers();
      loadModLogs();
      loadServerSettings();
      loadEmbedPreviews();
    }

    function switchTab(tabId) {
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById('tab-' + tabId).classList.add('active');
      event.currentTarget.classList.add('active');
    }

    function toggleDurationField() {
      const action = document.getElementById('mod-action').value;
      document.getElementById('duration-group').style.display = action === 'TIMEOUT' ? 'block' : 'none';
    }

    async function loadStats() {
      if (!currentGuildId) return;
      try {
        const res = await fetch(`/api/stats?guild_id=${currentGuildId}`);
        if (!res.ok) return;
        const d = await res.json();
        document.getElementById('stat-members').textContent = d.member_count;
        document.getElementById('stat-ping').textContent = d.ping_ms + ' ms';
        document.getElementById('stat-ram').textContent = d.memory_mb + ' MB';
        document.getElementById('stat-uptime').textContent = d.uptime_str;
      } catch (e) { console.error(e); }
    }

    async function loadMembers() {
      if (!currentGuildId) return;
      try {
        const res = await fetch(`/api/members?guild_id=${currentGuildId}`);
        if (!res.ok) return;
        const members = await res.json();
        const sel = document.getElementById('mod-target');
        sel.innerHTML = '<option value="" disabled selected>Select a member...</option>';
        members.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = `${m.name} (@${m.tag})`;
          sel.appendChild(opt);
        });
      } catch (e) { console.error(e); }
    }

    async function loadModLogs() {
      if (!currentGuildId) return;
      try {
        const res = await fetch(`/api/moderation/logs?guild_id=${currentGuildId}`);
        if (!res.ok) return;
        const logs = await res.json();
        const tbody = document.getElementById('logs-table-body');
        if (logs.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">No moderation events recorded for this server yet.</td></tr>';
          return;
        }
        tbody.innerHTML = logs.map(l => `
          <tr>
            <td><strong>#${l.id}</strong></td>
            <td><span class="tag tag-${l.action.toLowerCase()}">${l.action}</span></td>
            <td>${escapeHtml(l.target_name)}</td>
            <td>${escapeHtml(l.moderator_name)}</td>
            <td>${escapeHtml(l.reason)}${l.duration ? ' (' + l.duration + ')' : ''}</td>
          </tr>
        `).join('');
      } catch (e) { console.error(e); }
    }

    async function loadServerSettings() {
      if (!currentGuildId) return;
      try {
        const res = await fetch(`/api/guild/channels?guild_id=${currentGuildId}`);
        if (!res.ok) return;
        const data = await res.json();

        // Populate channels
        const populateSelect = (id, list, currentVal) => {
          const el = document.getElementById(id);
          el.innerHTML = '<option value="">(None / Default)</option>';
          list.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = '#' + item.name;
            if (item.id === currentVal) opt.selected = true;
            el.appendChild(opt);
          });
        };

        const populateRoles = (id, list, currentVal) => {
          const el = document.getElementById(id);
          el.innerHTML = '<option value="">(None)</option>';
          list.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = '@' + item.name;
            if (item.id === currentVal) opt.selected = true;
            el.appendChild(opt);
          });
        };

        populateSelect('setting-welcome-channel', data.channels, data.settings.welcome_channel_id);
        populateSelect('setting-rules-channel', data.channels, data.settings.rules_channel_id);
        populateSelect('setting-stream-channel', data.channels, data.settings.stream_channel_id);
        populateSelect('setting-video-channel', data.channels, data.settings.video_channel_id);
        populateRoles('setting-ping-role', data.roles, data.settings.stream_ping_role_id);
      } catch (e) { console.error(e); }
    }

    async function saveServerSettings(e) {
      e.preventDefault();
      if (!currentGuildId) return;
      try {
        const body = {
          guild_id: currentGuildId,
          welcome_channel_id: document.getElementById('setting-welcome-channel').value,
          rules_channel_id: document.getElementById('setting-rules-channel').value,
          stream_channel_id: document.getElementById('setting-stream-channel').value,
          video_channel_id: document.getElementById('setting-video-channel').value,
          stream_ping_role_id: document.getElementById('setting-ping-role').value
        };
        const res = await fetch('/api/guild/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        const d = await res.json();
        if (d.success) {
          alert('✅ Server settings saved successfully!');
        } else {
          alert('❌ Failed to save: ' + (d.error || 'Unknown error'));
        }
      } catch (err) {
        alert('❌ Error: ' + err.message);
      }
    }

    async function executeModAction(e) {
      e.preventDefault();
      if (!currentGuildId) return;
      const targetId = document.getElementById('mod-target').value;
      const action = document.getElementById('mod-action').value;
      const duration = document.getElementById('mod-duration').value;
      const reason = document.getElementById('mod-reason').value;

      try {
        const res = await fetch('/api/moderation/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            guild_id: currentGuildId,
            target_id: targetId,
            action: action,
            duration: duration,
            reason: reason
          })
        });
        const d = await res.json();
        if (d.success) {
          alert(`✅ Successfully executed ${action}!`);
          document.getElementById('mod-reason').value = '';
          loadModLogs();
          loadMembers();
        } else {
          alert('❌ Action failed: ' + (d.error || 'Unknown error'));
        }
      } catch (err) {
        alert('❌ Error: ' + err.message);
      }
    }

    async function loadEmbedPreviews() {
      if (!currentGuildId) return;
      try {
        const [w, r] = await Promise.all([
          fetch(`/api/embeds/welcome?guild_id=${currentGuildId}`).then(res => res.json()),
          fetch(`/api/embeds/rules?guild_id=${currentGuildId}`).then(res => res.json())
        ]);
        document.getElementById('welcome-preview').textContent = w.content || 'None';
        document.getElementById('rules-preview').textContent = r.content || 'None';
      } catch (e) { console.error(e); }
    }

    async function syncEmbed(type) {
      if (!currentGuildId) return;
      try {
        const res = await fetch(`/api/embeds/${type}/sync`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ guild_id: currentGuildId })
        });
        const d = await res.json();
        if (d.success) {
          alert(`✅ ${type.toUpperCase()} embed synced to Discord!`);
          loadEmbedPreviews();
        } else {
          alert('❌ Sync failed: ' + (d.error || 'Unknown error'));
        }
      } catch (e) { alert('❌ Error: ' + e.message); }
    }

    async function loginWithPin(e) {
      e.preventDefault();
      const pin = document.getElementById('pin-input').value;
      try {
        const res = await fetch('/auth/pin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pin: pin })
        });
        const d = await res.json();
        if (d.success) {
          window.location.reload();
        } else {
          alert('❌ Invalid PIN!');
        }
      } catch (err) {
        alert('❌ Login error: ' + err.message);
      }
    }

    async function logout() {
      await fetch('/auth/logout', { method: 'POST' });
      window.location.reload();
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Auto-refresh telemetry every 6 seconds
    setInterval(loadStats, 6000);
    window.onload = init;
  </script>
</body>
</html>
"""

class DashboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.setup_routes()

    def setup_routes(self):
        # UI & Auth
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/auth/discord", self.handle_discord_login)
        self.app.router.add_get("/auth/callback", self.handle_discord_callback)
        self.app.router.add_post("/auth/pin", self.handle_pin_login)
        self.app.router.add_post("/auth/logout", self.handle_logout)
        self.app.router.add_get("/api/auth/me", self.api_auth_me)

        # Multi-Server REST APIs (Protected)
        self.app.router.add_get("/api/stats", self.api_stats)
        self.app.router.add_get("/api/members", self.api_members)
        self.app.router.add_get("/api/moderation/logs", self.api_mod_logs)
        self.app.router.add_post("/api/moderation/action", self.api_mod_action)
        self.app.router.add_get("/api/guild/channels", self.api_guild_channels)
        self.app.router.add_post("/api/guild/settings", self.api_guild_settings)
        self.app.router.add_get("/api/embeds/welcome", self.api_get_welcome)
        self.app.router.add_post("/api/embeds/welcome/sync", self.api_sync_welcome)
        self.app.router.add_get("/api/embeds/rules", self.api_get_rules)
        self.app.router.add_post("/api/embeds/rules/sync", self.api_sync_rules)

    async def cog_load(self):
        """Starts the aiohttp web server on port 5000."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, "0.0.0.0", DASHBOARD_PORT)
            await self.site.start()
            logger.info(f"🌐 Multi-Server Dashboard Web Server active on http://0.0.0.0:{DASHBOARD_PORT}")
        except Exception as e:
            logger.error(f"Failed to start Dashboard Web Server: {e}", exc_info=True)

    def cog_unload(self):
        if self.runner:
            asyncio.create_task(self.runner.cleanup())

    # --- Authentication & Session Helpers ---
    def get_session(self, request: web.Request) -> Optional[Dict[str, Any]]:
        # 1. Cookie
        token = request.cookies.get("jeysbot_session")
        if token and token in SESSIONS:
            sess = SESSIONS[token]
            if sess["expires"] > time.time():
                return sess
            else:
                del SESSIONS[token]

        # 2. Bearer Header (fallback / API)
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split("Bearer ")[1].strip()
            if token == DASHBOARD_PIN:
                # Master Admin Session
                all_guilds = [str(g.id) for g in self.bot.guilds]
                return {
                    "user": {"name": "Bot Owner", "avatar": MISSJEY_AVATAR, "id": "0"},
                    "allowed_guild_ids": set(all_guilds),
                    "is_master": True,
                    "expires": time.time() + 3600
                }
            if token in SESSIONS:
                sess = SESSIONS[token]
                if sess["expires"] > time.time():
                    return sess
        return None

    def get_authorized_guild(self, request: web.Request, guild_id_str: str) -> Optional[discord.Guild]:
        sess = self.get_session(request)
        if not sess:
            raise web.HTTPUnauthorized(text=json.dumps({"error": "Login required"}), content_type="application/json")
        
        if guild_id_str not in sess["allowed_guild_ids"]:
            raise web.HTTPForbidden(text=json.dumps({"error": "Unauthorized: You do not have permissions for this server."}), content_type="application/json")

        guild = self.bot.get_guild(int(guild_id_str))
        if not guild:
            raise web.HTTPNotFound(text=json.dumps({"error": "Bot is not in this guild."}), content_type="application/json")
        return guild

    # --- UI & Auth Handlers ---
    async def handle_index(self, request: web.Request):
        return web.Response(text=HTML_DASHBOARD, content_type="text/html")

    async def handle_discord_login(self, request: web.Request):
        proto = request.headers.get("X-Forwarded-Proto", "https" if "trycloudflare" in request.host else "http")
        redirect_uri = f"{proto}://{request.host}/auth/callback"
        
        url = (
            f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code&scope=identify%20guilds"
        )
        return web.HTTPFound(url)

    async def handle_discord_callback(self, request: web.Request):
        code = request.query.get("code")
        if not code:
            return web.HTTPBadRequest(text="Missing OAuth2 code")

        proto = request.headers.get("X-Forwarded-Proto", "https" if "trycloudflare" in request.host else "http")
        redirect_uri = f"{proto}://{request.host}/auth/callback"

        data = {
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri
        }

        async with ClientSession() as session:
            # 1. Exchange code for access token
            async with session.post("https://discord.com/api/oauth2/token", data=data) as resp:
                token_data = await resp.json()

            access_token = token_data.get("access_token")
            if not access_token:
                logger.error(f"Failed to get OAuth token: {token_data}")
                return web.HTTPBadRequest(text=f"Failed to authenticate with Discord: {token_data.get('error_description', 'Invalid token')}")

            headers = {"Authorization": f"Bearer {access_token}"}

            # 2. Fetch User Profile
            async with session.get("https://discord.com/api/users/@me", headers=headers) as resp:
                user_data = await resp.json()

            # 3. Fetch User Guilds
            async with session.get("https://discord.com/api/users/@me/guilds", headers=headers) as resp:
                user_guilds = await resp.json()

        # 4. Filter guilds where user has MANAGE_GUILD (0x20) or ADMINISTRATOR (0x8) or is Owner
        allowed_guild_ids = set()
        user_managed_guilds = []

        for g in user_guilds:
            gid = str(g.get("id"))
            perms = int(g.get("permissions", "0"))
            is_owner = g.get("owner", False)
            is_admin = is_owner or bool(perms & 0x8) or bool(perms & 0x20)

            # Check if bot is also in this guild
            bot_guild = self.bot.get_guild(int(gid))
            if is_admin and bot_guild:
                allowed_guild_ids.add(gid)
                user_managed_guilds.append({
                    "id": gid,
                    "name": bot_guild.name,
                    "is_owner": is_owner
                })

        # Generate session
        token = secrets.token_urlsafe(32)
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_data['id']}/{user_data.get('avatar')}.png" if user_data.get('avatar') else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        SESSIONS[token] = {
            "user": {
                "id": str(user_data["id"]),
                "name": user_data.get("global_name") or user_data.get("username"),
                "avatar": avatar_url
            },
            "allowed_guild_ids": allowed_guild_ids,
            "is_master": False,
            "expires": time.time() + (86400 * 7) # 7 days
        }

        response = web.HTTPFound("/")
        response.set_cookie("jeysbot_session", token, max_age=86400 * 7, httponly=True, samesite="Lax")
        return response

    async def handle_pin_login(self, request: web.Request):
        data = await request.json()
        pin = data.get("pin", "")
        if pin == DASHBOARD_PIN:
            token = secrets.token_urlsafe(32)
            all_guild_ids = {str(g.id) for g in self.bot.guilds}
            SESSIONS[token] = {
                "user": {
                    "id": "owner",
                    "name": "Server Admin (Master)",
                    "avatar": MISSJEY_AVATAR
                },
                "allowed_guild_ids": all_guild_ids,
                "is_master": True,
                "expires": time.time() + (86400 * 7)
            }
            response = web.json_response({"success": True})
            response.set_cookie("jeysbot_session", token, max_age=86400 * 7, httponly=True, samesite="Lax")
            return response
        return web.json_response({"success": False, "error": "Invalid PIN"}, status=401)

    async def handle_logout(self, request: web.Request):
        token = request.cookies.get("jeysbot_session")
        if token and token in SESSIONS:
            del SESSIONS[token]
        response = web.json_response({"success": True})
        response.del_cookie("jeysbot_session")
        return response

    async def api_auth_me(self, request: web.Request):
        sess = self.get_session(request)
        if not sess:
            return web.json_response({"authenticated": False, "oauth_enabled": bool(DISCORD_CLIENT_SECRET)})
        
        guilds = []
        for gid in sess["allowed_guild_ids"]:
            g = self.bot.get_guild(int(gid))
            if g:
                guilds.append({
                    "id": str(g.id),
                    "name": g.name,
                    "member_count": g.member_count,
                    "is_owner": (str(g.owner_id) == sess["user"]["id"]) if not sess.get("is_master") else True
                })

        return web.json_response({
            "authenticated": True,
            "user": sess["user"],
            "guilds": guilds
        })

    # --- Multi-Server REST API Endpoints ---
    async def api_stats(self, request: web.Request):
        gid = request.query.get("guild_id", "")
        guild = self.get_authorized_guild(request, gid)

        uptime_sec = int(time.time() - START_TIME)
        uptime_str = str(timedelta(seconds=uptime_sec))
        
        process = psutil.Process()
        proc_mem = process.memory_info().rss / (1024 * 1024)

        return web.json_response({
            "guild_id": str(guild.id),
            "guild_name": guild.name,
            "member_count": guild.member_count,
            "ping_ms": round(self.bot.latency * 1000, 1),
            "memory_mb": round(proc_mem, 1),
            "uptime_str": uptime_str
        })

    async def api_members(self, request: web.Request):
        gid = request.query.get("guild_id", "")
        guild = self.get_authorized_guild(request, gid)

        members_data = []
        for m in guild.members:
            if not m.bot:
                members_data.append({
                    "id": str(m.id),
                    "name": m.display_name,
                    "tag": str(m),
                    "avatar": m.display_avatar.url
                })
        return web.json_response(members_data[:100])

    async def api_mod_logs(self, request: web.Request):
        gid = request.query.get("guild_id", "")
        guild = self.get_authorized_guild(request, gid)
        logs = await db.get_mod_logs(str(guild.id), limit=50)
        return web.json_response(logs)

    async def api_mod_action(self, request: web.Request):
        data = await request.json()
        gid = str(data.get("guild_id", ""))
        guild = self.get_authorized_guild(request, gid)
        sess = self.get_session(request)

        target_id = int(data.get("target_id", 0))
        action = data.get("action", "").upper()
        duration_str = data.get("duration", "10m")
        reason = data.get("reason", "Action taken via Web Dashboard")

        target = guild.get_member(target_id)
        if not target and action not in ["BAN"]:
            return web.json_response({"success": False, "error": "Target member not found in this server."})

        mod_name = sess["user"]["name"]
        mod_id = sess["user"]["id"]

        try:
            if action == "TIMEOUT":
                duration = parse_duration(duration_str)
                await target.timeout(duration, reason=reason)
                case_id = await db.log_mod_action(
                    guild_id=str(guild.id),
                    action="TIMEOUT",
                    target_id=str(target.id),
                    target_name=str(target),
                    moderator_id=mod_id,
                    moderator_name=mod_name,
                    reason=reason,
                    duration=duration_str
                )
                return web.json_response({"success": True, "case_id": case_id})

            elif action == "REMOVE_TIMEOUT":
                await target.timeout(None, reason=reason)
                case_id = await db.log_mod_action(
                    guild_id=str(guild.id),
                    action="REMOVE_TIMEOUT",
                    target_id=str(target.id),
                    target_name=str(target),
                    moderator_id=mod_id,
                    moderator_name=mod_name,
                    reason=reason
                )
                return web.json_response({"success": True, "case_id": case_id})

            elif action == "WARN":
                warn_id = await db.add_warning(str(guild.id), str(target.id), mod_id, reason)
                case_id = await db.log_mod_action(
                    guild_id=str(guild.id),
                    action="WARN",
                    target_id=str(target.id),
                    target_name=str(target),
                    moderator_id=mod_id,
                    moderator_name=mod_name,
                    reason=reason
                )
                return web.json_response({"success": True, "case_id": case_id})

            elif action == "KICK":
                await target.kick(reason=reason)
                case_id = await db.log_mod_action(
                    guild_id=str(guild.id),
                    action="KICK",
                    target_id=str(target.id),
                    target_name=str(target),
                    moderator_id=mod_id,
                    moderator_name=mod_name,
                    reason=reason
                )
                return web.json_response({"success": True, "case_id": case_id})

            elif action == "BAN":
                await guild.ban(discord.Object(id=target_id), reason=reason)
                case_id = await db.log_mod_action(
                    guild_id=str(guild.id),
                    action="BAN",
                    target_id=str(target_id),
                    target_name=str(target) if target else f"User ID {target_id}",
                    moderator_id=mod_id,
                    moderator_name=mod_name,
                    reason=reason
                )
                return web.json_response({"success": True, "case_id": case_id})

            else:
                return web.json_response({"success": False, "error": f"Unknown action: {action}"})

        except discord.Forbidden:
            return web.json_response({"success": False, "error": "Bot lacks permissions or target user outranks the bot."})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)})

    async def api_guild_channels(self, request: web.Request):
        gid = request.query.get("guild_id", "")
        guild = self.get_authorized_guild(request, gid)

        channels = [
            {"id": str(c.id), "name": c.name}
            for c in guild.text_channels
        ]
        roles = [
            {"id": str(r.id), "name": r.name}
            for r in guild.roles if not r.is_default()
        ]
        settings = await db.get_server_settings(str(guild.id)) or {}

        return web.json_response({
            "channels": channels,
            "roles": roles,
            "settings": settings
        })

    async def api_guild_settings(self, request: web.Request):
        data = await request.json()
        gid = str(data.get("guild_id", ""))
        guild = self.get_authorized_guild(request, gid)

        clean_data = {
            "welcome_channel_id": data.get("welcome_channel_id") or None,
            "rules_channel_id": data.get("rules_channel_id") or None,
            "stream_channel_id": data.get("stream_channel_id") or None,
            "video_channel_id": data.get("video_channel_id") or None,
            "stream_ping_role_id": data.get("stream_ping_role_id") or None
        }

        await db.update_server_settings(str(guild.id), **clean_data)
        return web.json_response({"success": True})

    async def api_get_welcome(self, request: web.Request):
        gid = request.query.get("guild_id", "")
        guild = self.get_authorized_guild(request, gid)
        from cogs.welcome import build_welcome_embed
        embed = build_welcome_embed(guild)
        return web.json_response({"content": embed.description or ""})

    async def api_sync_welcome(self, request: web.Request):
        data = await request.json()
        gid = str(data.get("guild_id", ""))
        guild = self.get_authorized_guild(request, gid)

        welcome_cog = self.bot.get_cog("Welcome")
        if not welcome_cog:
            return web.json_response({"success": False, "error": "Welcome cog not loaded"})
        
        # Call setup for this specific guild
        channel = None
        settings = await db.get_server_settings(str(guild.id))
        if settings and settings.get("welcome_channel_id"):
            channel = guild.get_channel(int(settings["welcome_channel_id"]))
        if not channel:
            channel = discord.utils.get(guild.text_channels, name="welcome")

        if not channel:
            return web.json_response({"success": False, "error": "No #welcome channel found in this server."})

        from cogs.welcome import build_welcome_embed
        embed = build_welcome_embed(guild)
        await channel.send(embed=embed)
        return web.json_response({"success": True})

    async def api_get_rules(self, request: web.Request):
        gid = request.query.get("guild_id", "")
        guild = self.get_authorized_guild(request, gid)
        from cogs.rules import build_rules_embed
        embed = build_rules_embed()
        return web.json_response({"content": embed.description or ""})

    async def api_sync_rules(self, request: web.Request):
        data = await request.json()
        gid = str(data.get("guild_id", ""))
        guild = self.get_authorized_guild(request, gid)

        rules_cog = self.bot.get_cog("Rules")
        if not rules_cog:
            return web.json_response({"success": False, "error": "Rules cog not loaded"})

        channel = None
        settings = await db.get_server_settings(str(guild.id))
        if settings and settings.get("rules_channel_id"):
            channel = guild.get_channel(int(settings["rules_channel_id"]))
        if not channel:
            channel = discord.utils.get(guild.text_channels, name="rules")

        if not channel:
            return web.json_response({"success": False, "error": "No #rules channel found in this server."})

        from cogs.rules import build_rules_embed
        embed = build_rules_embed()
        await channel.send(embed=embed)
        return web.json_response({"success": True})

async def setup(bot: commands.Bot):
    await bot.add_cog(DashboardCog(bot))
