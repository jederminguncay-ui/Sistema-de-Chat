"use strict";

const API_BASE = `http://${location.hostname}:8000`;
const WS_BASE = `ws://${location.hostname}:8080`;
const STORAGE_KEY = "sdc_session";

const state = {
  user: null, 
  ws: null, 
  conversations: [], 
  active: null, 
  messages: [], 
  reconnectTimer: null,
};

const $ = (id) => document.getElementById(id);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function initials(first, last) {
  const a = (first || "").trim().charAt(0);
  const b = (last || "").trim().charAt(0);
  return (a + b).toUpperCase() || "?";
}

function parseDate(value) {
  if (!value) return new Date();
  let s = String(value);
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(s);
  if (!hasZone) s += "Z";
  const d = new Date(s);
  return isNaN(d.getTime()) ? new Date() : d;
}

function formatTime(value) {
  return parseDate(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function dayLabel(value) {
  const d = parseDate(value);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const sameDay = (x, y) =>
    x.getFullYear() === y.getFullYear() &&
    x.getMonth() === y.getMonth() &&
    x.getDate() === y.getDate();
  if (sameDay(d, today)) return "Hoy";
  if (sameDay(d, yesterday)) return "Ayer";
  return d.toLocaleDateString([], {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

function dayKey(value) {
  const d = parseDate(value);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

async function api(path, { method = "GET", body = null, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && state.user && state.user.token) {
    headers["Authorization"] = `Bearer ${state.user.token}`;
  }
  let response;
  try {
    response = await fetch(API_BASE + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
    });
  } catch (networkError) {
    throw new Error("No se pudo conectar con el servidor.");
  }

  if (response.status === 401) {
    logout();
    throw new Error("Tu sesión expiró. Inicia sesión nuevamente.");
  }

  let data = null;
  const textBody = await response.text();
  if (textBody) {
    try {
      data = JSON.parse(textBody);
    } catch (_) {
      data = null;
    }
  }

  if (!response.ok) {
    const detail = data && data.detail ? data.detail : "Error en la solicitud.";
    throw new Error(detail);
  }
  return data;
}

function saveSession() {
  if (state.user) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.user));
  }
}

function loadSession() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return false;
  try {
    state.user = JSON.parse(raw);
    return !!(state.user && state.user.token);
  } catch (_) {
    localStorage.removeItem(STORAGE_KEY);
    return false;
  }
}

function showAuthError(target, message) {
  const node = $(target);
  node.textContent = message || "";
}

async function handleRegister() {
  showAuthError("register-error", "");
  const first_name = $("reg-first").value.trim();
  const last_name = $("reg-last").value.trim();
  const username = $("reg-username").value.trim();
  const password = $("reg-password").value;

  if (!first_name || !last_name || !username || !password) {
    showAuthError("register-error", "Todos los campos son obligatorios.");
    return;
  }

  try {
    await api("/register", {
      method: "POST",
      auth: false,
      body: { first_name, last_name, username, password },
    });
    // Tras registrarse, iniciar sesión automáticamente.
    await doLogin(username, password, "register-error");
  } catch (err) {
    showAuthError("register-error", err.message);
  }
}

async function handleLogin() {
  showAuthError("login-error", "");
  const username = $("login-username").value.trim();
  const password = $("login-password").value;
  if (!username || !password) {
    showAuthError("login-error", "Ingresa usuario y contraseña.");
    return;
  }
  await doLogin(username, password, "login-error");
}

async function doLogin(username, password, errorTarget) {
  try {
    const data = await api("/login", {
      method: "POST",
      auth: false,
      body: { username, password },
    });
    state.user = data; // incluye token
    saveSession();
    enterApp();
  } catch (err) {
    showAuthError(errorTarget, err.message);
  }
}

function logout() {
  localStorage.removeItem(STORAGE_KEY);
  if (state.ws) {
    try {
      state.ws.close();
    } catch (_) {}
  }
  if (state.reconnectTimer) {
    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = null;
  }
  state.user = null;
  state.ws = null;
  state.conversations = [];
  state.active = null;
  state.messages = [];
  $("app-screen").classList.add("is-hidden");
  $("auth-screen").classList.remove("is-hidden");
  $("login-username").value = "";
  $("login-password").value = "";
}

function enterApp() {
  $("auth-screen").classList.add("is-hidden");
  $("app-screen").classList.remove("is-hidden");

  $("me-avatar").textContent = initials(
    state.user.first_name,
    state.user.last_name
  );
  $("me-name").textContent = `${state.user.first_name} ${state.user.last_name}`;
  $("me-username").textContent = "@" + state.user.username;

  connectWS();
  loadConversations();
}

function connectWS() {
  if (!state.user) return;
  const url = `${WS_BASE}/ws?token=${encodeURIComponent(state.user.token)}`;
  const ws = new WebSocket(url);
  state.ws = ws;

  ws.onmessage = (event) => {
    let frame;
    try {
      frame = JSON.parse(event.data);
    } catch (_) {
      return;
    }
    handleServerFrame(frame);
  };

  ws.onclose = () => {
    if (state.user && !state.reconnectTimer) {
      state.reconnectTimer = setTimeout(() => {
        state.reconnectTimer = null;
        connectWS();
      }, 2000);
    }
  };

  ws.onerror = () => {
    try {
      ws.close();
    } catch (_) {}
  };
}

function wsSend(obj) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(obj));
    return true;
  }
  return false;
}

function handleServerFrame(frame) {
  switch (frame.type) {
    case "sent":
      onSentAck(frame);
      break;
    case "message":
      onIncomingMessage(frame);
      break;
    case "read":
      onReadReceipt(frame);
      break;
    case "error":
      console.warn("WS error:", frame.detail);
      break;
    default:
      break;
  }
}

function onSentAck(frame) {
  const msg = state.messages.find((m) => m.temp_id && m.temp_id === frame.temp_id);
  if (msg) {
    msg.id = frame.id;
    msg.created_at = frame.created_at;
    msg.delivered = !!frame.delivered;
    msg.read = !!frame.read;
    msg.pending = false;
    delete msg.temp_id;
  }
  if (state.active && state.active.id === frame.conversation_id) {
    renderMessages();
  }
}

function onIncomingMessage(frame) {
  const incoming = {
    id: frame.id,
    conversation_id: frame.conversation_id,
    sender_id: frame.sender_id,
    receiver_id: frame.receiver_id,
    content: frame.content,
    created_at: frame.created_at,
    delivered: true,
    read: false,
  };

  if (state.active && state.active.id === frame.conversation_id) {
    state.messages.push(incoming);
    renderMessages();
    markVisibleAsRead();
  } else {
    bumpConversationPreview(frame.conversation_id, frame.content, frame.created_at, true);
  }
  refreshSidebarPreview(frame.conversation_id, frame.content, frame.created_at);
}

function onReadReceipt(frame) {
  let changed = false;
  for (const m of state.messages) {
    if (m.id === frame.id) {
      m.read = true;
      m.delivered = true;
      changed = true;
    }
  }
  if (changed && state.active && state.active.id === frame.conversation_id) {
    renderMessages();
  }
}

async function loadConversations() {
  try {
    state.conversations = await api("/conversations");
    renderConversations();
  } catch (err) {
    console.warn("No se pudieron cargar las conversaciones:", err.message);
  }
}

function renderConversations() {
  const list = $("conversation-list");
  list.innerHTML = "";

  if (!state.conversations.length) {
    const empty = el("div", "search-empty", "Aún no tienes conversaciones.");
    list.appendChild(empty);
    return;
  }

  for (const conv of state.conversations) {
    const item = el("div", "conv");
    if (state.active && state.active.id === conv.id) {
      item.classList.add("is-active");
    }

    const avatar = el(
      "span",
      "avatar",
      initials(conv.other_user.first_name, conv.other_user.last_name)
    );

    const body = el("div", "conv-body");
    const top = el("div", "conv-top");
    const name = el(
      "span",
      "conv-name",
      `${conv.other_user.first_name} ${conv.other_user.last_name}`
    );
    const time = el(
      "span",
      "conv-time",
      conv.last_message_at ? formatTime(conv.last_message_at) : ""
    );
    top.appendChild(name);
    top.appendChild(time);

    const preview = el(
      "div",
      "conv-preview",
      conv.last_message || "Inicia la conversación"
    );

    body.appendChild(top);
    body.appendChild(preview);

    item.appendChild(avatar);
    item.appendChild(body);

    if (conv.unread_count > 0) {
      item.appendChild(el("span", "badge", String(conv.unread_count)));
    }

    item.addEventListener("click", () => openConversation(conv));
    list.appendChild(item);
  }
}

function refreshSidebarPreview(conversationId, content, createdAt) {
  const conv = state.conversations.find((c) => c.id === conversationId);
  if (conv) {
    conv.last_message = content;
    conv.last_message_at = createdAt;
    // Reordenar por actividad reciente.
    state.conversations.sort(
      (a, b) =>
        parseDate(b.last_message_at || b.created_at) -
        parseDate(a.last_message_at || a.created_at)
    );
    renderConversations();
  } else {
    loadConversations();
  }
}

function bumpConversationPreview(conversationId, content, createdAt, incrementUnread) {
  const conv = state.conversations.find((c) => c.id === conversationId);
  if (conv && incrementUnread) {
    conv.unread_count = (conv.unread_count || 0) + 1;
  }
}

let searchTimer = null;

function onSearchInput() {
  const q = $("search-input").value.trim();
  if (searchTimer) clearTimeout(searchTimer);
  if (!q) {
    hideSearchResults();
    return;
  }
  searchTimer = setTimeout(() => runSearch(q), 250);
}

async function runSearch(q) {
  try {
    const users = await api(`/users/search?q=${encodeURIComponent(q)}`);
    renderSearchResults(users);
  } catch (err) {
    renderSearchResults([]);
  }
}

function renderSearchResults(users) {
  const box = $("search-results");
  box.innerHTML = "";
  box.classList.remove("is-hidden");

  if (!users.length) {
    box.appendChild(el("div", "search-empty", "Sin resultados."));
    return;
  }

  for (const u of users) {
    const item = el("div", "search-item");
    item.appendChild(el("span", "avatar", initials(u.first_name, u.last_name)));
    const info = el("div", "conv-body");
    info.appendChild(
      el("div", "conv-name", `${u.first_name} ${u.last_name}`)
    );
    info.appendChild(el("div", "conv-preview", "@" + u.username));
    item.appendChild(info);
    item.addEventListener("click", () => startConversation(u));
    box.appendChild(item);
  }
}

function hideSearchResults() {
  const box = $("search-results");
  box.classList.add("is-hidden");
  box.innerHTML = "";
}

async function startConversation(user) {
  try {
    const conv = await api("/conversation/create", {
      method: "POST",
      body: { other_user_id: user.id },
    });
    $("search-input").value = "";
    hideSearchResults();

    const existing = state.conversations.find((c) => c.id === conv.id);
    if (!existing) {
      state.conversations.unshift(conv);
    }
    renderConversations();
    openConversation(conv);
  } catch (err) {
    console.warn("No se pudo crear la conversación:", err.message);
  }
}

async function openConversation(conv) {
  state.active = conv;
  $("chat-empty").classList.add("is-hidden");
  $("chat-active").classList.remove("is-hidden");
  $("app-screen").classList.add("show-chat"); // vista móvil

  $("peer-avatar").textContent = initials(
    conv.other_user.first_name,
    conv.other_user.last_name
  );
  $("peer-name").textContent = `${conv.other_user.first_name} ${conv.other_user.last_name}`;
  $("peer-username").textContent = "@" + conv.other_user.username;

  renderConversations();

  try {
    const detail = await api(`/conversation/${conv.id}`);
    state.messages = (detail.messages || []).map((m) => ({ ...m }));
    renderMessages();
    markVisibleAsRead();
    const c = state.conversations.find((x) => x.id === conv.id);
    if (c) {
      c.unread_count = 0;
      renderConversations();
    }
  } catch (err) {
    console.warn("No se pudo abrir la conversación:", err.message);
  }
}

function renderMessages() {
  const container = $("messages");
  container.innerHTML = "";
  let lastDay = null;

  for (const m of state.messages) {
    const key = dayKey(m.created_at);
    if (key !== lastDay) {
      container.appendChild(el("div", "day-sep", dayLabel(m.created_at)));
      lastDay = key;
    }

    const mine = m.sender_id === state.user.id;
    const bubble = el("div", "bubble " + (mine ? "out" : "in"));
    bubble.appendChild(el("div", "bubble-text", m.content));

    const meta = el("div", "bubble-meta");
    meta.appendChild(el("span", "bubble-time", formatTime(m.created_at)));

    if (mine) {
      const ticks = el("span", "ticks");
      if (m.pending) {
        ticks.textContent = "·"; // en envío
      } else if (m.read) {
        ticks.textContent = "\u2713\u2713";
        ticks.classList.add("read");
      } else if (m.delivered) {
        ticks.textContent = "\u2713\u2713";
      } else {
        ticks.textContent = "\u2713";
      }
      meta.appendChild(ticks);
    }

    bubble.appendChild(meta);
    container.appendChild(bubble);
  }

  container.scrollTop = container.scrollHeight;
}

function sendMessage() {
  const input = $("message-input");
  const content = input.value.trim();
  if (!content || !state.active) return;

  const temp_id = "tmp-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  const optimistic = {
    temp_id,
    id: null,
    conversation_id: state.active.id,
    sender_id: state.user.id,
    receiver_id: state.active.other_user.id,
    content,
    created_at: new Date().toISOString(),
    delivered: false,
    read: false,
    pending: true,
  };
  state.messages.push(optimistic);
  renderMessages();
  input.value = "";
  input.focus();

  const ok = wsSend({
    type: "send",
    temp_id,
    conversation_id: state.active.id,
    receiver_id: state.active.other_user.id,
    content,
  });
  if (!ok) {
    optimistic.pending = false;
    renderMessages();
  }

  refreshSidebarPreview(state.active.id, content, optimistic.created_at);
}

function markVisibleAsRead() {
  if (!state.active) return;
  const ids = state.messages
    .filter((m) => m.receiver_id === state.user.id && !m.read && m.id)
    .map((m) => m.id);
  if (!ids.length) return;
  wsSend({ type: "read", message_ids: ids });
  // Actualización local inmediata.
  for (const m of state.messages) {
    if (ids.includes(m.id)) {
      m.read = true;
      m.delivered = true;
    }
  }
}

function bindEvents() {
  $("tab-login").addEventListener("click", () => {
    $("tab-login").classList.add("is-active");
    $("tab-register").classList.remove("is-active");
    $("login-form").classList.remove("is-hidden");
    $("register-form").classList.add("is-hidden");
  });
  $("tab-register").addEventListener("click", () => {
    $("tab-register").classList.add("is-active");
    $("tab-login").classList.remove("is-active");
    $("register-form").classList.remove("is-hidden");
    $("login-form").classList.add("is-hidden");
  });

  $("login-btn").addEventListener("click", handleLogin);
  $("register-btn").addEventListener("click", handleRegister);

  $("login-password").addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleLogin();
  });
  $("reg-password").addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleRegister();
  });

  $("logout-btn").addEventListener("click", logout);

  $("search-input").addEventListener("input", onSearchInput);
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-box")) hideSearchResults();
  });

  $("send-btn").addEventListener("click", sendMessage);
  $("message-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });
}

function init() {
  bindEvents();
  if (loadSession()) {
    enterApp();
  }
}

document.addEventListener("DOMContentLoaded", init);