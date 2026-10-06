const STORAGE_KEYS = {
  chatMode: "lwh_chat_mode",
};

const MODE_LABELS = {
  part2: "Speaking Part 2",
  part3: "Speaking Part 3",
  writing: "Writing",
};

const loginGate = document.getElementById("login-gate");
const googleBtn = document.getElementById("google-btn");
const loginError = document.getElementById("login-error");

const sidebar = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");
const sidebarTitle = document.getElementById("sidebar-title");
const conversationList = document.getElementById("conversation-list");
const openSidebarBtn = document.getElementById("open-sidebar-btn");
const closeSidebarBtn = document.getElementById("close-sidebar-btn");
const sidebarNewChatBtn = document.getElementById("sidebar-new-chat-btn");
const userAvatar = document.getElementById("user-avatar");
const userName = document.getElementById("user-name");
const logoutBtn = document.getElementById("logout-btn");

const chatWindow = document.getElementById("chat-window");
const emptyState = document.getElementById("empty-state");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const newChatBtn = document.getElementById("new-chat-btn");
const modeButtons = document.querySelectorAll(".mode-btn");

let chatMode = readStoredMode();
let conversationId = null;
let conversations = [];
// Bumped on every navigation, so a slow response for a chat the user already left is ignored.
let viewToken = 0;

function readStoredMode() {
  try {
    const mode = localStorage.getItem(STORAGE_KEYS.chatMode);
    return MODE_LABELS[mode] ? mode : "part2";
  } catch {
    return "part2";
  }
}

function storeMode(mode) {
  try {
    localStorage.setItem(STORAGE_KEYS.chatMode, mode);
  } catch {
    // Storage can be blocked (private mode); the mode then just isn't remembered.
  }
}

// ---------- API ----------

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && path !== "/me") {
    showLogin();
  }
  if (!res.ok) {
    throw new ApiError(res.status, `Server trả về lỗi ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

// ---------- Login ----------

let googleScriptPromise = null;

function loadGoogleScript() {
  if (!googleScriptPromise) {
    googleScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error("Không tải được Google Sign-In"));
      document.head.appendChild(script);
    });
  }
  return googleScriptPromise;
}

function showLoginError(text) {
  loginError.textContent = text;
  loginError.classList.toggle("hidden", !text);
}

async function showLogin() {
  loginGate.classList.remove("hidden");
  if (!GOOGLE_CLIENT_ID) {
    showLoginError("Chưa cấu hình GOOGLE_CLIENT_ID trong config.js.");
    return;
  }
  try {
    await loadGoogleScript();
  } catch (err) {
    showLoginError(err.message);
    return;
  }
  google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: onGoogleCredential,
  });
  googleBtn.innerHTML = "";
  google.accounts.id.renderButton(googleBtn, {
    theme: "filled_blue",
    size: "large",
    shape: "pill",
    text: "signin_with",
    locale: "vi",
  });
}

async function onGoogleCredential(response) {
  showLoginError("");
  try {
    const user = await api("/auth/google", { method: "POST", body: { credential: response.credential } });
    showApp(user);
  } catch (err) {
    showLoginError("Đăng nhập thất bại, thử lại nhé.");
    console.error(err);
  }
}

logoutBtn.addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
  } catch (err) {
    console.error(err);
  }
  if (window.google?.accounts?.id) {
    google.accounts.id.disableAutoSelect();
  }
  conversations = [];
  conversationId = null;
  renderConversationList();
  clearChatWindow();
  closeSidebar();
  showLogin();
});

function showApp(user) {
  loginGate.classList.add("hidden");
  userName.textContent = user.name;
  if (user.avatar_url) {
    userAvatar.src = user.avatar_url;
    userAvatar.classList.remove("hidden");
  } else {
    userAvatar.classList.add("hidden");
  }
  switchMode(chatMode);
  chatInput.focus();
}

// ---------- Sidebar ----------

function openSidebar() {
  sidebar.classList.add("open");
  sidebarBackdrop.classList.add("visible");
}

function closeSidebar() {
  sidebar.classList.remove("open");
  sidebarBackdrop.classList.remove("visible");
}

openSidebarBtn.addEventListener("click", openSidebar);
closeSidebarBtn.addEventListener("click", closeSidebar);
sidebarBackdrop.addEventListener("click", closeSidebar);

function renderConversationList() {
  sidebarTitle.textContent = `Lịch sử · ${MODE_LABELS[chatMode]}`;
  conversationList.innerHTML = "";

  if (conversations.length === 0) {
    const empty = document.createElement("p");
    empty.className = "conversation-empty";
    empty.textContent = "Chưa có cuộc trò chuyện nào.";
    conversationList.appendChild(empty);
    return;
  }

  conversations.forEach((c) => {
    const item = document.createElement("div");
    item.className = "conversation-item";
    item.classList.toggle("active", c.id === conversationId);

    const title = document.createElement("button");
    title.type = "button";
    title.className = "conversation-title";
    title.textContent = c.title;
    title.title = c.title;
    title.addEventListener("click", () => {
      openConversation(c.id);
      closeSidebar();
    });

    const rename = document.createElement("button");
    rename.type = "button";
    rename.className = "icon-btn conversation-action";
    rename.textContent = "✎";
    rename.setAttribute("aria-label", "Đổi tên");
    rename.addEventListener("click", () => renameConversation(c));

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "icon-btn conversation-action";
    remove.textContent = "🗑";
    remove.setAttribute("aria-label", "Xoá");
    remove.addEventListener("click", () => deleteConversation(c));

    item.append(title, rename, remove);
    conversationList.appendChild(item);
  });
}

async function refreshConversations() {
  const mode = chatMode;
  const list = await api(`/conversations?category=${encodeURIComponent(mode)}`);
  if (mode !== chatMode) return; // user switched mode meanwhile
  conversations = list;
  renderConversationList();
}

async function renameConversation(c) {
  const title = window.prompt("Đổi tên cuộc trò chuyện", c.title);
  if (!title || !title.trim() || title.trim() === c.title) return;
  try {
    await api(`/conversations/${c.id}`, { method: "PATCH", body: { title: title.trim() } });
    await refreshConversations();
  } catch (err) {
    console.error(err);
  }
}

async function deleteConversation(c) {
  if (!window.confirm(`Xoá cuộc trò chuyện "${c.title}"?`)) return;
  try {
    await api(`/conversations/${c.id}`, { method: "DELETE" });
    if (c.id === conversationId) startNewConversation();
    await refreshConversations();
  } catch (err) {
    console.error(err);
  }
}

// ---------- Modes and conversations ----------

function clearChatWindow() {
  chatWindow.innerHTML = "";
  chatWindow.appendChild(emptyState);
}

function startNewConversation() {
  viewToken += 1;
  conversationId = null;
  clearChatWindow();
  renderConversationList();
}

newChatBtn.addEventListener("click", () => {
  startNewConversation();
  chatInput.focus();
});

sidebarNewChatBtn.addEventListener("click", () => {
  startNewConversation();
  closeSidebar();
  chatInput.focus();
});

async function openConversation(id) {
  const token = ++viewToken;
  conversationId = id;
  renderConversationList();
  clearChatWindow();
  try {
    const messages = await api(`/conversations/${id}/messages`);
    if (token !== viewToken) return;
    messages.forEach((m) => {
      if (m.role === "user") appendUserMessage(m.content);
      else appendBotMessage(m.content, m.sources);
    });
  } catch (err) {
    if (token !== viewToken) return;
    appendErrorMessage("Không tải được cuộc trò chuyện này.");
    console.error(err);
  }
}

function renderActiveMode() {
  modeButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === chatMode);
  });
}

// Each mode has its own chat list; switching reopens that mode's most recent chat.
async function switchMode(mode) {
  chatMode = mode;
  storeMode(mode);
  renderActiveMode();
  startNewConversation();
  try {
    await refreshConversations();
    if (mode === chatMode && conversationId === null && conversations.length > 0) {
      await openConversation(conversations[0].id);
    }
  } catch (err) {
    console.error(err);
  }
}

modeButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.mode === chatMode) return;
    switchMode(btn.dataset.mode);
    chatInput.focus();
  });
});

// ---------- Input ----------

chatInput.addEventListener("input", () => {
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";
});

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing && e.keyCode !== 229) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

// ---------- Rendering ----------

function scrollToBottom() {
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function hideEmptyState() {
  if (emptyState.parentNode) {
    emptyState.remove();
  }
}

function appendUserMessage(text) {
  hideEmptyState();
  const row = document.createElement("div");
  row.className = "msg-row user";
  row.innerHTML = `<div class="msg-bubble"></div>`;
  row.querySelector(".msg-bubble").textContent = text;
  chatWindow.appendChild(row);
  scrollToBottom();
}

function appendTypingIndicator() {
  hideEmptyState();
  const row = document.createElement("div");
  row.className = "msg-row bot";
  row.id = "typing-row";
  row.innerHTML = `
    <img src="assets/logo.png" class="msg-avatar" alt="bot" />
    <div class="msg-bubble">
      <div class="typing-dots"><span></span><span></span><span></span></div>
    </div>
  `;
  chatWindow.appendChild(row);
  scrollToBottom();
}

function removeTypingIndicator() {
  const row = document.getElementById("typing-row");
  if (row) row.remove();
}

function appendBotMessage(answer, sources) {
  const row = document.createElement("div");
  row.className = "msg-row bot";

  const col = document.createElement("div");
  col.className = "msg-col";

  const avatar = document.createElement("img");
  avatar.src = "assets/logo.png";
  avatar.className = "msg-avatar";
  avatar.alt = "bot";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble markdown-body";
  const rawHtml = marked.parse(answer, { breaks: true });
  bubble.innerHTML = DOMPurify.sanitize(rawHtml);
  col.appendChild(bubble);

  if (sources && sources.length > 0) {
    const details = document.createElement("details");
    details.className = "sources";
    const summary = document.createElement("summary");
    summary.textContent = `${sources.length} nguồn tham khảo`;
    details.appendChild(summary);

    sources.forEach((s) => {
      const chip = document.createElement("div");
      chip.className = "source-chip";
      const label = `<b>[${s.rank}]</b> ${escapeHtml(s.source_file)} &gt; ${escapeHtml(s.section_title)} (score ${s.score.toFixed(2)})`;
      chip.innerHTML = s.doc_url
        ? `<a href="${escapeHtml(s.doc_url)}" target="_blank" rel="noopener noreferrer">${label}</a>`
        : label;
      details.appendChild(chip);
    });

    col.appendChild(details);
  }

  row.appendChild(avatar);
  row.appendChild(col);
  chatWindow.appendChild(row);
  scrollToBottom();
}

function appendErrorMessage(text) {
  const row = document.createElement("div");
  row.className = "msg-row error";
  row.innerHTML = `<div class="msg-bubble"></div>`;
  row.querySelector(".msg-bubble").textContent = text;
  chatWindow.appendChild(row);
  scrollToBottom();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------- Sending ----------

function sendMessage(query) {
  const body = { query, category: chatMode };
  if (conversationId) {
    body.conversation_id = conversationId;
  }
  return api("/chat", { method: "POST", body });
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = chatInput.value.trim();
  if (!query) return;

  chatInput.value = "";
  chatInput.style.height = "auto";
  appendUserMessage(query);

  sendBtn.disabled = true;
  appendTypingIndicator();
  const token = viewToken;

  try {
    const data = await sendMessage(query);
    if (token !== viewToken) return; // user left this chat while waiting; it is saved anyway
    conversationId = data.conversation_id;

    removeTypingIndicator();
    appendBotMessage(data.answer, data.sources);
    refreshConversations().catch(console.error);
  } catch (err) {
    if (token !== viewToken) return;
    removeTypingIndicator();
    if (err.status === 429) {
      appendErrorMessage("Bạn đã dùng hết lượt hỏi hôm nay. Quay lại vào ngày mai nhé.");
    } else if (err.status !== 401) {
      appendErrorMessage("Xin lỗi, có lỗi xảy ra khi kết nối tới server. Thử lại nhé.");
    }
    console.error(err);
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
});

// ---------- Start ----------

async function init() {
  renderActiveMode();
  try {
    const user = await api("/me");
    showApp(user);
  } catch {
    showLogin();
  }
}

init();
