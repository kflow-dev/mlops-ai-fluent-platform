"""Small memory explorer web surface for AIFluent."""

from __future__ import annotations

import json
import time
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from aifluent.memory.config import get_default_memory_config
from aifluent.memory.store import Event, Store

router = APIRouter(prefix="/memory", tags=["memory"])

_store: Store | None = None


class MemoryEventCreate(BaseModel):
    kind: str
    data: dict
    blob: str = ""
    timestamp: Optional[float] = None


def get_store() -> Store:
    global _store
    if _store is None:
        cfg = get_default_memory_config()
        _store = Store(cfg.db_path)
    return _store


def serialize_event(event: Event) -> dict:
    return {
        "id": event.id,
        "timestamp": event.timestamp,
        "kind": event.kind,
        "data": event.data,
        "blob": event.blob,
    }


@router.get("", response_class=HTMLResponse)
def memory_home() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AIFluent Memory</title>
  <style>
    :root { color-scheme: light; --bg:#f4efe8; --fg:#1f2937; --muted:#6b7280; --card:#fffaf3; --line:#e5d5c0; --accent:#9a3412; --accent-soft:#fff1e7; }
    body { margin:0; font-family: Georgia, serif; background: radial-gradient(circle at top, #fff7ed, var(--bg)); color:var(--fg); }
    main { max-width: 980px; margin: 0 auto; padding: 40px 20px 80px; }
    h1 { margin:0 0 8px; font-size: 42px; }
    p { color: var(--muted); font-family: ui-monospace, Menlo, monospace; }
    .hero { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
    .row { display:flex; gap:12px; flex-wrap:wrap; margin: 24px 0; }
    input, button { border:1px solid var(--line); border-radius:12px; padding:12px 14px; font-size:14px; }
    input { flex:1 1 320px; background:#fff; }
    button { background:var(--accent); color:#fff; cursor:pointer; }
    button.secondary { background:var(--accent-soft); color:var(--accent); }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:12px; margin: 24px 0; }
    .card, .event { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:16px; box-shadow:0 10px 30px rgba(0,0,0,.04); }
    .event { margin-top: 12px; }
    .kind { display:inline-block; font-size:12px; font-family: ui-monospace, Menlo, monospace; color:var(--accent); margin-bottom:8px; }
    pre { white-space: pre-wrap; word-break: break-word; margin:0; font-family: ui-monospace, Menlo, monospace; font-size:12px; }
    .status { margin: 10px 0 0; min-height: 20px; color: var(--muted); font-family: ui-monospace, Menlo, monospace; font-size: 12px; }
    .drawer { position: fixed; top: 0; right: 0; width: min(720px, 100vw); height: 100vh; background: #fffaf3; border-left: 1px solid var(--line); box-shadow: -12px 0 40px rgba(0,0,0,.08); transform: translateX(100%); transition: transform .2s ease; z-index: 20; display:flex; flex-direction:column; }
    .drawer.open { transform: translateX(0); }
    .drawer-header { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:20px; border-bottom:1px solid var(--line); }
    .drawer-body { padding:20px; display:flex; flex-direction:column; gap:12px; overflow:auto; }
    textarea { width:100%; min-height:420px; resize:vertical; border:1px solid var(--line); border-radius:16px; padding:14px; font-family: ui-monospace, Menlo, monospace; font-size:12px; line-height:1.5; background:#fff; }
    .meta { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:14px; font-family: ui-monospace, Menlo, monospace; font-size:12px; }
    .actions { display:flex; gap:10px; flex-wrap:wrap; }
    .field { display:flex; flex-direction:column; gap:6px; }
    .field label { font-size:12px; font-family: ui-monospace, Menlo, monospace; color:var(--muted); }
    .chat-shell { margin-top:24px; background:var(--card); border:1px solid var(--line); border-radius:20px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,.04); }
    .chat-header { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:16px 18px; border-bottom:1px solid var(--line); }
    .chat-tools { display:flex; gap:8px; flex-wrap:wrap; }
    .chat-sessions { display:flex; flex-wrap:wrap; gap:8px; padding:12px 16px; border-bottom:1px solid var(--line); background:#fff8f1; }
    .chat-session-item { display:flex; align-items:center; gap:6px; background:#fff; border:1px solid var(--line); border-radius:999px; padding:6px 8px 6px 12px; font-family: ui-monospace, Menlo, monospace; font-size:12px; }
    .chat-session-item button { padding:6px 8px; border-radius:999px; font-size:11px; }
    .chat-session-meta { color:var(--muted); }
    .chat-log { max-height: 360px; overflow:auto; padding:16px; display:flex; flex-direction:column; gap:12px; background:#fffdf9; }
    .bubble { max-width:85%; padding:12px 14px; border-radius:16px; font-size:14px; line-height:1.5; white-space:pre-wrap; }
    .bubble.user { align-self:flex-end; background:#9a3412; color:#fff; border-bottom-right-radius:6px; }
    .bubble.assistant { align-self:flex-start; background:#fff1e7; color:#431407; border-bottom-left-radius:6px; }
    .chat-input { padding:16px; display:flex; gap:10px; border-top:1px solid var(--line); background:#fffaf3; }
    .chat-input textarea { min-height:72px; margin:0; flex:1; }
  </style>
</head>
<body>
  <main>
    <div class="hero">
      <div>
        <h1>AIFluent Memory</h1>
        <p>Search and inspect persisted events migrated from CatchMe-style storage.</p>
      </div>
      <button class="secondary" onclick="openSettings()">Settings</button>
    </div>
    <div class="row">
      <input id="query" placeholder="Search events, notes, prompts, actions">
      <button onclick="loadSearch()">Search</button>
      <button onclick="loadEvents()">Recent</button>
    </div>
    <div class="grid" id="stats"></div>
    <div class="status" id="status"></div>
    <div id="events"></div>
    <section class="chat-shell">
      <div class="chat-header">
        <div>
          <strong>AIFluent Chat</strong>
          <div class="status" id="chatStatus"></div>
        </div>
        <div class="chat-tools">
          <input id="chatTag" placeholder="session tag">
          <button class="secondary" onclick="saveChatSession()">Save</button>
          <button class="secondary" onclick="clearChat()">Clear Chat</button>
        </div>
      </div>
      <div class="chat-sessions" id="chatSessions"></div>
      <div class="chat-log" id="chatLog"></div>
      <div class="chat-input">
        <textarea id="chatPrompt" spellcheck="true" placeholder="Ask about the project, your memory data, or the configured models."></textarea>
        <button onclick="sendChat()">Send</button>
      </div>
    </section>
  </main>
  <aside class="drawer" id="settingsDrawer">
    <div class="drawer-header">
      <div>
        <strong>Model Settings</strong>
        <div class="status" id="settingsPath"></div>
      </div>
      <button class="secondary" onclick="closeSettings()">Close</button>
    </div>
    <div class="drawer-body">
      <div class="meta" id="runtimeMeta">Loading runtime info...</div>
      <div class="field">
        <label for="envModelConfig">AIFLUENT_MODEL_CONFIG</label>
        <input id="envModelConfig" placeholder="config/models.yaml">
      </div>
      <div class="field">
        <label for="envDataRoot">AIFLUENT_DATA_ROOT</label>
        <input id="envDataRoot" placeholder="data">
      </div>
      <div class="actions">
        <button class="secondary" onclick="saveEnvSettings(true)">Save Env and Reload</button>
      </div>
      <textarea id="modelsYaml" spellcheck="false"></textarea>
      <div class="actions">
        <button class="secondary" onclick="testSettings()">Test Config</button>
        <button onclick="saveSettings(true)">Save and Reload</button>
        <button class="secondary" onclick="loadSettings()">Reload from Disk</button>
      </div>
      <div class="status" id="settingsStatus"></div>
    </div>
  </aside>
  <script>
    function setStatus(msg, error=false) {
      const el = document.getElementById('status');
      el.textContent = msg || '';
      el.style.color = error ? '#b91c1c' : 'var(--muted)';
    }
    function setSettingsStatus(msg, error=false) {
      const el = document.getElementById('settingsStatus');
      el.textContent = msg || '';
      el.style.color = error ? '#b91c1c' : 'var(--muted)';
    }
    function setChatStatus(msg, error=false) {
      const el = document.getElementById('chatStatus');
      el.textContent = msg || '';
      el.style.color = error ? '#b91c1c' : 'var(--muted)';
    }
    function setChatSessions(msg, error=false) {
      const el = document.getElementById('chatSessions');
      el.innerHTML = msg || '';
      el.style.color = error ? '#b91c1c' : 'var(--muted)';
    }
    let chatHistory = [];
    async function loadStats() {
      const res = await fetch('/memory/api/stats');
      const stats = await res.json();
      document.getElementById('stats').innerHTML = stats.map(s =>
        `<div class="card"><div class="kind">${s.kind}</div><div><strong>${s.count}</strong> events</div></div>`
      ).join('');
    }
    async function loadEvents() {
      setStatus('Loading recent events...');
      const res = await fetch('/memory/api/events?limit=20');
      const events = await res.json();
      renderEvents(events);
      setStatus(`Loaded ${events.length} recent events.`);
    }
    async function loadSearch() {
      const q = document.getElementById('query').value.trim();
      const url = q ? '/memory/api/search?q=' + encodeURIComponent(q) : '/memory/api/events?limit=20';
      setStatus(q ? `Searching for "${q}"...` : 'Loading recent events...');
      const res = await fetch(url);
      const events = await res.json();
      renderEvents(events);
      setStatus(q ? `Found ${events.length} matching events.` : `Loaded ${events.length} recent events.`);
    }
    function renderEvents(events) {
      document.getElementById('events').innerHTML = events.map(e =>
        `<div class="event">
          <div class="kind">${e.kind}</div>
          <div>${new Date(e.timestamp * 1000).toLocaleString()}</div>
          <pre>${JSON.stringify(e.data, null, 2)}</pre>
        </div>`
      ).join('');
    }
    function renderChat() {
      const log = document.getElementById('chatLog');
      log.innerHTML = chatHistory.map(m =>
        `<div class="bubble ${m.role === 'user' ? 'user' : 'assistant'}">${escapeHtml(m.content)}</div>`
      ).join('');
      log.scrollTop = log.scrollHeight;
    }
    function escapeHtml(text) {
      return (text || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    }
    function clearChat() {
      chatHistory = [];
      renderChat();
      setChatStatus('Chat cleared.');
    }
    async function saveChatSession() {
      const tag = document.getElementById('chatTag').value.trim();
      if (!tag) {
        setChatStatus('Enter a session tag before saving.', true);
        return;
      }
      const res = await fetch('/chat/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tag, messages: chatHistory })
      });
      const body = await res.json();
      if (!res.ok) {
        setChatStatus(body.detail || 'Failed to save chat session.', true);
        return;
      }
      setChatStatus(`Saved chat session "${tag}".`);
      loadChatSessions();
    }
    async function loadChatSessions() {
      const res = await fetch('/chat/sessions');
      const body = await res.json();
      if (!res.ok) {
        setChatSessions('Failed to load sessions.', true);
        return;
      }
      if (!body.length) {
        setChatSessions('<span class="chat-session-meta">No saved sessions.</span>');
        return;
      }
      setChatSessions(body.map(s =>
        `<div class="chat-session-item">
          <span>${escapeHtml(s.tag)}</span>
          <span class="chat-session-meta">(${s.message_count})</span>
          <button class="secondary" onclick="resumeChatSession('${escapeHtml(s.tag)}')">Load</button>
          <button class="secondary" onclick="deleteChatSession('${escapeHtml(s.tag)}')">Delete</button>
        </div>`
      ).join(''));
    }
    async function resumeChatSession(tag) {
      const res = await fetch('/chat/sessions/' + encodeURIComponent(tag));
      const body = await res.json();
      if (!res.ok) {
        setChatStatus(body.detail || 'Failed to load chat session.', true);
        return;
      }
      chatHistory = body.messages || [];
      document.getElementById('chatTag').value = body.tag || tag;
      renderChat();
      setChatStatus(`Loaded session "${tag}".`);
    }
    async function deleteChatSession(tag) {
      const res = await fetch('/chat/sessions/' + encodeURIComponent(tag), { method: 'DELETE' });
      const body = await res.json();
      if (!res.ok) {
        setChatStatus(body.detail || 'Failed to delete chat session.', true);
        return;
      }
      if (document.getElementById('chatTag').value.trim() === tag) {
        document.getElementById('chatTag').value = '';
      }
      setChatStatus(`Deleted session "${tag}".`);
      loadChatSessions();
    }
    async function sendChat() {
      const promptEl = document.getElementById('chatPrompt');
      const content = promptEl.value.trim();
      if (!content) return;
      chatHistory.push({ role: 'user', content });
      renderChat();
      promptEl.value = '';
      setChatStatus('Waiting for model response...');
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: chatHistory })
      });
      const body = await res.json();
      if (!res.ok) {
        setChatStatus(body.detail || 'Chat request failed.', true);
        return;
      }
      const reply = (body.message && body.message.content) || '';
      chatHistory.push({ role: 'assistant', content: reply });
      renderChat();
      setChatStatus(`Responded with ${body.model}.`);
      loadChatSessions();
    }
    function openSettings() {
      document.getElementById('settingsDrawer').classList.add('open');
      loadSettings();
    }
    function closeSettings() {
      document.getElementById('settingsDrawer').classList.remove('open');
    }
    function renderRuntime(runtime) {
      const lines = (runtime.active_models || []).map(m => `${m.name} (${m.type}) -> ${m.path}`);
      document.getElementById('runtimeMeta').textContent =
        `Config: ${runtime.config_path}\nVoting threshold: ${runtime.voting_threshold}\nActive models:\n${lines.join('\n') || 'None'}`;
    }
    async function loadEnvSettings() {
      const res = await fetch('/config/env');
      const body = await res.json();
      if (!res.ok) {
        setSettingsStatus(body.detail || 'Failed to load .env settings.', true);
        return;
      }
      document.getElementById('envModelConfig').value = body.values.AIFLUENT_MODEL_CONFIG || 'config/models.yaml';
      document.getElementById('envDataRoot').value = body.values.AIFLUENT_DATA_ROOT || 'data';
    }
    async function loadSettings() {
      setSettingsStatus('Loading config...');
      await loadEnvSettings();
      const res = await fetch('/config/models');
      const body = await res.json();
      if (!res.ok) {
        setSettingsStatus(body.detail || 'Failed to load config.', true);
        return;
      }
      document.getElementById('settingsPath').textContent = body.path;
      document.getElementById('modelsYaml').value = body.content;
      renderRuntime(body.runtime);
      setSettingsStatus('Loaded config from disk.');
    }
    async function saveEnvSettings(reload) {
      setSettingsStatus(reload ? 'Saving .env and reloading...' : 'Saving .env...');
      const payload = {
        aifluent_model_config: document.getElementById('envModelConfig').value,
        aifluent_data_root: document.getElementById('envDataRoot').value,
        reload: !!reload
      };
      const res = await fetch('/config/env', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const body = await res.json();
      if (!res.ok) {
        setSettingsStatus(body.detail || 'Failed to save .env settings.', true);
        return;
      }
      renderRuntime(body.runtime);
      setSettingsStatus(reload ? 'Saved .env and reloaded runtime.' : 'Saved .env.');
      setStatus('Environment settings updated.');
    }
    async function saveSettings(reload) {
      setSettingsStatus(reload ? 'Saving and reloading...' : 'Saving...');
      const payload = {
        content: document.getElementById('modelsYaml').value,
        reload: !!reload
      };
      const res = await fetch('/config/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const body = await res.json();
      if (!res.ok) {
        setSettingsStatus(body.detail || 'Failed to save config.', true);
        return;
      }
      renderRuntime(body.runtime);
      setSettingsStatus(reload ? 'Saved config and reloaded runtime.' : 'Saved config.');
      setStatus('Configuration updated.');
    }
    async function testSettings() {
      setSettingsStatus('Validating config...');
      const payload = {
        content: document.getElementById('modelsYaml').value,
        aifluent_model_config: document.getElementById('envModelConfig').value,
        aifluent_data_root: document.getElementById('envDataRoot').value
      };
      const res = await fetch('/config/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const body = await res.json();
      if (!res.ok) {
        setSettingsStatus(body.detail || 'Validation failed.', true);
        return;
      }
      setSettingsStatus(`Validation passed: ${body.model_count} models, data root ${body.data_root}`);
    }
    loadStats();
    loadEvents();
    renderChat();
    loadChatSessions();
  </script>
</body>
</html>
"""


@router.get("/api/events")
def api_events(
    kind: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
    limit: int = 200,
) -> list[dict]:
    events = get_store().query_raw(kind=kind, since=since, until=until, limit=min(limit, 2000))
    return [serialize_event(event) for event in events]


@router.get("/api/search")
def api_search(q: str = "", kind: Optional[str] = None, limit: int = 100) -> list[dict]:
    if not q.strip():
        return []
    events = get_store().search(q, kind=kind, limit=min(limit, 500))
    return [serialize_event(event) for event in events]


@router.get("/api/stats")
def api_stats() -> list[dict]:
    return get_store().stats()


@router.get("/api/timeline")
def api_timeline(
    since: Optional[float] = None,
    until: Optional[float] = None,
    limit: int = 2000,
) -> dict:
    events = get_store().query_raw(since=since, until=until, limit=min(limit, 5000))
    grouped: dict[str, list] = {}
    for event in events:
        grouped.setdefault(event.kind, []).append(serialize_event(event))
    return {"since": since, "until": until, "tracks": grouped}


@router.post("/api/events")
def api_add_event(payload: MemoryEventCreate) -> dict:
    event = Event(
        timestamp=payload.timestamp or time.time(),
        kind=payload.kind,
        data=payload.data,
        blob=payload.blob,
    )
    get_store().insert_raw([event])
    return {"status": "ok"}


def dump_search_results(query: str, limit: int = 20) -> str:
    events = [serialize_event(event) for event in get_store().search(query, limit=limit)]
    return json.dumps(events, indent=2, ensure_ascii=False)
