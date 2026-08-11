const STORAGE_KEYS = {
  userName: "lwh_user_name",
  conversationId: "lwh_conversation_id",
  chatMode: "lwh_chat_mode",
};

const nameGate = document.getElementById("name-gate");
const nameForm = document.getElementById("name-form");
const nameInput = document.getElementById("name-input");

const chatWindow = document.getElementById("chat-window");
const emptyState = document.getElementById("empty-state");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const newChatBtn = document.getElementById("new-chat-btn");
const modeButtons = document.querySelectorAll(".mode-btn");

let conversationId = localStorage.getItem(STORAGE_KEYS.conversationId) || null;
let chatMode = localStorage.getItem(STORAGE_KEYS.chatMode) || "part2";

function getUserName() {
  return localStorage.getItem(STORAGE_KEYS.userName);
}

function initNameGate() {
  const existingName = getUserName();
  if (existingName) {
    nameGate.classList.add("hidden");
    return;
  }
  nameGate.classList.remove("hidden");
}

nameForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const name = nameInput.value.trim();
  if (!name) return;
  localStorage.setItem(STORAGE_KEYS.userName, name);
  nameGate.classList.add("hidden");
  chatInput.focus();
});

function startNewConversation() {
  conversationId = null;
  localStorage.removeItem(STORAGE_KEYS.conversationId);
  chatWindow.innerHTML = "";
  chatWindow.appendChild(emptyState);
}

newChatBtn.addEventListener("click", () => {
  startNewConversation();
});

function renderActiveMode() {
  modeButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === chatMode);
  });
}

modeButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.mode === chatMode) return;
    chatMode = btn.dataset.mode;
    localStorage.setItem(STORAGE_KEYS.chatMode, chatMode);
    renderActiveMode();
    startNewConversation();
    chatInput.focus();
  });
});

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

async function sendMessage(query) {
  const userName = getUserName();

  const body = {
    user_name: userName,
    query,
    category: chatMode,
  };
  if (conversationId) {
    body.conversation_id = conversationId;
  }

  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`Server trả về lỗi ${res.status}`);
  }

  return res.json();
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

  try {
    const data = await sendMessage(query);
    conversationId = data.conversation_id;
    localStorage.setItem(STORAGE_KEYS.conversationId, conversationId);

    removeTypingIndicator();
    appendBotMessage(data.answer, data.sources);
  } catch (err) {
    removeTypingIndicator();
    appendErrorMessage("Xin lỗi, có lỗi xảy ra khi kết nối tới server. Thử lại nhé.");
    console.error(err);
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
});

initNameGate();
renderActiveMode();
