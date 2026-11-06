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
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Jey's Bot Control Suite</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script>
    // Suppress benign CDN advisory notices in dev console
    const _origWarn = console.warn;
    console.warn = function(...args) {
      if (typeof args[0] === 'string' && (args[0].includes('cdn.tailwindcss.com') || args[0].includes('Babel transformer'))) return;
      _origWarn.apply(console, args);
    };
  </script>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: {
              50: '#f5f3ff',
              100: '#ede9fe',
              400: '#a78bfa',
              500: '#8b5cf6',
              600: '#7c3aed',
              700: '#6d28d9',
              900: '#4c1d95',
              glow: 'rgba(139, 92, 246, 0.25)'
            },
            surface: {
              DEFAULT: '#09090e',
              card: '#111119',
              cardHover: '#161622',
              border: '#1f1f2e',
              borderLight: '#2a2a3d',
              muted: '#8b8b9e'
            }
          },
          fontFamily: {
            sans: ['Inter', 'system-ui', 'sans-serif'],
            mono: ['JetBrains Mono', 'monospace']
          }
        }
      }
    };
  </script>
  <style>
    * { font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11'; }
    body { background-color: #09090e; color: #f3f3f7; }
    .glass-nav { background: rgba(15, 15, 23, 0.85); backdrop-filter: blur(16px); }
    .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: #262638; border-radius: 4px; }
    .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #373750; }
  </style>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body class="min-h-screen flex flex-col font-sans selection:bg-brand-600 selection:text-white">
  <div id="root"></div>

  <script type="text/babel">
    const { useState, useEffect, useMemo, useCallback } = React;
    const MISSJEY_AVATAR = "https://yt3.googleusercontent.com/O143rEtFVDnaNLx5zkY4QcYIXpKuUMIWkAN_m7ZJeuE5qCGhPMXJqWzHhiChGeJtWZq_lEFKkQ=s900-c-k-c0x00ffffff-no-rj";

    // --- Clean Vector Icons (No Emojis) ---
    const IconShield = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
    );
    const IconActivity = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
    );
    const IconUsers = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
    );
    const IconCpu = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>
    );
    const IconClock = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
    );
    const IconServer = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
    );
    const IconSliders = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
    );
    const IconFileText = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
    );
    const IconRefresh = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
    );
    const IconLogOut = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
    );
    const IconCheckCircle = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
    );
    const IconAlertTriangle = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
    );
    const IconChevronDown = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    );
    const IconLock = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
    );
    const IconKey = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2l-2 2m-1.5 1.5L16 7l-1.5-1.5L13 7l-1.5-1.5L10 7 8.5 5.5 7 7l-5.5 5.5a4 4 0 1 0 5.66 5.66L10 15.34l1.5 1.5L13 15.34l1.5 1.5L16 15.34l1.5 1.5L22 11.5 21 2z"/></svg>
    );
    const IconZap = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
    );
    const IconHash = ({ className = "w-4 h-4" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>
    );
    const IconDiscord = ({ className = "w-5 h-5" }) => (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.894.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
      </svg>
    );

    // --- Main Dashboard React Application ---
    function App() {
      const [auth, setAuth] = useState({ authenticated: false, loading: true, user: null, guilds: [] });
      const [selectedGuildId, setSelectedGuildId] = useState("");
      const [activeTab, setActiveTab] = useState("overview");
      const [stats, setStats] = useState(null);
      const [members, setMembers] = useState([]);
      const [modLogs, setModLogs] = useState([]);
      const [guildChannels, setGuildChannels] = useState({ channels: [], roles: [], settings: {} });
      const [welcomePreview, setWelcomePreview] = useState("");
      const [rulesPreview, setRulesPreview] = useState("");
      const [toasts, setToasts] = useState([]);
      const [pinInput, setPinInput] = useState("");
      const [isSubmitting, setIsSubmitting] = useState(false);

      // Moderation Form State
      const [modTarget, setModTarget] = useState("");
      const [modAction, setModAction] = useState("TIMEOUT");
      const [modDuration, setModDuration] = useState("10m");
      const [modReason, setModReason] = useState("");
      const [logFilter, setLogFilter] = useState("");

      const addToast = (type, message) => {
        const id = Date.now();
        setToasts(prev => [...prev, { id, type, message }]);
        setTimeout(() => {
          setToasts(prev => prev.filter(t => t.id !== id));
        }, 4000);
      };

      // Check current auth status
      const checkAuth = useCallback(async () => {
        try {
          const res = await fetch('/api/auth/me');
          const data = await res.json();
          if (data.authenticated) {
            setAuth({ authenticated: true, loading: false, user: data.user, guilds: data.guilds });
            const savedGid = localStorage.getItem('jeysbot_guild_id');
            const targetGid = (savedGid && data.guilds.find(g => g.id === savedGid)) ? savedGid : (data.guilds[0]?.id || "");
            setSelectedGuildId(targetGid);
          } else {
            setAuth({ authenticated: false, loading: false, user: null, guilds: [] });
          }
        } catch (e) {
          setAuth({ authenticated: false, loading: false, user: null, guilds: [] });
        }
      }, []);

      useEffect(() => {
        checkAuth();
      }, [checkAuth]);

      const selectedGuild = useMemo(() => {
        return auth.guilds.find(g => g.id === selectedGuildId) || null;
      }, [auth.guilds, selectedGuildId]);

      // Fetch Guild-Specific Data
      const fetchGuildData = useCallback(async (gid) => {
        if (!gid) return;
        try {
          // 1. Stats
          fetch(`/api/stats?guild_id=${gid}`).then(r => r.ok && r.json()).then(d => d && setStats(d));
          // 2. Members
          fetch(`/api/members?guild_id=${gid}`).then(r => r.ok && r.json()).then(d => d && setMembers(d));
          // 3. Mod Logs
          fetch(`/api/moderation/logs?guild_id=${gid}`).then(r => r.ok && r.json()).then(d => d && setModLogs(d));
          // 4. Channels & Settings
          fetch(`/api/guild/channels?guild_id=${gid}`).then(r => r.ok && r.json()).then(d => d && setGuildChannels(d));
          // 5. Previews
          fetch(`/api/embeds/welcome?guild_id=${gid}`).then(r => r.ok && r.json()).then(d => d && setWelcomePreview(d.content));
          fetch(`/api/embeds/rules?guild_id=${gid}`).then(r => r.ok && r.json()).then(d => d && setRulesPreview(d.content));
        } catch (err) {
          console.error("Error fetching data:", err);
        }
      }, []);

      useEffect(() => {
        if (selectedGuildId) {
          localStorage.setItem('jeysbot_guild_id', selectedGuildId);
          fetchGuildData(selectedGuildId);
        }
      }, [selectedGuildId, fetchGuildData]);

      // Auto-poll stats every 6s
      useEffect(() => {
        if (!selectedGuildId) return;
        const interval = setInterval(() => {
          fetch(`/api/stats?guild_id=${selectedGuildId}`).then(r => r.ok && r.json()).then(d => d && setStats(d));
        }, 6000);
        return () => clearInterval(interval);
      }, [selectedGuildId]);

      const handleServerSwitch = (e) => {
        setSelectedGuildId(e.target.value);
      };

      const handlePinLogin = async (e) => {
        e.preventDefault();
        if (!pinInput.trim()) return;
        try {
          const res = await fetch('/auth/pin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: pinInput })
          });
          const d = await res.json();
          if (d.success) {
            addToast('success', 'Master authorization verified');
            checkAuth();
          } else {
            addToast('error', 'Invalid security passcode');
          }
        } catch (err) {
          addToast('error', err.message);
        }
      };

      const handleLogout = async () => {
        await fetch('/auth/logout', { method: 'POST' });
        window.location.reload();
      };

      const executeModeration = async (e) => {
        e.preventDefault();
        if (!selectedGuildId || !modTarget) {
          addToast('error', 'Please select a target member');
          return;
        }
        setIsSubmitting(true);
        try {
          const res = await fetch('/api/moderation/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              guild_id: selectedGuildId,
              target_id: modTarget,
              action: modAction,
              duration: modDuration,
              reason: modReason || "Moderated via Web Dashboard"
            })
          });
          const data = await res.json();
          if (data.success) {
            addToast('success', `Executed ${modAction} (Case #${data.case_id})`);
            setModReason("");
            fetchGuildData(selectedGuildId);
          } else {
            addToast('error', data.error || 'Execution failed');
          }
        } catch (err) {
          addToast('error', err.message);
        } finally {
          setIsSubmitting(false);
        }
      };

      const handleSaveSettings = async (e) => {
        e.preventDefault();
        const form = e.target;
        const body = {
          guild_id: selectedGuildId,
          welcome_channel_id: form.welcome.value || null,
          rules_channel_id: form.rules.value || null,
          stream_channel_id: form.stream.value || null,
          video_channel_id: form.video.value || null,
          stream_ping_role_id: form.role.value || null
        };
        try {
          const res = await fetch('/api/guild/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
          });
          const data = await res.json();
          if (data.success) {
            addToast('success', 'Server channel configuration updated');
            fetchGuildData(selectedGuildId);
          } else {
            addToast('error', data.error || 'Failed to update settings');
          }
        } catch (err) {
          addToast('error', err.message);
        }
      };

      const handleSyncEmbed = async (type) => {
        try {
          const res = await fetch(`/api/embeds/${type}/sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ guild_id: selectedGuildId })
          });
          const data = await res.json();
          if (data.success) {
            addToast('success', `${type.toUpperCase()} embed published to channel`);
            fetchGuildData(selectedGuildId);
          } else {
            addToast('error', data.error || 'Sync failed');
          }
        } catch (err) {
          addToast('error', err.message);
        }
      };

      const filteredLogs = useMemo(() => {
        if (!logFilter.trim()) return modLogs;
        const q = logFilter.toLowerCase();
        return modLogs.filter(l => 
          l.target_name.toLowerCase().includes(q) ||
          l.moderator_name.toLowerCase().includes(q) ||
          l.action.toLowerCase().includes(q) ||
          l.reason.toLowerCase().includes(q)
        );
      }, [modLogs, logFilter]);

      if (auth.loading) {
        return (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex items-center gap-3 text-surface-muted text-sm font-mono tracking-wider">
              <span className="w-2 h-2 rounded-full bg-brand-500 animate-ping"></span>
              INITIALIZING CONTROL CENTER...
            </div>
          </div>
        );
      }

      return (
        <div className="flex-1 flex flex-col">
          {/* Top Sticky Header */}
          <header className="sticky top-0 z-40 border-b border-surface-border glass-nav px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-3">
                <img src={MISSJEY_AVATAR} alt="Bot Icon" className="w-9 h-9 rounded-full ring-2 ring-brand-500/40 object-cover shadow-lg shadow-brand-glow" />
                <div>
                  <h1 className="text-sm font-bold tracking-tight text-white flex items-center gap-2">
                    Jey Control Suite
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                      24/7 VPS
                    </span>
                  </h1>
                  <span className="text-xs text-surface-muted font-medium">Enterprise Discord Operations</span>
                </div>
              </div>

              {/* Server Switcher Pill */}
              {auth.authenticated && auth.guilds.length > 0 && (
                <div className="relative flex items-center bg-surface-card border border-surface-border hover:border-surface-borderLight rounded-xl px-3 py-1.5 transition-colors">
                  <IconServer className="w-3.5 h-3.5 text-brand-400 mr-2" />
                  <select 
                    value={selectedGuildId} 
                    onChange={handleServerSwitch}
                    className="bg-transparent text-xs font-semibold text-white outline-none cursor-pointer pr-6 appearance-none"
                  >
                    {auth.guilds.map(g => (
                      <option key={g.id} value={g.id} className="bg-surface-card text-white">
                        {g.name} {g.is_owner ? '(Owner)' : ''}
                      </option>
                    ))}
                  </select>
                  <IconChevronDown className="w-3.5 h-3.5 text-surface-muted absolute right-2.5 pointer-events-none" />
                </div>
              )}
            </div>

            {/* Navigation Tabs */}
            {auth.authenticated && (
              <nav className="flex items-center gap-1.5 bg-surface-card/60 p-1 rounded-xl border border-surface-border">
                <button 
                  onClick={() => setActiveTab("overview")} 
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeTab === "overview" ? "bg-brand-600 text-white shadow-md shadow-brand-glow" : "text-surface-muted hover:text-white hover:bg-surface-cardHover"}`}
                >
                  <IconActivity className="w-3.5 h-3.5" />
                  Overview
                </button>
                <button 
                  onClick={() => setActiveTab("moderation")} 
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeTab === "moderation" ? "bg-brand-600 text-white shadow-md shadow-brand-glow" : "text-surface-muted hover:text-white hover:bg-surface-cardHover"}`}
                >
                  <IconShield className="w-3.5 h-3.5" />
                  Moderation
                </button>
                <button 
                  onClick={() => setActiveTab("settings")} 
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeTab === "settings" ? "bg-brand-600 text-white shadow-md shadow-brand-glow" : "text-surface-muted hover:text-white hover:bg-surface-cardHover"}`}
                >
                  <IconSliders className="w-3.5 h-3.5" />
                  Channels
                </button>
                <button 
                  onClick={() => setActiveTab("embeds")} 
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeTab === "embeds" ? "bg-brand-600 text-white shadow-md shadow-brand-glow" : "text-surface-muted hover:text-white hover:bg-surface-cardHover"}`}
                >
                  <IconFileText className="w-3.5 h-3.5" />
                  Embeds
                </button>
              </nav>
            )}

            {/* Right Header: User Profile or Login */}
            <div className="flex items-center gap-3">
              {auth.authenticated ? (
                <div className="flex items-center gap-2 bg-surface-card border border-surface-border rounded-xl px-2.5 py-1">
                  <img src={auth.user.avatar} alt="User Avatar" className="w-6 h-6 rounded-full" />
                  <span className="text-xs font-semibold text-white">{auth.user.name}</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-400">Admin</span>
                  <button 
                    onClick={handleLogout} 
                    title="Sign out"
                    className="ml-2 text-surface-muted hover:text-rose-400 transition-colors p-1"
                  >
                    <IconLogOut className="w-3.5 h-3.5" />
                  </button>
                </div>
              ) : (
                <button 
                  onClick={() => {}} 
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 text-white hover:bg-brand-500 transition-all shadow-md shadow-brand-glow"
                >
                  Sign In
                </button>
              )}
            </div>
          </header>

          {/* Main Content Area */}
          <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
            {auth.authenticated ? (
              <>
                {/* 1. OVERVIEW TAB */}
                {activeTab === "overview" && (
                  <div className="space-y-6">
                    {/* Top Stat Metric Cards */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                      {/* Members */}
                      <div className="bg-surface-card border border-surface-border hover:border-brand-500/30 rounded-2xl p-5 transition-all">
                        <div className="flex items-center justify-between text-surface-muted mb-3">
                          <span className="text-xs font-semibold uppercase tracking-wider">Server Members</span>
                          <div className="p-2 rounded-lg bg-surface-cardHover border border-surface-border">
                            <IconUsers className="w-4 h-4 text-brand-400" />
                          </div>
                        </div>
                        <div className="text-2xl font-bold font-mono text-white tracking-tight">
                          {stats?.member_count ?? "—"}
                        </div>
                        <div className="text-[11px] text-surface-muted mt-2 truncate">
                          {selectedGuild?.name || "Active Server"}
                        </div>
                      </div>

                      {/* Latency */}
                      <div className="bg-surface-card border border-surface-border hover:border-brand-500/30 rounded-2xl p-5 transition-all">
                        <div className="flex items-center justify-between text-surface-muted mb-3">
                          <span className="text-xs font-semibold uppercase tracking-wider">Gateway Latency</span>
                          <div className="p-2 rounded-lg bg-surface-cardHover border border-surface-border">
                            <IconZap className="w-4 h-4 text-emerald-400" />
                          </div>
                        </div>
                        <div className="text-2xl font-bold font-mono text-white tracking-tight flex items-baseline gap-1.5">
                          {stats?.ping_ms ?? "—"}
                          <span className="text-xs font-normal text-surface-muted font-sans">ms</span>
                        </div>
                        <div className="text-[11px] text-emerald-400/90 mt-2 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                          Optimal WebSocket connection
                        </div>
                      </div>

                      {/* Memory */}
                      <div className="bg-surface-card border border-surface-border hover:border-brand-500/30 rounded-2xl p-5 transition-all">
                        <div className="flex items-center justify-between text-surface-muted mb-3">
                          <span className="text-xs font-semibold uppercase tracking-wider">VPS Memory</span>
                          <div className="p-2 rounded-lg bg-surface-cardHover border border-surface-border">
                            <IconCpu className="w-4 h-4 text-brand-400" />
                          </div>
                        </div>
                        <div className="text-2xl font-bold font-mono text-white tracking-tight flex items-baseline gap-1.5">
                          {stats?.memory_mb ?? "—"}
                          <span className="text-xs font-normal text-surface-muted font-sans">MB</span>
                        </div>
                        <div className="text-[11px] text-surface-muted mt-2">
                          Ubuntu 24.04 LTS (NVMe High-Speed)
                        </div>
                      </div>

                      {/* Uptime */}
                      <div className="bg-surface-card border border-surface-border hover:border-brand-500/30 rounded-2xl p-5 transition-all">
                        <div className="flex items-center justify-between text-surface-muted mb-3">
                          <span className="text-xs font-semibold uppercase tracking-wider">Instance Uptime</span>
                          <div className="p-2 rounded-lg bg-surface-cardHover border border-surface-border">
                            <IconClock className="w-4 h-4 text-amber-400" />
                          </div>
                        </div>
                        <div className="text-2xl font-bold font-mono text-white tracking-tight">
                          {stats?.uptime_str ?? "—"}
                        </div>
                        <div className="text-[11px] text-surface-muted mt-2">
                          Persistent systemd automation
                        </div>
                      </div>
                    </div>

                    {/* Server Context Banner */}
                    <div className="bg-surface-card border border-surface-border rounded-2xl p-6">
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-surface-border">
                        <div>
                          <span className="text-xs font-mono text-brand-400 tracking-wider uppercase font-semibold">Protected Environment</span>
                          <h2 className="text-xl font-bold text-white mt-1">{selectedGuild?.name || "Server Operations"}</h2>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20">
                            <IconShield className="w-3.5 h-3.5" />
                            Strict Per-Guild Isolation
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-surface-muted mt-4 leading-relaxed max-w-3xl">
                        This session is authenticated with direct Discord Administrator permissions for this server. 
                        All moderation operations, warning databases, and channel routing are compartmentalized. Actions performed here 
                        will execute immediately on Discord without latency.
                      </p>
                    </div>
                  </div>
                )}

                {/* 2. MODERATION TAB */}
                {activeTab === "moderation" && (
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                    {/* Left: Execution Form (5 cols) */}
                    <div className="lg:col-span-5 bg-surface-card border border-surface-border rounded-2xl p-6">
                      <div className="flex items-center gap-2 mb-5 pb-3 border-b border-surface-border">
                        <IconShield className="w-4 h-4 text-brand-400" />
                        <h2 className="text-sm font-bold uppercase tracking-wider text-white">Execute Moderation</h2>
                      </div>

                      <form onSubmit={executeModeration} className="space-y-4">
                        <div>
                          <label className="block text-xs font-semibold text-surface-muted mb-2">Target Member</label>
                          <select 
                            value={modTarget} 
                            onChange={e => setModTarget(e.target.value)}
                            required
                            className="w-full bg-surface-cardHover border border-surface-border focus:border-brand-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none transition-colors"
                          >
                            <option value="" disabled>Select target server member...</option>
                            {members.map(m => (
                              <option key={m.id} value={m.id}>{m.name} (@{m.tag})</option>
                            ))}
                          </select>
                        </div>

                        <div>
                          <label className="block text-xs font-semibold text-surface-muted mb-2">Disciplinary Action</label>
                          <div className="grid grid-cols-2 gap-2">
                            {[
                              { id: "TIMEOUT", label: "Timeout (Mute)" },
                              { id: "REMOVE_TIMEOUT", label: "Remove Timeout" },
                              { id: "WARN", label: "Issue Warning" },
                              { id: "KICK", label: "Kick Member" },
                              { id: "BAN", label: "Ban Member" },
                            ].map(act => (
                              <button
                                key={act.id}
                                type="button"
                                onClick={() => setModAction(act.id)}
                                className={`text-xs font-medium py-2 px-3 rounded-lg border text-left transition-all ${modAction === act.id ? "bg-brand-600/20 border-brand-500 text-brand-300" : "bg-surface-cardHover border-surface-border text-surface-muted hover:border-surface-borderLight hover:text-white"}`}
                              >
                                {act.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        {modAction === "TIMEOUT" && (
                          <div>
                            <label className="block text-xs font-semibold text-surface-muted mb-2">Timeout Duration</label>
                            <select 
                              value={modDuration} 
                              onChange={e => setModDuration(e.target.value)}
                              className="w-full bg-surface-cardHover border border-surface-border focus:border-brand-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none transition-colors"
                            >
                              <option value="5m">5 Minutes</option>
                              <option value="10m">10 Minutes</option>
                              <option value="1h">1 Hour</option>
                              <option value="1d">1 Day (24 Hours)</option>
                              <option value="1w">1 Week (7 Days)</option>
                            </select>
                          </div>
                        )}

                        <div>
                          <label className="block text-xs font-semibold text-surface-muted mb-2">Audit Reason</label>
                          <input 
                            type="text" 
                            placeholder="E.g. Inappropriate behavior, spam in voice/text"
                            value={modReason} 
                            onChange={e => setModReason(e.target.value)}
                            required
                            className="w-full bg-surface-cardHover border border-surface-border focus:border-brand-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none transition-colors"
                          />
                        </div>

                        <button 
                          type="submit" 
                          disabled={isSubmitting}
                          className="w-full mt-2 py-3 px-4 rounded-xl font-semibold text-xs tracking-wider uppercase bg-brand-600 hover:bg-brand-500 text-white transition-all shadow-lg shadow-brand-glow flex items-center justify-center gap-2 disabled:opacity-50"
                        >
                          <IconCheckCircle className="w-4 h-4" />
                          {isSubmitting ? "Processing..." : `Dispatch ${modAction}`}
                        </button>
                      </form>
                    </div>

                    {/* Right: Audit Log Table (7 cols) */}
                    <div className="lg:col-span-7 bg-surface-card border border-surface-border rounded-2xl p-6 flex flex-col">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-3 border-b border-surface-border">
                        <div className="flex items-center gap-2">
                          <IconFileText className="w-4 h-4 text-brand-400" />
                          <h2 className="text-sm font-bold uppercase tracking-wider text-white">Guild Audit Log</h2>
                        </div>
                        <div className="flex items-center gap-2">
                          <input 
                            type="text"
                            placeholder="Search logs..."
                            value={logFilter}
                            onChange={e => setLogFilter(e.target.value)}
                            className="bg-surface-cardHover border border-surface-border rounded-lg px-2.5 py-1 text-xs text-white placeholder-surface-muted outline-none w-36 focus:w-48 transition-all"
                          />
                          <button 
                            onClick={() => fetchGuildData(selectedGuildId)}
                            title="Refresh Audit Logs"
                            className="p-1.5 rounded-lg bg-surface-cardHover border border-surface-border text-surface-muted hover:text-white transition-colors"
                          >
                            <IconRefresh className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="flex-1 overflow-x-auto custom-scrollbar max-h-[500px]">
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="border-b border-surface-border text-surface-muted uppercase font-mono tracking-wider">
                              <th className="py-2.5 px-3">Case</th>
                              <th className="py-2.5 px-3">Action</th>
                              <th className="py-2.5 px-3">Target</th>
                              <th className="py-2.5 px-3">Moderator</th>
                              <th className="py-2.5 px-3">Reason</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-surface-border/50">
                            {filteredLogs.length === 0 ? (
                              <tr>
                                <td colSpan="5" className="py-12 text-center text-surface-muted">
                                  No moderation logs recorded for this server yet.
                                </td>
                              </tr>
                            ) : (
                              filteredLogs.map(l => {
                                const badgeColors = {
                                  TIMEOUT: "bg-amber-500/10 text-amber-400 border-amber-500/20",
                                  REMOVE_TIMEOUT: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
                                  WARN: "bg-brand-500/10 text-brand-400 border-brand-500/20",
                                  KICK: "bg-orange-500/10 text-orange-400 border-orange-500/20",
                                  BAN: "bg-rose-500/10 text-rose-400 border-rose-500/20",
                                }[l.action] || "bg-surface-cardHover text-surface-muted border-surface-border";

                                return (
                                  <tr key={l.id} className="hover:bg-surface-cardHover/50 transition-colors">
                                    <td className="py-3 px-3 font-mono text-surface-muted">#{l.id}</td>
                                    <td className="py-3 px-3">
                                      <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold border ${badgeColors}`}>
                                        {l.action}
                                      </span>
                                    </td>
                                    <td className="py-3 px-3 font-medium text-white">{l.target_name}</td>
                                    <td className="py-3 px-3 text-surface-muted">{l.moderator_name}</td>
                                    <td className="py-3 px-3 text-surface-muted max-w-[180px] truncate" title={l.reason}>
                                      {l.reason} {l.duration ? `(${l.duration})` : ''}
                                    </td>
                                  </tr>
                                );
                              })
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}

                {/* 3. SETTINGS & CHANNELS TAB */}
                {activeTab === "settings" && (
                  <div className="max-w-2xl mx-auto bg-surface-card border border-surface-border rounded-2xl p-7">
                    <div className="flex items-center gap-2 mb-2 pb-3 border-b border-surface-border">
                      <IconSliders className="w-4 h-4 text-brand-400" />
                      <h2 className="text-sm font-bold uppercase tracking-wider text-white">Channel Routing & Roles</h2>
                    </div>
                    <p className="text-xs text-surface-muted mb-6 leading-relaxed">
                      Select which text channels on <strong className="text-white">{selectedGuild?.name}</strong> receive YouTube notifications, onboarding guides, and server rules.
                    </p>

                    <form onSubmit={handleSaveSettings} className="space-y-4">
                      <div>
                        <label className="block text-xs font-semibold text-surface-muted mb-2">Welcome & Guide Channel</label>
                        <select 
                          name="welcome" 
                          defaultValue={guildChannels.settings.welcome_channel_id || ""}
                          className="w-full bg-surface-cardHover border border-surface-border focus:border-brand-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
                        >
                          <option value="">(None / Auto-detect #welcome)</option>
                          {guildChannels.channels.map(c => (
                            <option key={c.id} value={c.id}>#{c.name}</option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-surface-muted mb-2">Rules & Guidelines Channel</label>
                        <select 
                          name="rules" 
                          defaultValue={guildChannels.settings.rules_channel_id || ""}
                          className="w-full bg-surface-cardHover border border-surface-border focus:border-brand-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
                        >
                          <option value="">(None / Auto-detect #rules)</option>
                          {guildChannels.channels.map(c => (
                            <option key={c.id} value={c.id}>#{c.name}</option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-surface-muted mb-2">YouTube Live Stream Channel</label>
                        <select 
                          name="stream" 
                          defaultValue={guildChannels.settings.stream_channel_id || ""}
                          className="w-full bg-surface-cardHover border border-surface-border focus:border-brand-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
                        >
                          <option value="">(None / Auto-detect #live-streams)</option>
                          {guildChannels.channels.map(c => (
                            <option key={c.id} value={c.id}>#{c.name}</option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-surface-muted mb-2">YouTube Videos & Shorts Channel</label>
                        <select 
                          name="video" 
                          defaultValue={guildChannels.settings.video_channel_id || ""}
                          className="w-full bg-surface-cardHover border border-surface-border focus:border-brand-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
                        >
                          <option value="">(None / Auto-detect #videos)</option>
                          {guildChannels.channels.map(c => (
                            <option key={c.id} value={c.id}>#{c.name}</option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-surface-muted mb-2">Live Stream Ping Role</label>
                        <select 
                          name="role" 
                          defaultValue={guildChannels.settings.stream_ping_role_id || ""}
                          className="w-full bg-surface-cardHover border border-surface-border focus:border-brand-500 rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
                        >
                          <option value="">(None / Auto-detect @Stream Alert)</option>
                          {guildChannels.roles.map(r => (
                            <option key={r.id} value={r.id}>@{r.name}</option>
                          ))}
                        </select>
                      </div>

                      <button 
                        type="submit" 
                        className="w-full mt-4 py-3 px-4 rounded-xl font-semibold text-xs tracking-wider uppercase bg-brand-600 hover:bg-brand-500 text-white transition-all shadow-lg shadow-brand-glow flex items-center justify-center gap-2"
                      >
                        <IconCheckCircle className="w-4 h-4" />
                        Save Server Configuration
                      </button>
                    </form>
                  </div>
                )}

                {/* 4. EMBEDS TAB */}
                {activeTab === "embeds" && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Welcome Embed Card */}
                    <div className="bg-surface-card border border-surface-border rounded-2xl p-6 flex flex-col">
                      <div className="flex items-center justify-between pb-4 border-b border-surface-border mb-4">
                        <div className="flex items-center gap-2">
                          <IconFileText className="w-4 h-4 text-brand-400" />
                          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Welcome Guide Embed</h3>
                        </div>
                        <button 
                          onClick={() => handleSyncEmbed("welcome")}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 hover:bg-brand-500 text-white transition-all shadow-sm flex items-center gap-1.5"
                        >
                          <IconRefresh className="w-3.5 h-3.5" />
                          Sync to Discord
                        </button>
                      </div>
                      <pre className="flex-1 bg-surface-cardHover border border-surface-border/60 rounded-xl p-4 text-xs font-mono text-surface-muted overflow-y-auto max-h-[420px] custom-scrollbar whitespace-pre-wrap">
                        {welcomePreview || "No welcome embed generated."}
                      </pre>
                    </div>

                    {/* Rules Embed Card */}
                    <div className="bg-surface-card border border-surface-border rounded-2xl p-6 flex flex-col">
                      <div className="flex items-center justify-between pb-4 border-b border-surface-border mb-4">
                        <div className="flex items-center gap-2">
                          <IconShield className="w-4 h-4 text-brand-400" />
                          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Server Rules Embed</h3>
                        </div>
                        <button 
                          onClick={() => handleSyncEmbed("rules")}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 hover:bg-brand-500 text-white transition-all shadow-sm flex items-center gap-1.5"
                        >
                          <IconRefresh className="w-3.5 h-3.5" />
                          Sync to Discord
                        </button>
                      </div>
                      <pre className="flex-1 bg-surface-cardHover border border-surface-border/60 rounded-xl p-4 text-xs font-mono text-surface-muted overflow-y-auto max-h-[420px] custom-scrollbar whitespace-pre-wrap">
                        {rulesPreview || "No rules embed generated."}
                      </pre>
                    </div>
                  </div>
                )}
              </>
            ) : null}
          </main>

          {/* Authentication Modal (Shown when unauthenticated) */}
          {!auth.authenticated && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
              <div className="bg-surface-card border border-surface-border rounded-3xl p-8 max-w-md w-full text-center shadow-2xl shadow-black relative overflow-hidden">
                <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-surface-cardHover border border-surface-border flex items-center justify-center">
                  <IconShield className="w-8 h-8 text-brand-400" />
                </div>
                
                <h2 className="text-xl font-bold text-white mb-2 tracking-tight">Enterprise Access Verification</h2>
                <p className="text-xs text-surface-muted leading-relaxed mb-6">
                  Sign in with your verified Discord account to manage your servers with role-based access control.
                </p>

                {/* 1-Click Discord OAuth2 */}
                <a 
                  href="/auth/discord" 
                  className="w-full py-3 px-4 rounded-xl font-semibold text-xs tracking-wider uppercase bg-[#5865F2] hover:bg-[#4752c4] text-white transition-all shadow-lg flex items-center justify-center gap-2.5"
                >
                  <IconDiscord className="w-4 h-4" />
                  Continue with Discord
                </a>

                {/* Divider */}
                <div className="flex items-center my-6 gap-3 text-[11px] text-surface-muted font-mono uppercase tracking-wider">
                  <div className="flex-1 h-px bg-surface-border"></div>
                  <span>Or Master Key</span>
                  <div className="flex-1 h-px bg-surface-border"></div>
                </div>

                {/* Master PIN Fallback */}
                <form onSubmit={handlePinLogin} className="space-y-3">
                  <div className="relative">
                    <IconKey className="w-4 h-4 text-surface-muted absolute left-3.5 top-3.5 pointer-events-none" />
                    <input 
                      type="password"
                      placeholder="Enter Master Security Key"
                      value={pinInput}
                      onChange={e => setPinInput(e.target.value)}
                      className="w-full bg-surface-cardHover border border-surface-border focus:border-brand-500 rounded-xl pl-10 pr-3.5 py-2.5 text-xs text-white placeholder-surface-muted outline-none transition-colors"
                    />
                  </div>
                  <button 
                    type="submit" 
                    className="w-full py-2.5 px-4 rounded-xl font-semibold text-xs tracking-wider uppercase bg-surface-cardHover border border-surface-border hover:border-surface-borderLight text-white transition-all"
                  >
                    Authenticate with Key
                  </button>
                </form>
              </div>
            </div>
          )}

          {/* Floating Toast Notification Stack */}
          <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none">
            {toasts.map(t => (
              <div 
                key={t.id} 
                className={`pointer-events-auto px-4 py-3 rounded-xl border text-xs font-semibold shadow-xl flex items-center gap-2.5 animate-slideUp ${
                  t.type === 'success' ? 'bg-surface-card border-emerald-500/30 text-emerald-400' :
                  t.type === 'error' ? 'bg-surface-card border-rose-500/30 text-rose-400' :
                  'bg-surface-card border-surface-border text-white'
                }`}
              >
                {t.type === 'success' ? <IconCheckCircle className="w-4 h-4 text-emerald-400" /> : <IconAlertTriangle className="w-4 h-4 text-rose-400" />}
                {t.message}
              </div>
            ))}
          </div>
        </div>
      );
    }

    ReactDOM.createRoot(document.getElementById('root')).render(<App />);
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
            logger.info(f"🌐 React Dashboard Web Server active on http://0.0.0.0:{DASHBOARD_PORT}")
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
            async with session.post("https://discord.com/api/oauth2/token", data=data) as resp:
                token_data = await resp.json()

            access_token = token_data.get("access_token")
            if not access_token:
                logger.error(f"Failed to get OAuth token: {token_data}")
                return web.HTTPBadRequest(text=f"Failed to authenticate with Discord: {token_data.get('error_description', 'Invalid token')}")

            headers = {"Authorization": f"Bearer {access_token}"}

            async with session.get("https://discord.com/api/users/@me", headers=headers) as resp:
                user_data = await resp.json()

            async with session.get("https://discord.com/api/users/@me/guilds", headers=headers) as resp:
                user_guilds = await resp.json()

        allowed_guild_ids = set()
        user_managed_guilds = []

        for g in user_guilds:
            gid = str(g.get("id"))
            perms = int(g.get("permissions", "0"))
            is_owner = g.get("owner", False)
            is_admin = is_owner or bool(perms & 0x8) or bool(perms & 0x20)

            bot_guild = self.bot.get_guild(int(gid))
            if is_admin and bot_guild:
                allowed_guild_ids.add(gid)
                user_managed_guilds.append({
                    "id": gid,
                    "name": bot_guild.name,
                    "is_owner": is_owner
                })

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
            "expires": time.time() + (86400 * 7)
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
                    "name": "System Administrator",
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
        reason = data.get("reason", "Moderated via Web Dashboard")

        target = guild.get_member(target_id)
        if not target and action not in ["BAN"]:
            return web.json_response({"success": False, "error": "Target member not found in this server."})

        mod_name = sess["user"]["name"]
        mod_id = sess["user"]["id"]
        mod_cog = self.bot.get_cog("ModerationCog")
        fake_mod = guild.get_member(int(mod_id)) if mod_id.isdigit() else self.bot.user

        try:
            if action == "TIMEOUT":
                duration = parse_duration(duration_str)
                # DM Target
                if mod_cog and target:
                    await mod_cog.send_user_dm(
                        target,
                        action_name="Timed Out",
                        color=0xFEE75C,
                        reason=reason,
                        extra_field=("Duration", duration_str)
                    )
                await target.timeout(duration, reason=f"[{mod_name}] {reason}")
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
                if mod_cog:
                    await mod_cog.send_audit_log(
                        guild=guild,
                        action_name="Timeout Applied",
                        color=0xFEE75C,
                        target=target,
                        moderator=fake_mod or self.bot.user,
                        reason=reason,
                        duration=duration_str,
                        case_id=case_id
                    )
                return web.json_response({"success": True, "case_id": case_id})

            elif action == "REMOVE_TIMEOUT":
                await target.timeout(None, reason=f"[{mod_name}] {reason}")
                case_id = await db.log_mod_action(
                    guild_id=str(guild.id),
                    action="REMOVE_TIMEOUT",
                    target_id=str(target.id),
                    target_name=str(target),
                    moderator_id=mod_id,
                    moderator_name=mod_name,
                    reason=reason
                )
                if mod_cog:
                    await mod_cog.send_audit_log(
                        guild=guild,
                        action_name="Timeout Removed",
                        color=0x57F287,
                        target=target,
                        moderator=fake_mod or self.bot.user,
                        reason=reason,
                        case_id=case_id
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
                
                dm_sent = False
                if mod_cog and target:
                    dm_sent = await mod_cog.send_user_dm(
                        target,
                        action_name="Warned",
                        color=0xF1C40F,
                        reason=reason
                    )
                    await mod_cog.send_audit_log(
                        guild=guild,
                        action_name="Member Warned",
                        color=0xF1C40F,
                        target=target,
                        moderator=fake_mod or self.bot.user,
                        reason=reason,
                        case_id=case_id
                    )
                return web.json_response({"success": True, "case_id": case_id, "dm_sent": dm_sent})

            elif action == "KICK":
                if mod_cog and target:
                    await mod_cog.send_user_dm(
                        target,
                        action_name="Kicked",
                        color=0xE67E22,
                        reason=reason
                    )
                await target.kick(reason=f"[{mod_name}] {reason}")
                case_id = await db.log_mod_action(
                    guild_id=str(guild.id),
                    action="KICK",
                    target_id=str(target.id),
                    target_name=str(target),
                    moderator_id=mod_id,
                    moderator_name=mod_name,
                    reason=reason
                )
                if mod_cog:
                    await mod_cog.send_audit_log(
                        guild=guild,
                        action_name="Member Kicked",
                        color=0xE67E22,
                        target=target,
                        moderator=fake_mod or self.bot.user,
                        reason=reason,
                        case_id=case_id
                    )
                return web.json_response({"success": True, "case_id": case_id})

            elif action == "BAN":
                if mod_cog and target:
                    await mod_cog.send_user_dm(
                        target,
                        action_name="Banned",
                        color=0xED4245,
                        reason=reason
                    )
                await guild.ban(discord.Object(id=target_id), reason=f"[{mod_name}] {reason}")
                case_id = await db.log_mod_action(
                    guild_id=str(guild.id),
                    action="BAN",
                    target_id=str(target_id),
                    target_name=str(target) if target else f"User ID {target_id}",
                    moderator_id=mod_id,
                    moderator_name=mod_name,
                    reason=reason
                )
                if mod_cog:
                    await mod_cog.send_audit_log(
                        guild=guild,
                        action_name="Member Banned",
                        color=0xED4245,
                        target=target or discord.Object(id=target_id),
                        moderator=fake_mod or self.bot.user,
                        reason=reason,
                        case_id=case_id
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
