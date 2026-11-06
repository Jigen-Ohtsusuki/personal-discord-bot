import os
import sys
import time
import json
import psutil
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import discord
from discord.ext import commands
from aiohttp import web

import config
from database import db
from cogs.moderation import parse_duration, format_duration

logger = logging.getLogger("DashboardCog")

DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))
DASHBOARD_PIN = os.getenv("DASHBOARD_PIN", "jey2026") # Admin access PIN
START_TIME = time.time()

MISSJEY_AVATAR = "https://yt3.googleusercontent.com/O143rEtFVDnaNLx5zkY4QcYIXpKuUMIWkAN_m7ZJeuE5qCGhPMXJqWzHhiChGeJtWZq_lEFKkQ=s900-c-k-c0x00ffffff-no-rj"

HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Jey's Bot 💜 • Control Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0b0f;
      --card-bg: #14141c;
      --card-border: #232330;
      --accent: #AA88FF;
      --accent-hover: #9872ff;
      --accent-glow: rgba(170, 136, 255, 0.25);
      --text: #f0f0f5;
      --text-muted: #8e8ea6;
      --success: #4ade80;
      --danger: #f87171;
      --warning: #fbbf24;
      --radius: 14px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; }
    header { background: #12121a; border-bottom: 1px solid var(--card-border); padding: 16px 28px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 50; }
    .brand { display: flex; align-items: center; gap: 14px; }
    .brand img { width: 44px; height: 44px; border-radius: 50%; border: 2px solid var(--accent); box-shadow: 0 0 15px var(--accent-glow); }
    .brand h1 { font-size: 1.25rem; font-weight: 800; background: linear-gradient(135deg, #fff, var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .brand span { font-size: 0.8rem; color: var(--text-muted); display: block; font-weight: 500; }
    .nav-tabs { display: flex; gap: 8px; }
    .tab-btn { background: transparent; border: none; color: var(--text-muted); font-size: 0.9rem; font-weight: 600; padding: 10px 18px; border-radius: 10px; cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center; gap: 8px; }
    .tab-btn:hover { color: #fff; background: rgba(255,255,255,0.05); }
    .tab-btn.active { color: #fff; background: var(--accent); box-shadow: 0 0 14px var(--accent-glow); }
    .status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 30px; font-size: 0.82rem; font-weight: 700; background: rgba(74, 222, 128, 0.12); color: var(--success); border: 1px solid rgba(74, 222, 128, 0.3); }
    .status-dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; box-shadow: 0 0 8px var(--success); animation: pulse 2s infinite; }
    @keyframes pulse { 0% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.9); } 100% { opacity: 1; transform: scale(1); } }
    main { flex: 1; max-width: 1240px; width: 100%; margin: 24px auto; padding: 0 20px; }
    .tab-pane { display: none; }
    .tab-pane.active { display: block; }
    .grid-4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; margin-bottom: 24px; }
    .stat-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 20px; transition: transform 0.2s, border-color 0.2s; position: relative; overflow: hidden; }
    .stat-card:hover { transform: translateY(-2px); border-color: rgba(170, 136, 255, 0.4); }
    .stat-card .label { font-size: 0.82rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-card .value { font-size: 1.8rem; font-weight: 800; margin-top: 8px; color: #fff; }
    .stat-card .sub { font-size: 0.78rem; color: var(--text-muted); margin-top: 6px; }
    .panel-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 24px; margin-bottom: 24px; }
    .panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--card-border); }
    .panel-header h2 { font-size: 1.15rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 10px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th { text-align: left; padding: 12px 14px; color: var(--text-muted); font-weight: 600; border-bottom: 1px solid var(--card-border); }
    td { padding: 14px; border-bottom: 1px solid rgba(255,255,255,0.03); }
    tr:hover td { background: rgba(255,255,255,0.02); }
    .tag { display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; }
    .tag-timeout { background: rgba(251, 191, 36, 0.15); color: var(--warning); border: 1px solid rgba(251, 191, 36, 0.3); }
    .tag-kick { background: rgba(249, 115, 22, 0.15); color: #f97316; border: 1px solid rgba(249, 115, 22, 0.3); }
    .tag-ban { background: rgba(248, 113, 113, 0.15); color: var(--danger); border: 1px solid rgba(248, 113, 113, 0.3); }
    .tag-warn { background: rgba(244, 208, 63, 0.15); color: #f4d03f; border: 1px solid rgba(244, 208, 63, 0.3); }
    .form-group { margin-bottom: 16px; }
    .form-group label { display: block; font-size: 0.82rem; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
    input[type="text"], input[type="password"], textarea, select { width: 100%; background: #0e0e14; border: 1px solid var(--card-border); color: #fff; padding: 12px 14px; border-radius: 10px; font-size: 0.9rem; transition: border-color 0.2s; outline: none; }
    input[type="text"]:focus, input[type="password"]:focus, textarea:focus, select:focus { border-color: var(--accent); box-shadow: 0 0 10px var(--accent-glow); }
    textarea { resize: vertical; min-height: 120px; }
    .btn { background: var(--accent); color: #fff; font-weight: 700; border: none; padding: 12px 22px; border-radius: 10px; cursor: pointer; transition: all 0.2s; font-size: 0.9rem; display: inline-flex; align-items: center; gap: 8px; }
    .btn:hover { background: var(--accent-hover); box-shadow: 0 0 16px var(--accent-glow); transform: translateY(-1px); }
    .btn-secondary { background: #232330; color: var(--text); }
    .btn-secondary:hover { background: #2f2f40; box-shadow: none; }
    .btn-danger { background: #dc2626; }
    .btn-danger:hover { background: #b91c1c; box-shadow: 0 0 16px rgba(220, 38, 38, 0.4); }
    .actions-row { display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
    .preview-box { background: #0c0c12; border: 1px solid var(--card-border); border-left: 4px solid var(--accent); border-radius: 8px; padding: 18px; margin-top: 14px; white-space: pre-wrap; font-size: 0.88rem; line-height: 1.6; color: #ddd; max-height: 380px; overflow-y: auto; }
    #toast { position: fixed; bottom: 24px; right: 24px; background: #1c1c28; border: 1px solid var(--accent); color: #fff; padding: 14px 22px; border-radius: 12px; font-size: 0.9rem; font-weight: 600; box-shadow: 0 8px 30px rgba(0,0,0,0.5); z-index: 100; transform: translateY(100px); opacity: 0; transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
    #toast.show { transform: translateY(0); opacity: 1; }
    /* Modal */
    .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.75); backdrop-filter: blur(4px); display: none; align-items: center; justify-content: center; z-index: 99; }
    .modal-overlay.active { display: flex; }
    .modal-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 28px; max-width: 440px; width: 90%; box-shadow: 0 20px 50px rgba(0,0,0,0.6); }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <img src="https://yt3.googleusercontent.com/O143rEtFVDnaNLx5zkY4QcYIXpKuUMIWkAN_m7ZJeuE5qCGhPMXJqWzHhiChGeJtWZq_lEFKkQ=s900-c-k-c0x00ffffff-no-rj" alt="MissJey">
      <div>
        <h1>Jey's Bot 💜 Dashboard</h1>
        <span>MissJey Community • Control Center</span>
      </div>
    </div>
    <nav class="nav-tabs">
      <button class="tab-btn active" onclick="switchTab('overview')">📊 Overview</button>
      <button class="tab-btn" onclick="switchTab('moderation')">🛡️ Moderation</button>
      <button class="tab-btn" onclick="switchTab('youtube')">🎬 YouTube</button>
      <button class="tab-btn" onclick="switchTab('embeds')">📜 Welcome & Rules</button>
    </nav>
    <div class="status-badge">
      <span class="status-dot"></span>
      <span id="header-status">Online (24/7 VPS)</span>
    </div>
  </header>

  <main>
    <!-- OVERVIEW TAB -->
    <div id="tab-overview" class="tab-pane active">
      <div class="grid-4">
        <div class="stat-card">
          <div class="label">Server Members</div>
          <div class="value" id="stat-members">—</div>
          <div class="sub">JigenxOhtsusuki</div>
        </div>
        <div class="stat-card">
          <div class="label">Bot Latency</div>
          <div class="value" id="stat-ping">— ms</div>
          <div class="sub">Discord Gateway</div>
        </div>
        <div class="stat-card">
          <div class="label">VPS Memory Usage</div>
          <div class="value" id="stat-ram">—</div>
          <div class="sub" id="stat-ram-sub">4 GB Total NVMe VPS</div>
        </div>
        <div class="stat-card">
          <div class="label">Bot Uptime</div>
          <div class="value" id="stat-uptime">—</div>
          <div class="sub">Continuous 24/7 Hosting</div>
        </div>
      </div>

      <div class="panel-card">
        <div class="panel-header">
          <h2>⚡ System Health & Server Details</h2>
          <button class="btn btn-secondary" onclick="fetchStatus()">🔄 Refresh Stats</button>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
          <div>
            <p style="color: var(--text-muted); font-size: 0.85rem;">Target Server</p>
            <p style="font-weight: 700; font-size: 1.05rem; margin-top: 4px;" id="guild-name">—</p>
          </div>
          <div>
            <p style="color: var(--text-muted); font-size: 0.85rem;">Dedicated Creator</p>
            <p style="font-weight: 700; font-size: 1.05rem; margin-top: 4px;">MissJey (@MissjeyGaming)</p>
          </div>
          <div>
            <p style="color: var(--text-muted); font-size: 0.85rem;">VPS Host IP</p>
            <p style="font-weight: 700; font-size: 1.05rem; margin-top: 4px;">198.73.57.222 (Ubuntu 24.04 LTS)</p>
          </div>
          <div>
            <p style="color: var(--text-muted); font-size: 0.85rem;">Push Engine</p>
            <p style="font-weight: 700; font-size: 1.05rem; margin-top: 4px; color: var(--success);">⚡ Real-Time WebSub (0 Polling)</p>
          </div>
        </div>
      </div>
    </div>

    <!-- MODERATION TAB -->
    <div id="tab-moderation" class="tab-pane">
      <div class="panel-card">
        <div class="panel-header">
          <h2>🛡️ Quick Moderation Action</h2>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px;">
          <div class="form-group">
            <label>Select Member</label>
            <select id="mod-member-select">
              <option value="">Loading members...</option>
            </select>
          </div>
          <div class="form-group">
            <label>Action</label>
            <select id="mod-action-type" onchange="toggleDurationField()">
              <option value="TIMEOUT">⏳ Timeout (Mute)</option>
              <option value="WARN">⚠️ Warn</option>
              <option value="KICK">👢 Kick</option>
              <option value="BAN">🔨 Ban</option>
              <option value="UNTIMEOUT">🔊 Remove Timeout</option>
            </select>
          </div>
          <div class="form-group" id="mod-duration-group">
            <label>Duration</label>
            <select id="mod-duration-select">
              <option value="60s">60 Seconds</option>
              <option value="5m">5 Minutes</option>
              <option value="10m" selected>10 Minutes</option>
              <option value="1h">1 Hour</option>
              <option value="1d">1 Day</option>
              <option value="7d">1 Week</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label>Reason for Punishment</label>
          <input type="text" id="mod-reason" placeholder="e.g. Breaking community guidelines in chat...">
        </div>
        <button class="btn btn-danger" onclick="executeModAction()">⚡ Execute Moderation Action</button>
      </div>

      <div class="panel-card">
        <div class="panel-header">
          <h2>📋 Moderation Audit Log Cases</h2>
          <button class="btn btn-secondary" onclick="fetchModLogs()">🔄 Refresh Cases</button>
        </div>
        <div style="overflow-x: auto;">
          <table>
            <thead>
              <tr>
                <th>Case #</th>
                <th>Action</th>
                <th>Target User</th>
                <th>Moderator</th>
                <th>Reason</th>
                <th>Duration</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody id="mod-logs-body">
              <tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 30px;">Loading cases...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- YOUTUBE TAB -->
    <div id="tab-youtube" class="tab-pane">
      <div class="panel-card">
        <div class="panel-header">
          <h2>🎬 YouTube Notification Routing</h2>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px;">
          <div class="stat-card">
            <div class="label">🔴 Live Streams</div>
            <div class="value" style="font-size: 1.2rem;">#live-streams</div>
            <div class="sub">Mentions @Stream Alert</div>
          </div>
          <div class="stat-card">
            <div class="label">🎬 Regular Videos</div>
            <div class="value" style="font-size: 1.2rem;">#videos</div>
            <div class="sub">Mentions @Video Alert</div>
          </div>
          <div class="stat-card">
            <div class="label">📱 YouTube Shorts</div>
            <div class="value" style="font-size: 1.2rem;">#shorts</div>
            <div class="sub">Mentions @Video Alert</div>
          </div>
        </div>
      </div>
    </div>

    <!-- EMBEDS TAB -->
    <div id="tab-embeds" class="tab-pane">
      <div class="panel-card">
        <div class="panel-header">
          <h2>📜 #welcome Guide Preview & Sync</h2>
          <button class="btn" onclick="syncWelcomeEmbed()">🚀 Sync & Update in Discord</button>
        </div>
        <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 12px;">This embed is pinned in <strong style="color: #fff;">#welcome</strong> and directs new members to rules, roles, announcements, and socials.</p>
        <div class="preview-box" id="welcome-preview-text">Loading #welcome preview...</div>
      </div>

      <div class="panel-card">
        <div class="panel-header">
          <h2>📜 #rules Embed Preview & Sync</h2>
          <button class="btn" onclick="syncRulesEmbed()">🚀 Sync & Update in Discord</button>
        </div>
        <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 12px;">The 10 official server guidelines and moderation enforcement policy in <strong style="color: #fff;">#rules</strong>.</p>
        <div class="preview-box" id="rules-preview-text">Loading #rules preview...</div>
      </div>
    </div>
  </main>

  <div id="toast"></div>

  <!-- Auth PIN Modal -->
  <div class="modal-overlay" id="auth-modal">
    <div class="modal-card">
      <h2 style="font-size: 1.2rem; font-weight: 800; margin-bottom: 8px;">🔐 Admin Access Required</h2>
      <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 18px;">Please enter the server security PIN to manage moderation and customizer settings.</p>
      <div class="form-group">
        <input type="password" id="auth-pin-input" placeholder="Enter PIN (Default: jey2026)">
      </div>
      <button class="btn" style="width: 100%; justify-content: center;" onclick="verifyPin()">Unlock Dashboard</button>
    </div>
  </div>

  <script>
    let ADMIN_PIN = localStorage.getItem("jeysbot_pin") || "jey2026";

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 3500);
    }

    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById('tab-' + tabId).classList.add('active');

      if (tabId === 'moderation') { fetchMembers(); fetchModLogs(); }
      if (tabId === 'embeds') { fetchEmbedPreviews(); }
    }

    function toggleDurationField() {
      const action = document.getElementById('mod-action-type').value;
      const group = document.getElementById('mod-duration-group');
      group.style.display = (action === 'TIMEOUT') ? 'block' : 'none';
    }

    async function fetchStatus() {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        document.getElementById('stat-members').innerText = data.member_count;
        document.getElementById('stat-ping').innerText = data.ping_ms + ' ms';
        document.getElementById('stat-ram').innerText = data.memory_mb + ' MB';
        document.getElementById('stat-uptime').innerText = data.uptime_str;
        document.getElementById('guild-name').innerText = data.guild_name;
      } catch (e) {
        console.error(e);
      }
    }

    async function fetchMembers() {
      try {
        const res = await fetch('/api/members');
        const members = await res.json();
        const select = document.getElementById('mod-member-select');
        select.innerHTML = members.map(m => `<option value="${m.id}">${m.name} (${m.tag})</option>`).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function fetchModLogs() {
      try {
        const res = await fetch('/api/moderation/logs');
        const logs = await res.json();
        const tbody = document.getElementById('mod-logs-body');
        if (!logs.length) {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 30px;">No moderation cases recorded yet.</td></tr>';
          return;
        }
        tbody.innerHTML = logs.map(l => {
          let tagClass = 'tag-warn';
          if (l.action === 'TIMEOUT') tagClass = 'tag-timeout';
          if (l.action === 'KICK') tagClass = 'tag-kick';
          if (l.action === 'BAN') tagClass = 'tag-ban';
          return `
            <tr>
              <td><strong>#${l.id}</strong></td>
              <td><span class="tag ${tagClass}">${l.action}</span></td>
              <td>${l.target_name} <span style="color:var(--text-muted); font-size:0.75rem;">(${l.target_id})</span></td>
              <td>${l.moderator_name}</td>
              <td>${l.reason || '—'}</td>
              <td>${l.duration || '—'}</td>
              <td style="color:var(--text-muted); font-size:0.8rem;">${new Date(l.created_at).toLocaleString()}</td>
            </tr>
          `;
        }).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function executeModAction() {
      const targetId = document.getElementById('mod-member-select').value;
      const action = document.getElementById('mod-action-type').value;
      const duration = document.getElementById('mod-duration-select').value;
      const reason = document.getElementById('mod-reason').value || "No reason specified";

      if (!targetId) {
        showToast("Please select a member first!");
        return;
      }

      try {
        const res = await fetch('/api/moderation/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + ADMIN_PIN },
          body: JSON.stringify({ target_id: targetId, action: action, duration: duration, reason: reason })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`✅ ${action} executed successfully! Case #${data.case_id}`);
          document.getElementById('mod-reason').value = "";
          fetchModLogs();
        } else {
          showToast(`❌ Error: ${data.error}`);
        }
      } catch (e) {
        showToast("❌ Failed to contact server.");
      }
    }

    async function fetchEmbedPreviews() {
      try {
        const resW = await fetch('/api/embeds/welcome');
        const dataW = await resW.json();
        document.getElementById('welcome-preview-text').innerText = dataW.content;

        const resR = await fetch('/api/embeds/rules');
        const dataR = await resR.json();
        document.getElementById('rules-preview-text').innerText = dataR.content;
      } catch (e) {
        console.error(e);
      }
    }

    async function syncWelcomeEmbed() {
      try {
        const res = await fetch('/api/embeds/welcome/sync', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + ADMIN_PIN }
        });
        const data = await res.json();
        if (data.success) showToast("✅ #welcome guide updated live in Discord!");
        else showToast("❌ Error: " + data.error);
      } catch (e) { showToast("❌ Update request failed."); }
    }

    async function syncRulesEmbed() {
      try {
        const res = await fetch('/api/embeds/rules/sync', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + ADMIN_PIN }
        });
        const data = await res.json();
        if (data.success) showToast("✅ #rules guidelines updated live in Discord!");
        else showToast("❌ Error: " + data.error);
      } catch (e) { showToast("❌ Update request failed."); }
    }

    function verifyPin() {
      const pin = document.getElementById('auth-pin-input').value;
      ADMIN_PIN = pin;
      localStorage.setItem("jeysbot_pin", pin);
      document.getElementById('auth-modal').classList.remove('active');
      showToast("🔐 PIN saved!");
    }

    // Auto-load status on page load and every 10 seconds
    fetchStatus();
    setInterval(fetchStatus, 10000);
  </script>
</body>
</html>
"""

class DashboardCog(commands.Cog, name="Dashboard"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.setup_routes()

    def setup_routes(self):
        # UI
        self.app.router.add_get("/", self.handle_index)
        
        # REST APIs
        self.app.router.add_get("/api/stats", self.api_stats)
        self.app.router.add_get("/api/members", self.api_members)
        self.app.router.add_get("/api/moderation/logs", self.api_mod_logs)
        self.app.router.add_post("/api/moderation/action", self.api_mod_action)
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
            logger.info(f"🌐 Dashboard Web Server active on http://0.0.0.0:{DASHBOARD_PORT}")
        except Exception as e:
            logger.error(f"Failed to start Dashboard Web Server: {e}", exc_info=True)

    def cog_unload(self):
        if self.runner:
            asyncio.create_task(self.runner.cleanup())

    def check_auth(self, request: web.Request) -> bool:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split("Bearer ")[1].strip()
            return token == DASHBOARD_PIN
        return False

    async def handle_index(self, request: web.Request):
        return web.Response(text=HTML_DASHBOARD, content_type="text/html")

    async def api_stats(self, request: web.Request):
        guild = self.bot.guilds[0] if self.bot.guilds else None
        uptime_sec = int(time.time() - START_TIME)
        uptime_str = str(timedelta(seconds=uptime_sec))
        
        mem = psutil.virtual_memory()
        process = psutil.Process()
        proc_mem = process.memory_info().rss / (1024 * 1024)

        return web.json_response({
            "bot_name": str(self.bot.user) if self.bot.user else "Jey's Bot 💜",
            "guild_name": guild.name if guild else "Not Connected",
            "member_count": guild.member_count if guild else 0,
            "ping_ms": round(self.bot.latency * 1000, 1),
            "memory_mb": round(proc_mem, 1),
            "uptime_str": uptime_str
        })

    async def api_members(self, request: web.Request):
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return web.json_response([])
            
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
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return web.json_response([])
            
        import aiosqlite
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT * FROM mod_logs WHERE guild_id = ? ORDER BY id DESC LIMIT 50
            """, (str(guild.id),)) as cursor:
                rows = await cursor.fetchall()
                return web.json_response([dict(r) for r in rows])

    async def api_mod_action(self, request: web.Request):
        if not self.check_auth(request):
            return web.json_response({"success": False, "error": "Invalid or missing Admin PIN"}, status=401)
            
        data = await request.json()
        target_id = int(data.get("target_id", 0))
        action = data.get("action", "").upper()
        duration_str = data.get("duration", "10m")
        reason = data.get("reason", "Action taken via Web Dashboard")

        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return web.json_response({"success": False, "error": "Bot not connected to server."})

        target = guild.get_member(target_id)
        if not target:
            return web.json_response({"success": False, "error": "Member not found in server."})

        mod_cog = self.bot.get_cog("Moderation")

        try:
            case_id = None
            if action == "TIMEOUT":
                td = parse_duration(duration_str) or timedelta(minutes=10)
                await target.timeout(td, reason=f"[Web Dashboard] {reason}")
                dur_fmt = format_duration(td)
                case_id = await db.log_mod_action(str(guild.id), "TIMEOUT", str(target.id), str(target), "0", "Web Dashboard", reason, dur_fmt)
                if mod_cog:
                    await mod_cog.send_audit_log(guild, "⏳ Member Timed Out", 0xFEE75C, target, guild.me, reason, dur_fmt, case_id)

            elif action == "UNTIMEOUT":
                await target.timeout(None, reason="Timeout removed via Web Dashboard")
                case_id = await db.log_mod_action(str(guild.id), "UNTIMEOUT", str(target.id), str(target), "0", "Web Dashboard", reason)
                if mod_cog:
                    await mod_cog.send_audit_log(guild, "🔊 Timeout Removed", 0x57F287, target, guild.me, reason, None, case_id)

            elif action == "WARN":
                await db.add_warning(str(guild.id), str(target.id), "0", reason)
                case_id = await db.log_mod_action(str(guild.id), "WARN", str(target.id), str(target), "0", "Web Dashboard", reason)
                if mod_cog:
                    await mod_cog.send_audit_log(guild, "⚠️ Member Warned", 0xF1C40F, target, guild.me, reason, None, case_id)

            elif action == "KICK":
                await target.kick(reason=f"[Web Dashboard] {reason}")
                case_id = await db.log_mod_action(str(guild.id), "KICK", str(target.id), str(target), "0", "Web Dashboard", reason)
                if mod_cog:
                    await mod_cog.send_audit_log(guild, "👢 Member Kicked", 0xE67E22, target, guild.me, reason, None, case_id)

            elif action == "BAN":
                await target.ban(reason=f"[Web Dashboard] {reason}")
                case_id = await db.log_mod_action(str(guild.id), "BAN", str(target.id), str(target), "0", "Web Dashboard", reason)
                if mod_cog:
                    await mod_cog.send_audit_log(guild, "🔨 Member Banned", 0xED4245, target, guild.me, reason, None, case_id)

            return web.json_response({"success": True, "case_id": case_id})

        except discord.Forbidden:
            return web.json_response({"success": False, "error": "Bot role is lower than target role in Discord or lacks permissions."})
        except Exception as e:
            logger.error(f"Error executing web mod action: {e}", exc_info=True)
            return web.json_response({"success": False, "error": str(e)})

    async def api_get_welcome(self, request: web.Request):
        from cogs.welcome import build_welcome_embed
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return web.json_response({"content": "Guild not available"})
        embed = build_welcome_embed(guild)
        return web.json_response({"content": embed.description or ""})

    async def api_sync_welcome(self, request: web.Request):
        if not self.check_auth(request):
            return web.json_response({"success": False, "error": "Invalid PIN"}, status=401)
        welcome_cog = self.bot.get_cog("Welcome")
        if not welcome_cog:
            return web.json_response({"success": False, "error": "Welcome cog not loaded"})
        await welcome_cog.on_ready()
        return web.json_response({"success": True})

    async def api_get_rules(self, request: web.Request):
        from cogs.rules import build_rules_embed
        embed = build_rules_embed()
        return web.json_response({"content": embed.description or ""})

    async def api_sync_rules(self, request: web.Request):
        if not self.check_auth(request):
            return web.json_response({"success": False, "error": "Invalid PIN"}, status=401)
        rules_cog = self.bot.get_cog("Rules")
        if not rules_cog:
            return web.json_response({"success": False, "error": "Rules cog not loaded"})
        await rules_cog.on_ready()
        return web.json_response({"success": True})

async def setup(bot: commands.Bot):
    await bot.add_cog(DashboardCog(bot))
