(() => {
  "use strict";

  const STORAGE_KEY = "peoplepilot.chat.v1";
  const SESSION_KEY = "peoplepilot.session.v1";
  const MAX_MESSAGE_LENGTH = 1000;

  const elements = {
    form: document.querySelector("#chat-form"),
    input: document.querySelector("#chat-input"),
    sendButton: document.querySelector("#send-button"),
    count: document.querySelector("#character-count"),
    chatArea: document.querySelector("#chat-area"),
    messages: document.querySelector("#messages"),
    welcome: document.querySelector("#welcome"),
    typing: document.querySelector("#typing-row"),
    newChat: document.querySelector("#new-chat-button"),
    mobileNewChat: document.querySelector("#mobile-new-chat"),
    headerStatusDot: document.querySelector("#header-status-dot"),
    headerStatusText: document.querySelector("#header-status-text"),
    sidebarStatusDot: document.querySelector("#sidebar-status-dot"),
    sidebarStatusText: document.querySelector("#sidebar-status-text"),
  };

  let isSending = false;
  let messages = loadMessages();
  let sessionId = loadSessionId();

  function loadMessages() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter((item) => item && ["user", "assistant"].includes(item.role) && typeof item.text === "string")
        .slice(-100);
    } catch {
      return [];
    }
  }

  function loadSessionId() {
    const stored = localStorage.getItem(SESSION_KEY);
    return stored && /^[A-Za-z0-9-]{8,64}$/.test(stored) ? stored : null;
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-100)));
    if (sessionId) localStorage.setItem(SESSION_KEY, sessionId);
  }

  function formatTime(timestamp) {
    const date = timestamp ? new Date(timestamp) : new Date();
    if (Number.isNaN(date.getTime())) return "";
    return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(date);
  }

  function appendInlineContent(parent, text) {
    const tokenPattern = /(\[Page\s+(\d+)\]|Pages?\s+(\d+(?:\s*,\s*\d+)*)|\*\*([^*]+)\*\*)/gi;
    let cursor = 0;
    let match;

    function appendSourceLink(pageNumber) {
      const source = document.createElement("a");
      source.className = "source-link";
      source.href = `/handbook#page=${pageNumber}`;
      source.target = "_blank";
      source.rel = "noopener";
      source.textContent = `Page ${pageNumber}`;
      source.setAttribute("aria-label", `Open employee handbook page ${pageNumber}`);
      parent.append(source);
    }

    while ((match = tokenPattern.exec(text)) !== null) {
      if (match.index > cursor) parent.append(document.createTextNode(text.slice(cursor, match.index)));

      if (match[2]) {
        appendSourceLink(match[2]);
      } else if (match[3]) {
        match[3].split(",").map((page) => page.trim()).forEach(appendSourceLink);
      } else if (match[4]) {
        const strong = document.createElement("strong");
        strong.textContent = match[4];
        parent.append(strong);
      }
      cursor = tokenPattern.lastIndex;
    }

    if (cursor < text.length) parent.append(document.createTextNode(text.slice(cursor)));
  }

  function renderAssistantText(container, text) {
    const lines = text.replace(/\r\n/g, "\n").split("\n");
    let list = null;

    for (const rawLine of lines) {
      const line = rawLine.trim();
      const listMatch = line.match(/^[-•*]\s+(.+)/);

      if (listMatch) {
        if (!list) {
          list = document.createElement("ul");
          container.append(list);
        }
        const item = document.createElement("li");
        appendInlineContent(item, listMatch[1]);
        list.append(item);
        continue;
      }

      list = null;
      if (!line) continue;
      const paragraph = document.createElement("p");
      appendInlineContent(paragraph, line);
      container.append(paragraph);
    }
  }

  function buildMessage(message) {
    const row = document.createElement("article");
    row.className = `message-row ${message.role}`;

    const avatar = document.createElement("div");
    avatar.className = `message-avatar ${message.role === "assistant" ? "assistant-mini" : "user-mini"}`;
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = message.role === "assistant" ? "P" : "You";

    const content = document.createElement("div");
    content.className = "message-content";
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    if (message.role === "assistant") renderAssistantText(bubble, message.text);
    else bubble.textContent = message.text;

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = `${message.role === "assistant" ? "PeoplePilot" : "You"} · ${formatTime(message.timestamp)}`;
    content.append(bubble, meta);

    if (message.role === "assistant") row.append(avatar, content);
    else row.append(content, avatar);
    return row;
  }

  function renderHistory() {
    elements.messages.replaceChildren();
    elements.welcome.hidden = messages.length > 0;
    for (const message of messages) elements.messages.append(buildMessage(message));
  }

  function addMessage(role, text) {
    const message = { role, text, timestamp: new Date().toISOString() };
    messages.push(message);
    elements.welcome.hidden = true;
    elements.messages.append(buildMessage(message));
    saveState();
    scrollToLatest();
  }

  function showError(message, originalQuestion) {
    const row = document.createElement("div");
    row.className = "message-row assistant transient-error";
    const avatar = document.createElement("div");
    avatar.className = "message-avatar assistant-mini";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "P";
    const card = document.createElement("div");
    card.className = "error-card";
    card.append(document.createTextNode(message));
    const retry = document.createElement("button");
    retry.className = "retry-button";
    retry.type = "button";
    retry.textContent = "Try again";
    retry.addEventListener("click", () => {
      row.remove();
      sendMessage(originalQuestion, false);
    });
    card.append(retry);
    row.append(avatar, card);
    elements.messages.append(row);
    scrollToLatest();
  }

  function scrollToLatest() {
    requestAnimationFrame(() => {
      elements.chatArea.scrollTo({ top: elements.chatArea.scrollHeight, behavior: "smooth" });
    });
  }

  function setSending(sending) {
    isSending = sending;
    elements.input.disabled = sending;
    elements.typing.hidden = !sending;
    updateComposer();
    if (sending) scrollToLatest();
  }

  function updateComposer() {
    const length = elements.input.value.length;
    elements.count.textContent = `${length} / ${MAX_MESSAGE_LENGTH}`;
    elements.count.classList.toggle("near-limit", length >= 900);
    elements.sendButton.disabled = isSending || !elements.input.value.trim();
    elements.input.style.height = "auto";
    elements.input.style.height = `${Math.min(elements.input.scrollHeight, 130)}px`;
  }

  async function sendMessage(rawMessage, appendUser = true) {
    const message = rawMessage.trim();
    if (!message || isSending || message.length > MAX_MESSAGE_LENGTH) return;

    document.querySelectorAll(".transient-error").forEach((node) => node.remove());
    if (appendUser) addMessage("user", message);
    elements.input.value = "";
    setSending(true);

    try {
      const payload = { message };
      if (sessionId) payload.session_id = sessionId;
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }

      if (!response.ok) throw new Error(data.detail || "The assistant could not answer right now.");
      if (typeof data.answer !== "string" || typeof data.session_id !== "string") {
        throw new Error("The assistant returned an unexpected response.");
      }

      sessionId = data.session_id;
      addMessage("assistant", data.answer);
    } catch (error) {
      const text = error instanceof Error ? error.message : "The assistant could not answer right now.";
      showError(text, message);
    } finally {
      setSending(false);
      elements.input.focus();
    }
  }

  function resetConversation() {
    if (messages.length && !window.confirm("Start a new conversation? Your current chat will be cleared from this browser.")) return;
    messages = [];
    sessionId = null;
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(SESSION_KEY);
    elements.messages.replaceChildren();
    elements.welcome.hidden = false;
    elements.input.value = "";
    updateComposer();
    elements.chatArea.scrollTo({ top: 0, behavior: "smooth" });
    elements.input.focus();
  }

  function setHealth(online) {
    const dots = [elements.headerStatusDot, elements.sidebarStatusDot];
    for (const dot of dots) {
      dot.classList.toggle("online", online);
      dot.classList.toggle("offline", !online);
    }
    elements.headerStatusText.textContent = online ? "Online and ready" : "Assistant unavailable";
    elements.sidebarStatusText.textContent = online ? "Assistant online" : "Assistant unavailable";
  }

  async function checkHealth() {
    try {
      const response = await fetch("/api/health", { cache: "no-store" });
      const data = await response.json();
      setHealth(response.ok && data.status === "ok");
    } catch {
      setHealth(false);
    }
  }

  elements.form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(elements.input.value);
  });

  elements.input.addEventListener("input", updateComposer);
  elements.input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      elements.form.requestSubmit();
    }
  });

  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => sendMessage(button.dataset.prompt || ""));
  });
  elements.newChat.addEventListener("click", resetConversation);
  elements.mobileNewChat.addEventListener("click", resetConversation);

  renderHistory();
  updateComposer();
  checkHealth();
  if (messages.length) scrollToLatest();
})();
