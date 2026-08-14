// Employee dashboard
state.dashboard = null;

function setDashboardMessage(message = "", stateName = "") {
  const area = select("#dashboard-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function dashboardActor() {
  return currentActor();
}

function ticketStatusPresentation(status) {
  const presentations = {
    open: ["待受理", "is-open"],
    in_progress: ["处理中", "is-progress"],
    awaiting_requester: ["待我补充", "is-awaiting"],
    resolved: ["已解决", "is-resolved"],
    closed: ["已关闭", "is-closed"],
  };
  return presentations[status] ?? [status, ""];
}

function formatDashboardDate(value) {
  if (!value) return "刚刚";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "最近更新";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function setDashboardText(selector, value) {
  const element = select(selector);
  if (element) element.textContent = String(value ?? 0);
}

function renderDashboardTickets(tickets, ticketSummary) {
  const container = select("#dashboard-ticket-list");
  if (!container) return;

  setDashboardText(
    "#dashboard-ticket-total",
    ticketSummary.open_count + ticketSummary.in_progress_count + ticketSummary.resolved_count + ticketSummary.closed_count,
  );
  container.replaceChildren();
  if (tickets.length === 0) {
    appendAgentElement(container, "p", "还没有工单。遇到问题时可以先询问 Agent。", "dashboard-empty-state");
    return;
  }

  tickets.forEach((ticket) => {
    const item = document.createElement("article");
    item.className = "dashboard-ticket-item";
    const main = document.createElement("div");
    const titleRow = document.createElement("div");
    titleRow.className = "dashboard-ticket-title-row";
    appendAgentElement(titleRow, "h3", ticket.title);
    const [statusLabel, statusClass] = ticketStatusPresentation(ticket.status);
    appendAgentElement(titleRow, "span", statusLabel, `dashboard-ticket-status ${statusClass}`);
    appendAgentElement(main, "p", `${ticket.priority === "urgent" ? "紧急" : ticket.priority === "high" ? "高" : ticket.priority === "low" ? "低" : "中"}优先级 · 更新于 ${formatDashboardDate(ticket.updated_at)}`);
    main.prepend(titleRow);
    item.append(main);
    container.append(item);
  });
}

function renderDashboardKnowledgeBases(knowledgeBases, totalCount) {
  const container = select("#dashboard-knowledge-list");
  if (!container) return;

  setDashboardText("#dashboard-knowledge-total", totalCount);
  container.replaceChildren();
  if (knowledgeBases.length === 0) {
    appendAgentElement(container, "p", "尚未创建知识库，可以先导入团队资料。", "dashboard-empty-state");
    return;
  }

  knowledgeBases.forEach((knowledgeBase) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "dashboard-knowledge-item";
    const badge = document.createElement("span");
    badge.className = "dashboard-knowledge-badge";
    badge.textContent = knowledgeBase.name.slice(0, 1).toUpperCase();
    const body = document.createElement("span");
    appendAgentElement(body, "strong", knowledgeBase.name);
    appendAgentElement(body, "small", knowledgeBase.description || knowledgeBase.department || "通用资料库");
    item.append(badge, body);
    item.addEventListener("click", () => activateView("knowledge"));
    container.append(item);
  });
}

function renderDashboardConversations(conversations = []) {
  const container = select("#dashboard-conversation-list");
  if (!container) return;
  setDashboardText("#dashboard-conversation-total", conversations.length);
  container.replaceChildren();

  if (conversations.length === 0) {
    appendAgentElement(container, "p", "还没有本次会话记录。", "dashboard-empty-state");
    return;
  }

  conversations.slice(0, 3).forEach((conversation) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "dashboard-conversation-item";
    appendAgentElement(item, "strong", conversation.title || "新对话");
    appendAgentElement(
      item,
      "span",
      conversation.last_message_preview || "Agent 已回复",
    );
    item.addEventListener("click", () => {
      openAgentForActor(
        state.dashboard?.actor ?? dashboardActor(),
        conversation.id,
      ).catch((error) => {
        setDashboardMessage(error.message);
      });
    });
    container.append(item);
  });
}

function renderDashboard(dashboard) {
  if (!dashboard) return;
  const tickets = dashboard.tickets;
  const indexing = dashboard.indexing;
  setDashboardText("#dashboard-actor-greeting", dashboard.actor);
  setDashboardText("#dashboard-open-count", tickets.open_count);
  setDashboardText("#dashboard-in-progress-count", tickets.in_progress_count);
  setDashboardText("#dashboard-pending-index-count", indexing.pending_count);
  setDashboardText("#dashboard-failed-index-count", indexing.failed_count);
  setDashboardText("#dashboard-knowledge-base-count", indexing.knowledge_base_count);
  setDashboardText("#dashboard-document-count", indexing.document_count);
  setDashboardText("#dashboard-ready-count", indexing.ready_count);

  const activeTickets = tickets.open_count + tickets.in_progress_count;
  const greeting = select("#dashboard-greeting");
  const detail = select("#dashboard-greeting-detail");
  const indexDetail = select("#dashboard-index-detail");
  if (greeting) {
    greeting.textContent = activeTickets
      ? `你有 ${activeTickets} 项工单正在等待跟进。`
      : "当前没有需要跟进的工单。";
  }
  if (detail) {
    detail.textContent = indexing.failed_count
      ? `有 ${indexing.failed_count} 份资料索引失败，需要检查。`
      : `已有 ${indexing.ready_count} 份资料可供 Agent 检索。`;
  }
  if (indexDetail) {
    indexDetail.textContent = indexing.pending_count
      ? `${indexing.pending_count} 份资料正在进入检索库`
      : "所有已提交资料均已处理";
  }

  renderDashboardTickets(dashboard.recent_tickets, tickets);
  renderDashboardKnowledgeBases(dashboard.knowledge_bases, indexing.knowledge_base_count);
  renderDashboardConversations(dashboard.recent_conversations ?? []);
}

async function loadDashboard() {
  const actor = dashboardActor();
  try {
    const dashboard = await request("/dashboard");
    state.dashboard = dashboard;
    renderDashboard(dashboard);
    setDashboardMessage();
  } catch (error) {
    setDashboardMessage(error.message);
  }
}

function bindDashboard() {
  select("#refresh-dashboard")?.addEventListener("click", loadDashboard);
  selectAll("[data-dashboard-view]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.dashboardView === "agent") {
        openAgentForActor(dashboardActor()).catch((error) => {
          setDashboardMessage(error.message);
        });
        return;
      }
      activateView(button.dataset.dashboardView);
    });
  });
  renderDashboardConversations(state.dashboard?.recent_conversations ?? []);
}
