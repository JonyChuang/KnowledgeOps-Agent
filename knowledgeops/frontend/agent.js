// Agent conversation workspace
state.agentConversations = [];
state.activeAgentConversationId = null;
state.activeAgentConversationLoaded = false;

function setApiStatus(text) {
  selectAll(".api-status").forEach((status) => {
    status.textContent = text;
  });
}

function getActiveAgentConversation() {
  return state.agentConversations.find(
    (conversation) => conversation.id === state.activeAgentConversationId,
  );
}

function activeAgentActor() {
  return currentActor();
}

function conversationFromApi(conversation) {
  return {
    id: conversation.id,
    title: conversation.title || "新对话",
    knowledgeBaseId: conversation.knowledge_base_id ?? "",
    items: (conversation.messages ?? []).map((message) => {
      if (message.role === "user") {
        return { type: "user", text: message.content ?? "" };
      }
      return {
        type: "turn",
        actor: conversation.actor,
        messageId: message.id,
        turn: {
          thread_id: message.thread_id,
          status: message.status,
          answer: message.content,
          citations: message.citations ?? [],
          pending_action: message.pending_action,
          created_ticket_id: message.created_ticket_id,
          ticket_ids: message.ticket_ids ?? [],
          error: message.error,
        },
      };
    }),
  };
}

function upsertConversation(conversation) {
  const index = state.agentConversations.findIndex(
    (item) => item.id === conversation.id,
  );
  if (index >= 0) state.agentConversations[index] = conversation;
  else state.agentConversations.unshift(conversation);
}

async function loadAgentConversations({ preserveActive = true } = {}) {
  const actor = activeAgentActor();
  const page = await request("/agent/conversations", {
    headers: { "X-Actor": actor },
  });
  state.agentConversations = page.items.map((conversation) => ({
    id: conversation.id,
    title: conversation.title,
    lastPreview: conversation.last_message_preview,
    itemCount: conversation.message_count,
    items: [],
    loaded: false,
  }));
  if (
    !preserveActive ||
    !state.agentConversations.some(
      (conversation) => conversation.id === state.activeAgentConversationId,
    )
  ) {
    state.activeAgentConversationId = state.agentConversations[0]?.id ?? null;
  }
  renderConversationList();
  if (state.activeAgentConversationId) {
    await openAgentConversation(state.activeAgentConversationId);
  } else {
    state.activeAgentConversationLoaded = false;
    renderAgentMessages();
  }
}

async function openAgentConversation(conversationId) {
  const actor = activeAgentActor();
  const response = await request(
    `/agent/conversations/${encodeURIComponent(conversationId)}`,
    { headers: { "X-Actor": actor } },
  );
  const conversation = conversationFromApi(response);
  conversation.loaded = true;
  upsertConversation(conversation);
  state.activeAgentConversationId = conversation.id;
  state.activeAgentConversationLoaded = true;
  if (conversation.knowledgeBaseId) {
    const knowledgeBase = select("#agent-knowledge-base");
    if (knowledgeBase) knowledgeBase.value = conversation.knowledgeBaseId;
  }
  renderConversationList();
  renderAgentMessages();
}

async function openAgentForActor(actor, conversationId = null) {
  const actorInput = select("#agent-actor");
  if (actorInput) actorInput.value = actor;
  activateView("agent");
  await loadAgentConversations({ preserveActive: false });
  if (conversationId) await openAgentConversation(conversationId);
}

function shortenConversationText(text, maxLength = 28) {
  const normalized = String(text ?? "").replace(/\s+/g, " ").trim();
  return normalized.length > maxLength
    ? `${normalized.slice(0, maxLength)}...`
    : normalized || "等待输入消息";
}

function updateConversationTitle(conversation) {
  const firstMessage = conversation.items.find((item) => item.type === "user");
  if (firstMessage) {
    conversation.title = shortenConversationText(firstMessage.text, 18);
  }
}

function renderConversationList() {
  const list = select("#conversation-list");
  const count = select("#conversation-count");
  if (!list) return;

  if (count) count.textContent = String(state.agentConversations.length);
  list.replaceChildren();

  if (state.agentConversations.length === 0) {
    appendAgentElement(list, "p", "还没有对话", "conversation-empty");
    return;
  }

  state.agentConversations.forEach((conversation) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "conversation-item";
    item.classList.toggle(
      "is-active",
      conversation.id === state.activeAgentConversationId,
    );

    appendAgentElement(item, "strong", conversation.title);
    const lastItem = conversation.items[conversation.items.length - 1];
    appendAgentElement(
      item,
      "span",
      conversation.lastPreview || lastItem?.type === "user"
        ? conversation.lastPreview || shortenConversationText(lastItem.text)
        : lastItem?.type === "turn"
          ? "Agent 已回复"
          : "等待输入消息",
    );

    item.addEventListener("click", () => {
      openAgentConversation(conversation.id).catch((error) => {
        showAgentMessage(error.message);
      });
    });
    list.append(item);
  });
}

function createAgentWelcome() {
  const welcome = document.createElement("div");
  welcome.className = "agent-welcome";
  appendAgentElement(welcome, "div", "K", "agent-welcome-mark");
  appendAgentElement(welcome, "h2", "有什么可以帮你？");
  appendAgentElement(
    welcome,
    "p",
    "可以查询知识库、查看工单，或协助创建需要确认的工单。",
  );

  const suggestions = document.createElement("div");
  suggestions.className = "suggestion-list";
  suggestions.setAttribute("aria-label", "示例问题");
  [
    ["总结工程规范", "帮我总结知识库中的工程规范"],
    ["查看未关闭工单", "查看当前未关闭的工单"],
    ["创建 VPN 工单", "帮我创建一个 VPN 无法连接的工单"],
    ["获取排查建议", "根据知识库给我排查建议"],
  ].forEach(([label, message]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", () => {
      const input = select("#agent-message");
      if (!input) return;
      input.value = message;
      select("#agent-form")?.requestSubmit();
    });
    suggestions.append(button);
  });

  welcome.append(suggestions);
  return welcome;
}

function createChatMessage(role, content) {
  const message = document.createElement("article");
  message.className = `chat-message is-${role}`;

  const avatar = document.createElement("div");
  avatar.className = "chat-avatar";
  avatar.textContent = role === "user" ? "我" : "K";

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.textContent = content;

  message.append(avatar, bubble);
  return message;
}

function agentStatusPresentation(status) {
  const presentations = {
    completed: ["已完成", ""],
    confirmation_required: ["等待确认", "is-pending"],
    cancelled: ["已取消", "is-error"],
    failed: ["处理失败", "is-error"],
  };
  return presentations[status] ?? [status, ""];
}

function createAgentTurnElement(turn, actor, messageId = null) {
  const message = document.createElement("article");
  message.className = "chat-message is-agent";

  const avatar = document.createElement("div");
  avatar.className = "chat-avatar";
  avatar.textContent = "K";

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  const [statusLabel, statusClass] = agentStatusPresentation(turn.status);
  const meta = document.createElement("div");
  meta.className = "agent-turn-meta";
  appendAgentElement(meta, "span", "KnowledgeOps Agent");
  appendAgentElement(meta, "span", statusLabel, `agent-status-chip ${statusClass}`);
  bubble.append(meta);

  if (turn.error) {
    appendAgentElement(bubble, "p", turn.error, "form-message");
  }

  if (turn.answer) {
    appendAgentElement(bubble, "p", turn.answer, "agent-answer");
  }

  if (turn.created_ticket_id) {
    appendAgentElement(
      bubble,
      "p",
      `已创建工单：${turn.created_ticket_id}`,
      "form-message is-success",
    );
  } else if ((turn.ticket_ids ?? []).length > 0) {
    appendAgentElement(
      bubble,
      "p",
      `关联工单：${turn.ticket_ids.join("、")}`,
      "form-message is-success",
    );
  }

  const citations = turn.citations ?? [];
  if (citations.length > 0) {
    const citationSection = document.createElement("section");
    citationSection.className = "agent-citations";
    appendAgentElement(citationSection, "h2", "引用来源");

    citations.forEach((citation) => {
      const item = document.createElement("article");
      item.className = "agent-citation";
      appendAgentElement(item, "strong", citation.source_name);
      appendAgentElement(item, "p", citation.text);
      citationSection.append(item);
    });
    bubble.append(citationSection);
  }

  if (turn.status === "confirmation_required") {
    const title = turn.pending_action?.arguments?.title ?? "未命名工单";
    appendAgentElement(
      bubble,
      "p",
      `即将创建工单：${title}`,
      "form-message is-pending",
    );

    const actions = document.createElement("div");
    actions.className = "agent-actions";
    actions.append(
      createAgentConfirmationButton("确认创建工单", true, turn.thread_id, actor),
      createAgentConfirmationButton("取消创建", false, turn.thread_id, actor),
    );
    bubble.append(actions);
  }

  if (messageId && turn.status === "completed" && (turn.answer || turn.error)) {
    const feedback = document.createElement("div");
    feedback.className = "agent-feedback-actions";
    appendAgentElement(feedback, "span", "这条回答有帮助吗？");
    [
      ["有帮助", "helpful"],
      ["无帮助", "unhelpful"],
      ["引用过期", "stale_citation"],
      ["答案不准确", "incorrect_answer"],
    ].forEach(([label, feedbackType]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "agent-feedback-button";
      button.textContent = label;
      button.addEventListener("click", () => submitAgentFeedback(messageId, feedbackType, button));
      feedback.append(button);
    });
    bubble.append(feedback);
  }

  message.append(avatar, bubble);
  return message;
}

function renderAgentMessages() {
  const container = select("#agent-result");
  if (!container) return;

  container.replaceChildren();
  const conversation = getActiveAgentConversation();

  if (!conversation || !conversation.loaded || conversation.items.length === 0) {
    container.append(createAgentWelcome());
    return;
  }

  conversation.items.forEach((item) => {
    if (item.type === "user") {
      container.append(createChatMessage("user", item.text));
    } else if (item.type === "turn") {
      container.append(createAgentTurnElement(item.turn, item.actor, item.messageId));
    } else if (item.type === "notice") {
      const notice = createChatMessage("agent", item.text);
      notice.querySelector(".chat-bubble")?.classList.add("is-notice");
      container.append(notice);
    }
  });

  container.scrollTop = container.scrollHeight;
}

function startPendingAgentConversation(message, actor, knowledgeBaseId) {
  let conversation = getActiveAgentConversation();
  if (conversation?.loaded) {
    conversation.items.push({ type: "user", text: message });
  } else {
    conversation = {
      id: `pending-${Date.now()}`,
      title: shortenConversationText(message, 18),
      knowledgeBaseId,
      lastPreview: shortenConversationText(message),
      itemCount: 1,
      items: [{ type: "user", text: message }],
      loaded: true,
      pending: true,
      localOnly: true,
    };
    state.agentConversations.unshift(conversation);
    state.activeAgentConversationId = conversation.id;
    state.activeAgentConversationLoaded = true;
  }

  updateConversationTitle(conversation);
  renderConversationList();
  renderAgentMessages();
  return conversation;
}

function showAgentMessage(message, stateName = "") {
  const container = select("#agent-result");
  if (!container) return;

  container.querySelector("#agent-processing")?.remove();
  if (stateName === "is-pending") {
    const processing = document.createElement("p");
    processing.id = "agent-processing";
    processing.className = "agent-processing";
    processing.textContent = message;
    container.append(processing);
    container.scrollTop = container.scrollHeight;
    return;
  }

  if (state.activeAgentConversationLoaded) {
    const conversation = getActiveAgentConversation();
    if (conversation) {
      conversation.items.push({ type: "notice", text: message });
      renderConversationList();
      renderAgentMessages();
      return;
    }
  }
  appendAgentElement(container, "p", message, "form-message");
}

function updateAgentConversationTurn(turn, actor) {
  const conversation = getActiveAgentConversation();
  if (!conversation) return;

  let turnIndex = -1;
  for (let index = conversation.items.length - 1; index >= 0; index -= 1) {
    const item = conversation.items[index];
    if (item.type === "turn" && item.turn.thread_id === turn.thread_id) {
      turnIndex = index;
      break;
    }
  }

  const item = { type: "turn", turn, actor };
  if (turnIndex >= 0) {
    conversation.items[turnIndex] = item;
  } else {
    conversation.items.push(item);
  }
}

function renderAgentResult(turn, actor) {
  const activeConversation = getActiveAgentConversation();
  if (turn.conversation_id) {
    if (activeConversation?.pending) {
      activeConversation.id = turn.conversation_id;
      activeConversation.pending = false;
      activeConversation.localOnly = false;
    }
    state.activeAgentConversationId = turn.conversation_id;
    state.activeAgentConversationLoaded = true;
  }
  updateAgentConversationTurn(turn, actor);
  const conversation = getActiveAgentConversation();
  if (conversation) {
    conversation.lastPreview = turn.answer || turn.error || "Agent 已回复";
    conversation.itemCount = conversation.items.length;
  }
  renderConversationList();
  renderAgentMessages();
  loadDashboard();
}

function createAgentConfirmationButton(label, approved, threadId, actor) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;

  button.addEventListener("click", async () => {
    selectAll("#agent-result .agent-actions button").forEach((item) => {
      item.disabled = true;
    });

    try {
      showAgentMessage("正在提交确认结果...", "is-pending");
      const result = await request(
        `/agent/turns/${encodeURIComponent(threadId)}/confirmation`,
        {
          method: "POST",
          headers: { "X-Actor": actor },
          body: JSON.stringify({ approved }),
        },
      );
      renderAgentResult(result, actor);
    } catch (error) {
      showAgentMessage(error.message);
    }
  });

  return button;
}

function bindAgentWorkspace() {
  select("#new-agent-chat")?.addEventListener("click", () => {
    state.activeAgentConversationId = null;
    state.activeAgentConversationLoaded = false;
    renderConversationList();
    renderAgentMessages();
    select("#agent-message")?.focus();
  });

  const messageInput = select("#agent-message");
  messageInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      select("#agent-form")?.requestSubmit();
    }
  });

  select("#agent-actor")?.addEventListener("change", () => {
    state.activeAgentConversationId = null;
    state.activeAgentConversationLoaded = false;
    loadAgentConversations({ preserveActive: false }).catch((error) => {
      showAgentMessage(error.message);
    });
  });
}

function bindAgentForm() {
  const form = select("#agent-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const actor = currentActor();
    const messageInput = select("#agent-message");
    const message = String(messageInput?.value ?? "").trim();
    const knowledgeBaseId = String(select("#agent-knowledge-base")?.value ?? "");

    if (!actor || !message) {
      showAgentMessage("请先登录并填写请求内容。");
      return;
    }

    if (messageInput) messageInput.value = "";

    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;

    const payload = { user_message: message };
    const activeConversation = getActiveAgentConversation();
    if (activeConversation?.loaded && !activeConversation.localOnly) {
      payload.conversation_id = activeConversation.id;
    }
    if (knowledgeBaseId) payload.knowledge_base_id = knowledgeBaseId;

    try {
      startPendingAgentConversation(message, actor, knowledgeBaseId);
      showAgentMessage("Agent 正在处理...", "is-pending");
      const result = await request("/agent/turns", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      renderAgentResult(result, actor);
      await loadAgentConversations();
      await openAgentConversation(result.conversation_id);
    } catch (error) {
      const pendingConversation = getActiveAgentConversation();
      if (pendingConversation?.pending) pendingConversation.pending = false;
      showAgentMessage(error.message);
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
}
