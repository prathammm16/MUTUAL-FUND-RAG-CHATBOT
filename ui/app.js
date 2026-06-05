/**
 * Groww Chatbot UI — multi-chat + POST /api/chat
 */

const API_BASE = window.__API_BASE__ || "";
const CHAT_TIMEOUT_MS = 30_000;
const STORAGE_KEY = "groww-chatbot-sessions";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const messagesEl = $("#messages");
const welcomeEl = $("#welcome-panel");
const formEl = $("#chat-form");
const inputEl = $("#message-input");
const sendBtn = $("#send-btn");
const hintEl = $("#composer-hint");
const statusEl = $("#api-status");
const schemeListEl = $("#scheme-list");
const chatListEl = $("#chat-list");

let busy = false;

/** @type {{ chats: Array<{id:string,title:string,messages:Array,messages:object[],updatedAt:number}>, activeId: string }} */
let sessionState = { chats: [], activeId: "" };

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function isSafeUrl(url) {
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

function formatAnswerHtml(raw) {
  const escaped = escapeHtml(raw || "");
  return escaped.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/gi,
    (_match, label, url) => {
      if (!isSafeUrl(url)) return escapeHtml(label);
      const safeUrl = escapeHtml(url);
      return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
    }
  );
}

function newChatId() {
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.chats?.length) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveSessions() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessionState));
  } catch {
    /* quota or private mode */
  }
}

function defaultChatTitle() {
  return `Chat ${sessionState.chats.length + 1}`;
}

function createChat(title = null) {
  const chat = {
    id: newChatId(),
    title: title ?? defaultChatTitle(),
    messages: [],
    updatedAt: Date.now(),
  };
  sessionState.chats.unshift(chat);
  sessionState.activeId = chat.id;
  saveSessions();
  return chat;
}

function getActiveChat() {
  return sessionState.chats.find((c) => c.id === sessionState.activeId) ?? null;
}

function ensureSessions() {
  const saved = loadSessions();
  if (saved) {
    sessionState = saved;
    if (!sessionState.chats.some((c) => c.id === sessionState.activeId)) {
      sessionState.activeId = sessionState.chats[0]?.id ?? "";
    }
  }
  if (!sessionState.chats.length) {
    createChat();
  }
}

function chatTitleFromMessage(text) {
  const t = text.trim();
  if (t.length <= 42) return t;
  return `${t.slice(0, 42)}…`;
}

function setBusy(value) {
  busy = value;
  if (sendBtn) sendBtn.disabled = value || !inputEl?.value.trim();
  if (inputEl) inputEl.disabled = value;
}

function updateSendEnabled() {
  if (sendBtn) sendBtn.disabled = busy || !inputEl?.value.trim();
}

function hideWelcome() {
  welcomeEl?.classList.add("hidden");
}

function showWelcomeIfEmpty() {
  const chat = getActiveChat();
  if (!chat?.messages.length) {
    welcomeEl?.classList.remove("hidden");
  }
}

function openMobileSidebar() {
  $("#sidebar")?.classList.add("open-mobile");
  const backdrop = $("#sidebar-backdrop");
  backdrop?.classList.add("visible");
  backdrop?.setAttribute("aria-hidden", "false");
  document.body.classList.add("sidebar-open");
}

function closeMobileSidebar() {
  $("#sidebar")?.classList.remove("open-mobile");
  const backdrop = $("#sidebar-backdrop");
  backdrop?.classList.remove("visible");
  backdrop?.setAttribute("aria-hidden", "true");
  document.body.classList.remove("sidebar-open");
}

function toggleMobileSidebar() {
  if ($("#sidebar")?.classList.contains("open-mobile")) {
    closeMobileSidebar();
  } else {
    openMobileSidebar();
  }
}

function scrollChatToTop() {
  const main = $("#chat-main");
  main?.scrollTo({ top: 0, behavior: "smooth" });
}

function scrollToBottom() {
  const main = $("#chat-main");
  main?.scrollTo({ top: main.scrollHeight, behavior: "smooth" });
}

function persistUserMessage(text) {
  const chat = getActiveChat();
  if (!chat) return;
  chat.messages.push({ role: "user", text });
  if (/^Chat \d+$/.test(chat.title) && text.trim()) {
    chat.title = chatTitleFromMessage(text);
  }
  chat.updatedAt = Date.now();
  saveSessions();
  renderChatList();
}

function persistAssistantMessage(payload) {
  const chat = getActiveChat();
  if (!chat) return;
  chat.messages.push({ role: "assistant", payload });
  chat.updatedAt = Date.now();
  saveSessions();
  renderChatList();
}

function appendUserMessage(text, { persist = true } = {}) {
  hideWelcome();
  const wrap = document.createElement("div");
  wrap.className = "msg-user";
  wrap.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  messagesEl.appendChild(wrap);
  if (persist) persistUserMessage(text);
  scrollToBottom();
  return wrap;
}

function appendLoading() {
  const wrap = document.createElement("div");
  wrap.className = "msg-assistant loading-row";
  wrap.dataset.loading = "true";
  wrap.innerHTML = `
    <div class="avatar muted" aria-hidden="true">
      <span class="material-symbols-outlined">smart_toy</span>
    </div>
    <div class="glass-card">
      <div class="typing-row" aria-busy="true" aria-label="Loading">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span style="margin-left:0.5rem;color:var(--text-muted);font-size:0.85rem">Searching corpus…</span>
      </div>
    </div>`;
  messagesEl.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

function removeLoading(node) {
  node?.remove();
}

function buildCitationHtml(citationUrl, label = "View scheme on Groww") {
  if (!citationUrl || !isSafeUrl(citationUrl)) return "";
  const url = escapeHtml(citationUrl);
  return `<a class="citation-link" href="${url}" target="_blank" rel="noopener noreferrer">
    <span class="material-symbols-outlined" aria-hidden="true">link</span>
    ${escapeHtml(label)}
  </a>`;
}

function appendAssistantMessage(payload, { persist = true } = {}) {
  const { answer, citation_url, footer, type } = payload;
  const isRefusal = type === "refusal";
  const isNotFound = type === "not_found";
  const isError = type === "error";

  const wrap = document.createElement("div");
  wrap.className = "msg-assistant";

  let cardClass = "glass-card";
  let badgeClass = "badge-verified";
  let labelText = "Verified response";
  let labelClass = "label-tag";
  let title = "Factual answer";
  let showCompliance = !isRefusal && !isError;

  if (isRefusal) {
    cardClass += " refusal-card";
    badgeClass += " badge-refusal";
    labelText = "Compliance protocol";
    labelClass += " refusal";
    title = "No investment advice";
    showCompliance = false;
  } else if (isNotFound) {
    cardClass += " not-found-card";
    labelText = "Not in corpus";
    title = "No matching facts";
  } else if (isError) {
    wrap.classList.add("msg-error");
    labelText = "Error";
    title = "Something went wrong";
    showCompliance = false;
  } else {
    cardClass += " answer-glow";
  }

  const bodyHtml = formatAnswerHtml(answer);
  const citationHtml =
    !isRefusal && citation_url && isSafeUrl(citation_url)
      ? buildCitationHtml(citation_url)
      : isRefusal && citation_url && isSafeUrl(citation_url)
        ? buildCitationHtml(citation_url, "Investor education resource")
        : "";

  const footerHtml = footer
    ? `<span class="source-meta">${escapeHtml(footer)}</span>`
    : "";

  wrap.innerHTML = `
    <div class="avatar ${isRefusal ? "muted" : ""}" aria-hidden="true">
      <span class="material-symbols-outlined" style="${isRefusal ? "" : "font-variation-settings:'FILL' 1"}">smart_toy</span>
    </div>
    <article class="${cardClass}">
      <header class="card-header">
        <div>
          <div class="${labelClass}">
            ${isRefusal ? '<span class="material-symbols-outlined" style="color:var(--warning);font-size:1rem">warning</span>' : '<span class="label-dot"></span>'}
            <span>${escapeHtml(labelText)}</span>
          </div>
          <h3 class="card-title">${escapeHtml(title)}</h3>
        </div>
        <span class="${badgeClass}">
          <span class="material-symbols-outlined" style="font-size:1rem;${isRefusal ? "" : "font-variation-settings:'FILL' 1"}">${isRefusal ? "gavel" : "verified"}</span>
          ${isRefusal ? "Refusal" : isNotFound ? "Not found" : "Source verified"}
        </span>
      </header>
      <div class="card-body">${bodyHtml}</div>
      ${citationHtml || footerHtml ? `<footer class="card-footer">${citationHtml}${footerHtml}</footer>` : ""}
      ${showCompliance ? `<div class="compliance-note"><strong>Disclaimer</strong> Mutual fund investments are subject to market risks. This assistant shares scheme-page facts only — not recommendations.</div>` : ""}
    </article>`;

  messagesEl.appendChild(wrap);
  if (persist) persistAssistantMessage(payload);
  scrollToBottom();
}

function renderMessagesFromChat() {
  if (!messagesEl) return;
  messagesEl.innerHTML = "";
  const chat = getActiveChat();
  if (!chat?.messages.length) {
    showWelcomeIfEmpty();
    return;
  }
  hideWelcome();
  for (const msg of chat.messages) {
    if (msg.role === "user") {
      appendUserMessage(msg.text, { persist: false });
    } else if (msg.role === "assistant") {
      appendAssistantMessage(msg.payload, { persist: false });
    }
  }
}

function renderChatList() {
  if (!chatListEl) return;
  chatListEl.innerHTML = "";
  const sorted = [...sessionState.chats].sort((a, b) => b.updatedAt - a.updatedAt);

  for (const chat of sorted) {
    const li = document.createElement("li");
    li.className = `chat-list-item${chat.id === sessionState.activeId ? " active" : ""}`;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chat-list-btn";
    btn.innerHTML = `
      <span class="material-symbols-outlined chat-list-icon" aria-hidden="true">chat_bubble_outline</span>
      <span class="chat-list-title">${escapeHtml(chat.title)}</span>`;
    btn.addEventListener("click", () => switchChat(chat.id));

    const del = document.createElement("button");
    del.type = "button";
    del.className = "chat-delete-btn";
    del.setAttribute("aria-label", `Delete ${chat.title}`);
    del.innerHTML = '<span class="material-symbols-outlined" aria-hidden="true">close</span>';
    del.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteChat(chat.id);
    });

    li.appendChild(btn);
    li.appendChild(del);
    chatListEl.appendChild(li);
  }
}

function switchChat(id) {
  if (id === sessionState.activeId || busy) return;
  sessionState.activeId = id;
  saveSessions();
  renderChatList();
  renderMessagesFromChat();
  resetComposer();
  scrollChatToTop();
  inputEl?.focus();
  closeMobileSidebar();
}

function resetComposer() {
  if (inputEl) inputEl.value = "";
  if (hintEl) hintEl.textContent = "";
  updateSendEnabled();
}

function startNewChat() {
  if (busy) return;

  const active = getActiveChat();

  // Already on a blank draft — reset the view instead of creating duplicates.
  if (active && !active.messages.length) {
    renderChatList();
    renderMessagesFromChat();
    resetComposer();
    scrollChatToTop();
    inputEl?.focus();
    closeMobileSidebar();
    return;
  }

  createChat();
  renderChatList();
  renderMessagesFromChat();
  resetComposer();
  scrollChatToTop();
  inputEl?.focus();
  closeMobileSidebar();
}

function deleteChat(id) {
  if (sessionState.chats.length <= 1) {
    sessionState.chats = [];
    createChat();
  } else {
    sessionState.chats = sessionState.chats.filter((c) => c.id !== id);
    if (sessionState.activeId === id) {
      sessionState.activeId = sessionState.chats[0].id;
    }
  }
  saveSessions();
  renderChatList();
  renderMessagesFromChat();
}

async function fetchChat(message) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail ?? data.message ?? res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  } catch (err) {
    clearTimeout(timer);
    if (err.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw err;
  }
}

async function sendMessage(text) {
  const trimmed = text.trim();
  if (!trimmed || busy) return;

  hintEl.textContent = "";
  setBusy(true);
  appendUserMessage(trimmed);
  inputEl.value = "";
  updateSendEnabled();

  const loading = appendLoading();
  try {
    const data = await fetchChat(trimmed);
    removeLoading(loading);
    appendAssistantMessage(data);
  } catch (err) {
    removeLoading(loading);
    appendAssistantMessage({
      answer: err.message || "Could not reach the assistant. Check that the API is running.",
      citation_url: "",
      footer: "",
      type: "error",
    });
  } finally {
    setBusy(false);
    inputEl.focus();
  }
}

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    const data = await res.json();
    if (data.index_ready) {
      statusEl.textContent = "Index ready";
      statusEl.className = "status-pill ok";
    } else {
      statusEl.textContent = "Index degraded";
      statusEl.className = "status-pill bad";
      statusEl.title = "Run scripts/build_index.py --reset";
    }
  } catch {
    statusEl.textContent = "API offline";
    statusEl.className = "status-pill bad";
    statusEl.title = API_BASE
      ? `Cannot reach ${API_BASE}/api/health (check Railway port + CORS)`
      : "Set VITE_API_BASE_URL on Vercel and redeploy";
  }
}

function renderFundList(schemes) {
  if (!schemeListEl) return;
  schemeListEl.innerHTML = schemes
    .map((s) => {
      const name = escapeHtml(s.scheme_name);
      const url = escapeHtml(s.source_url);
      return `<li>
        <a class="fund-item fund-item--link" href="${url}" target="_blank" rel="noopener noreferrer">${name}</a>
      </li>`;
    })
    .join("");
}

async function loadSchemes() {
  const fallback = [
    { scheme_name: "HDFC Silver ETF FoF Direct Growth", source_url: "https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth" },
    { scheme_name: "HDFC Mid Cap Fund Direct Growth", source_url: "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth" },
    { scheme_name: "HDFC Equity Fund Direct Growth", source_url: "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth" },
    { scheme_name: "HDFC Gold ETF Fund of Fund Direct Plan Growth", source_url: "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth" },
    { scheme_name: "HDFC NIFTY 50 Index Fund Direct Growth", source_url: "https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth" },
  ];
  try {
    const res = await fetch(`${API_BASE}/api/schemes`);
    if (!res.ok) {
      renderFundList(fallback);
      return;
    }
    const data = await res.json();
    renderFundList(data.schemes?.length ? data.schemes : fallback);
  } catch {
    renderFundList(fallback);
  }
}

function wireChips() {
  $$("[data-chip]").forEach((el) => {
    el.addEventListener("click", () => {
      const q = el.getAttribute("data-chip");
      if (!q) return;
      inputEl.value = q;
      updateSendEnabled();
      void sendMessage(q);
    });
  });
}

formEl?.addEventListener("submit", (e) => {
  e.preventDefault();
  void sendMessage(inputEl.value);
});

inputEl?.addEventListener("input", () => {
  updateSendEnabled();
  if (inputEl.value.trim()) hintEl.textContent = "";
});

inputEl?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) formEl.requestSubmit();
  }
});

$("#menu-toggle")?.addEventListener("click", () => {
  toggleMobileSidebar();
});

$("#sidebar-close")?.addEventListener("click", () => {
  closeMobileSidebar();
});

$("#sidebar-backdrop")?.addEventListener("click", () => {
  closeMobileSidebar();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeMobileSidebar();
});

window.addEventListener("resize", () => {
  if (window.matchMedia("(min-width: 768px)").matches) {
    closeMobileSidebar();
  }
});

function wireNewChatButtons() {
  const handler = (e) => {
    e.preventDefault();
    startNewChat();
  };
  $("#new-chat-btn")?.addEventListener("click", handler);
  $("#new-chat-btn-mobile")?.addEventListener("click", handler);
}

ensureSessions();
renderChatList();
renderMessagesFromChat();
checkHealth();
loadSchemes();
wireChips();
wireNewChatButtons();
updateSendEnabled();
