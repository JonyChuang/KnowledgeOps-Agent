// Employee ticket workspace
state.ticketWorkspace = {
  status: "",
  query: "",
  limit: 10,
  offset: 0,
  total: 0,
  selectedTicketId: null,
};

function setTicketsMessage(message = "", stateName = "") {
  const area = select("#tickets-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function ticketsActor() {
  return currentActor();
}

function ticketPriorityLabel(priority) {
  const labels = {
    low: "低优先级",
    medium: "中优先级",
    high: "高优先级",
    urgent: "紧急",
  };
  return labels[priority] ?? priority;
}

function ticketImpactLabel(impact) {
  const labels = {
    single_user: "单个员工",
    team: "团队范围",
    department: "部门范围",
    company: "全公司范围",
  };
  return labels[impact] ?? impact ?? "未标记";
}

function ticketEscalationLabel(level) {
  const labels = {
    none: "未升级",
    team_lead: "已升级至组长",
    manager: "已升级至负责人",
  };
  return labels[level] ?? level ?? "未升级";
}

function ticketActivityPresentation(eventType) {
  const presentations = {
    "ticket.created": ["已提交服务请求", "is-created"],
    "ticket.accepted": ["已受理", "is-status"],
    "ticket.assigned": ["已转派", "is-assigned"],
    "ticket.priority_changed": ["优先级已调整", "is-priority"],
    "ticket.escalated": ["已升级", "is-escalated"],
    "requester.comment_added": ["已补充信息", "is-comment"],
    "ticket.status_changed": ["状态已更新", "is-status"],
    "ticket.reopened": ["已重新打开", "is-reopened"],
  };
  return presentations[eventType] ?? ["处理动态", "is-status"];
}

function ticketActivityText(activity) {
  if (activity.content) return activity.content;
  const fromStatus = activity.details?.from_status;
  const toStatus = activity.details?.to_status;
  if (fromStatus && toStatus) {
    return `状态从“${ticketStatusPresentation(fromStatus)[0]}”变更为“${ticketStatusPresentation(toStatus)[0]}”。`;
  }
  return "已记录一条工单动态。";
}

function renderTicketPreview(ticket) {
  const empty = select("#ticket-preview-empty");
  const preview = select("#ticket-preview");
  if (!empty || !preview) return;

  if (!ticket) {
    empty.hidden = false;
    preview.hidden = true;
    empty.classList.remove("is-hidden");
    preview.classList.add("is-hidden");
    preview.replaceChildren();
    return;
  }

  empty.hidden = true;
  preview.hidden = false;
  empty.classList.add("is-hidden");
  preview.classList.remove("is-hidden");
  preview.replaceChildren();

  const header = document.createElement("header");
  header.className = "ticket-preview-header";
  appendAgentElement(header, "span", `工单 #${ticket.id.slice(0, 8)}`, "ticket-preview-label");
  appendAgentElement(header, "h2", ticket.title);
  const [statusLabel, statusClass] = ticketStatusPresentation(ticket.status);
  appendAgentElement(
    header,
    "span",
    statusLabel,
    `dashboard-ticket-status ${statusClass} ticket-preview-status`,
  );

  const details = document.createElement("dl");
  details.className = "ticket-preview-details";
  const addDetail = (label, value, className = "") => {
    const row = document.createElement("div");
    appendAgentElement(row, "dt", label);
    appendAgentElement(row, "dd", value, className);
    details.append(row);
  };
  addDetail("优先级", ticketPriorityLabel(ticket.priority));
  addDetail("服务分类", ticket.category || "通用服务");
  addDetail("影响范围", ticketImpactLabel(ticket.impact));
  addDetail("处理人", ticket.assignee || "等待分派");
  addDetail("服务时限", ticket.sla_due_at ? formatDashboardDate(ticket.sla_due_at) : "暂未设置");
  addDetail("提交时间", formatDashboardDate(ticket.created_at));
  addDetail("最后更新", formatDashboardDate(ticket.updated_at));
  addDetail("问题描述", ticket.description, "ticket-preview-description");

  const actions = document.createElement("div");
  actions.className = "ticket-preview-actions";
  if (ticket.status === "resolved") {
    const confirmButton = document.createElement("button");
    confirmButton.type = "button";
    confirmButton.className = "primary-action";
    confirmButton.textContent = "确认解决";
    confirmButton.addEventListener("click", () => confirmTicketResolution(ticket.id));

    const reopenButton = document.createElement("button");
    reopenButton.type = "button";
    reopenButton.className = "secondary-action";
    reopenButton.textContent = "重新打开";
    reopenButton.addEventListener("click", () => reopenTicket(ticket.id));
    actions.append(confirmButton, reopenButton);
  }

  const timeline = document.createElement("section");
  timeline.className = "ticket-timeline";
  appendAgentElement(timeline, "h3", "处理时间线");
  const activities = ticket.activities ?? [];
  if (activities.length === 0) {
    appendAgentElement(timeline, "p", "暂时没有可展示的处理记录。", "ticket-timeline-empty");
  } else {
    const list = document.createElement("ol");
    activities.forEach((activity) => {
      const item = document.createElement("li");
      const [label, className] = ticketActivityPresentation(activity.event_type);
      appendAgentElement(item, "span", label, `ticket-activity-type ${className}`);
      appendAgentElement(item, "strong", activity.actor || "系统");
      appendAgentElement(item, "time", formatDashboardDate(activity.created_at));
      appendAgentElement(item, "p", ticketActivityText(activity));
      list.append(item);
    });
    timeline.append(list);
  }

  if (ticket.status !== "closed") {
    const commentForm = document.createElement("form");
    commentForm.className = "ticket-comment-form";
    const label = document.createElement("label");
    label.htmlFor = "ticket-comment-input";
    label.textContent = "补充信息";
    const input = document.createElement("textarea");
    input.id = "ticket-comment-input";
    input.name = "content";
    input.rows = 3;
    input.maxLength = 4000;
    input.placeholder = "补充错误现象、发生时间或已尝试的处理方式";
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "secondary-action";
    submit.textContent = "提交补充";
    label.append(input);
    commentForm.append(label, submit);
    commentForm.addEventListener("submit", (event) => {
      event.preventDefault();
      addTicketComment(ticket.id, input.value, submit);
    });
    timeline.append(commentForm);
  }

  preview.append(header, details, actions, timeline);
}

async function refreshSelectedTicket(ticket) {
  state.ticketWorkspace.selectedTicketId = ticket.id;
  renderTicketPreview(ticket);
  await loadTickets({ preserveSelection: true });
  loadDashboard();
  setTicketsMessage("工单详情已更新。", "is-success");
}

async function addTicketComment(ticketId, content, submitButton) {
  const normalized = String(content ?? "").trim();
  if (!normalized) {
    setTicketsMessage("请填写需要补充的信息。", "is-error");
    return;
  }
  const actor = ticketsActor();
  if (submitButton) submitButton.disabled = true;
  try {
    setTicketsMessage("正在提交补充信息...", "is-pending");
    const ticket = await request(`/tickets/${encodeURIComponent(ticketId)}/comments`, {
      method: "POST",
      headers: { "X-Actor": actor },
      body: JSON.stringify({ content: normalized }),
    });
    await refreshSelectedTicket(ticket);
  } catch (error) {
    setTicketsMessage(error.message, "is-error");
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
}

async function confirmTicketResolution(ticketId) {
  const actor = ticketsActor();
  try {
    setTicketsMessage("正在确认解决结果...", "is-pending");
    const ticket = await request(`/tickets/${encodeURIComponent(ticketId)}/confirm-resolution`, {
      method: "POST",
      headers: { "X-Actor": actor },
    });
    await refreshSelectedTicket(ticket);
  } catch (error) {
    setTicketsMessage(error.message, "is-error");
  }
}

async function reopenTicket(ticketId) {
  const reason = window.prompt("请说明仍需继续处理的原因：");
  if (reason === null) return;
  const normalized = reason.trim();
  if (normalized.length < 2) {
    setTicketsMessage("重新打开时请至少说明两个字的原因。", "is-error");
    return;
  }
  const actor = ticketsActor();
  try {
    setTicketsMessage("正在重新打开工单...", "is-pending");
    const ticket = await request(`/tickets/${encodeURIComponent(ticketId)}/reopen`, {
      method: "POST",
      headers: { "X-Actor": actor },
      body: JSON.stringify({ reason: normalized }),
    });
    await refreshSelectedTicket(ticket);
  } catch (error) {
    setTicketsMessage(error.message, "is-error");
  }
}

function renderTicketList(items) {
  const container = select("#tickets-list");
  if (!container) return;
  container.replaceChildren();

  if (items.length === 0) {
    appendAgentElement(
      container,
      "p",
      "没有找到匹配的工单。可以调整筛选条件，或通过 Agent 提交新的服务请求。",
      "tickets-empty-state",
    );
    return;
  }

  items.forEach((ticket) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "ticket-list-item";
    if (ticket.id === state.ticketWorkspace.selectedTicketId) {
      item.classList.add("is-selected");
    }

    const main = document.createElement("div");
    appendAgentElement(main, "h3", ticket.title);
    appendAgentElement(main, "p", ticket.description);

    const meta = document.createElement("div");
    meta.className = "ticket-list-meta";
    const [statusLabel, statusClass] = ticketStatusPresentation(ticket.status);
    appendAgentElement(meta, "span", statusLabel, `dashboard-ticket-status ${statusClass}`);
    appendAgentElement(meta, "span", `${ticketPriorityLabel(ticket.priority)} · ${formatDashboardDate(ticket.updated_at)}`);

    item.append(main, meta);
    item.addEventListener("click", () => loadTicketPreview(ticket.id));
    container.append(item);
  });
}

function renderTicketsPagination() {
  const workspace = state.ticketWorkspace;
  const currentPage = Math.floor(workspace.offset / workspace.limit) + 1;
  const totalPages = Math.max(1, Math.ceil(workspace.total / workspace.limit));
  const previous = select("#tickets-previous-page");
  const next = select("#tickets-next-page");
  const summary = select("#tickets-page-summary");

  if (previous) previous.disabled = workspace.offset === 0;
  if (next) next.disabled = workspace.offset + workspace.limit >= workspace.total;
  if (summary) summary.textContent = `第 ${currentPage} / ${totalPages} 页`;
}

function renderTicketsResultSummary(total) {
  const summary = select("#tickets-result-summary");
  const count = select("#tickets-result-count");
  if (summary) {
    summary.textContent = total
      ? `共找到 ${total} 张属于当前操作人的工单。`
      : "没有符合当前条件的工单。";
  }
  if (count) count.textContent = String(total);
}

async function loadTicketPreview(ticketId) {
  const actor = ticketsActor();
  try {
    const ticket = await request(`/tickets/${encodeURIComponent(ticketId)}`, {
      headers: { "X-Actor": actor },
    });
    state.ticketWorkspace.selectedTicketId = ticket.id;
    renderTicketPreview(ticket);
    renderTicketList(state.ticketWorkspace.items ?? []);
    setTicketsMessage();
  } catch (error) {
    state.ticketWorkspace.selectedTicketId = null;
    renderTicketPreview(null);
    setTicketsMessage(error.message);
  }
}

async function loadTickets({ resetOffset = false, preserveSelection = false } = {}) {
  const workspace = state.ticketWorkspace;
  const actor = ticketsActor();
  if (resetOffset) workspace.offset = 0;

  const parameters = new URLSearchParams({
    limit: String(workspace.limit),
    offset: String(workspace.offset),
  });
  if (workspace.status) parameters.set("status", workspace.status);
  if (workspace.query) parameters.set("query", workspace.query);

  try {
    setTicketsMessage("正在加载工单...", "is-pending");
    const page = await request(`/tickets?${parameters.toString()}`, {
      headers: { "X-Actor": actor },
    });
    workspace.items = page.items;
    workspace.total = page.total;
    renderTicketList(page.items);
    renderTicketsResultSummary(page.total);
    renderTicketsPagination();

    if (
      !preserveSelection
      && !page.items.some((ticket) => ticket.id === workspace.selectedTicketId)
    ) {
      workspace.selectedTicketId = null;
      renderTicketPreview(null);
    }
    setTicketsMessage();
  } catch (error) {
    workspace.items = [];
    workspace.total = 0;
    renderTicketList([]);
    renderTicketsResultSummary(0);
    renderTicketsPagination();
    renderTicketPreview(null);
    setTicketsMessage(error.message);
  }
}

function bindTickets() {
  selectAll('[data-view="tickets"]').forEach((button) => {
    button.addEventListener("click", () => loadTickets());
  });

  select("#refresh-tickets")?.addEventListener("click", () => loadTickets());
  select("#tickets-actor")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadTickets({ resetOffset: true });
    }
  });
  selectAll("[data-ticket-status]").forEach((button) => {
    button.addEventListener("click", () => {
      state.ticketWorkspace.status = button.dataset.ticketStatus ?? "";
      selectAll("[data-ticket-status]").forEach((tab) => {
        tab.classList.toggle("is-active", tab === button);
      });
      loadTickets({ resetOffset: true });
    });
  });
  select("#ticket-search-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    state.ticketWorkspace.query = String(
      select("#ticket-search-input")?.value ?? "",
    ).trim();
    loadTickets({ resetOffset: true });
  });
  select("#tickets-previous-page")?.addEventListener("click", () => {
    state.ticketWorkspace.offset = Math.max(
      0,
      state.ticketWorkspace.offset - state.ticketWorkspace.limit,
    );
    loadTickets();
  });
  select("#tickets-next-page")?.addEventListener("click", () => {
    state.ticketWorkspace.offset += state.ticketWorkspace.limit;
    loadTickets();
  });
}


// My handling queue
state.serviceDesk = {
  scope: "unassigned",
  query: "",
  limit: 10,
  offset: 0,
  total: 0,
  selectedTicketId: null,
  items: [],
};

function setServiceDeskMessage(message = "", stateName = "") {
  const area = select("#service-desk-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function serviceDeskActor() {
  return currentActor();
}

function serviceDeskHeaders() {
  return {};
}

function renderServiceDeskPreview(ticket) {
  const empty = select("#service-desk-preview-empty");
  const preview = select("#service-desk-preview");
  if (!empty || !preview) return;
  if (!ticket) {
    empty.hidden = false;
    preview.hidden = true;
    preview.replaceChildren();
    return;
  }

  empty.hidden = true;
  preview.hidden = false;
  preview.replaceChildren();

  const header = document.createElement("header");
  header.className = "ticket-preview-header";
  appendAgentElement(header, "span", `工单 #${ticket.id.slice(0, 8)} · 申请人 ${ticket.requester}`, "ticket-preview-label");
  appendAgentElement(header, "h2", ticket.title);
  const [statusLabel, statusClass] = ticketStatusPresentation(ticket.status);
  appendAgentElement(header, "span", statusLabel, `dashboard-ticket-status ${statusClass} ticket-preview-status`);

  const details = document.createElement("dl");
  details.className = "ticket-preview-details";
  const addDetail = (label, value, className = "") => {
    const row = document.createElement("div");
    appendAgentElement(row, "dt", label);
    appendAgentElement(row, "dd", value, className);
    details.append(row);
  };
  addDetail("优先级", ticketPriorityLabel(ticket.priority));
  addDetail("服务分类", ticket.category || "通用服务");
  addDetail("影响范围", ticketImpactLabel(ticket.impact));
  addDetail("当前处理人", ticket.assignee || "尚未领取");
  addDetail("服务时限", ticket.sla_due_at ? formatDashboardDate(ticket.sla_due_at) : "暂未设置");
  addDetail("升级状态", ticketEscalationLabel(ticket.escalation_level));
  addDetail("问题描述", ticket.description, "ticket-preview-description");

  const actions = document.createElement("div");
  actions.className = "ticket-preview-actions";
  if (ticket.status === "open" && !ticket.assignee) {
    const accept = document.createElement("button");
    accept.type = "button";
    accept.className = "primary-action";
    accept.textContent = "领取并开始处理";
    accept.addEventListener("click", () => runServiceDeskAction(ticket.id, "accept"));
    actions.append(accept);
  }
  if (!["resolved", "closed"].includes(ticket.status)) {
    const assign = document.createElement("button");
    assign.type = "button";
    assign.className = "secondary-action";
    assign.textContent = "转派";
    assign.addEventListener("click", () => assignServiceDeskTicket(ticket.id));
    actions.append(assign);
  }
  if (ticket.status === "in_progress" && ticket.assignee === serviceDeskActor()) {
    const requestInformation = document.createElement("button");
    requestInformation.type = "button";
    requestInformation.className = "secondary-action";
    requestInformation.textContent = "请求补充";
    requestInformation.addEventListener("click", () => runServiceDeskAction(
      ticket.id,
      "request-information",
      "请说明需要申请人补充的信息：",
    ));
    const resolve = document.createElement("button");
    resolve.type = "button";
    resolve.className = "primary-action";
    resolve.textContent = "标记已解决";
    resolve.addEventListener("click", () => runServiceDeskAction(
      ticket.id,
      "resolve",
      "请填写处理结果或解决方案：",
    ));
    const priority = document.createElement("button");
    priority.type = "button";
    priority.className = "secondary-action";
    priority.textContent = "调整优先级";
    priority.addEventListener("click", () => updateServiceDeskPriority(ticket.id));
    const escalate = document.createElement("button");
    escalate.type = "button";
    escalate.className = "secondary-action";
    escalate.textContent = "升级处理";
    escalate.addEventListener("click", () => escalateServiceDeskTicket(ticket.id));
    actions.append(requestInformation, resolve, priority, escalate);
  }

  const timeline = document.createElement("section");
  timeline.className = "ticket-timeline";
  appendAgentElement(timeline, "h3", "处理时间线");
  const activities = ticket.activities ?? [];
  if (!activities.length) {
    appendAgentElement(timeline, "p", "暂时没有可展示的处理记录。", "ticket-timeline-empty");
  } else {
    const list = document.createElement("ol");
    activities.forEach((activity) => {
      const item = document.createElement("li");
      const [label, className] = ticketActivityPresentation(activity.event_type);
      appendAgentElement(item, "span", label, `ticket-activity-type ${className}`);
      appendAgentElement(item, "strong", activity.actor || "系统");
      appendAgentElement(item, "time", formatDashboardDate(activity.created_at));
      appendAgentElement(item, "p", ticketActivityText(activity));
      list.append(item);
    });
    timeline.append(list);
  }
  preview.append(header, details, actions, timeline);
}

function renderServiceDeskList(items) {
  const container = select("#service-desk-list");
  if (!container) return;
  container.replaceChildren();
  if (!items.length) {
    appendAgentElement(container, "p", "当前队列没有符合条件的工单。", "tickets-empty-state");
    return;
  }
  items.forEach((ticket) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "ticket-list-item";
    if (ticket.id === state.serviceDesk.selectedTicketId) item.classList.add("is-selected");
    const main = document.createElement("div");
    appendAgentElement(main, "h3", ticket.title);
    appendAgentElement(main, "p", `${ticket.requester} · ${ticket.description}`);
    const meta = document.createElement("div");
    meta.className = "ticket-list-meta";
    const [statusLabel, statusClass] = ticketStatusPresentation(ticket.status);
    appendAgentElement(meta, "span", statusLabel, `dashboard-ticket-status ${statusClass}`);
    appendAgentElement(meta, "span", ticket.assignee ? `处理人：${ticket.assignee}` : "待领取");
    item.append(main, meta);
    item.addEventListener("click", () => loadServiceDeskPreview(ticket.id));
    container.append(item);
  });
}

function renderServiceDeskPagination() {
  const desk = state.serviceDesk;
  const currentPage = Math.floor(desk.offset / desk.limit) + 1;
  const totalPages = Math.max(1, Math.ceil(desk.total / desk.limit));
  const previous = select("#service-desk-previous-page");
  const next = select("#service-desk-next-page");
  if (previous) previous.disabled = desk.offset === 0;
  if (next) next.disabled = desk.offset + desk.limit >= desk.total;
  const summary = select("#service-desk-page-summary");
  if (summary) summary.textContent = `第 ${currentPage} / ${totalPages} 页`;
}

async function loadServiceDeskPreview(ticketId) {
  try {
    const ticket = await request(`/service-desk/tickets/${encodeURIComponent(ticketId)}`, {
      headers: serviceDeskHeaders(),
    });
    state.serviceDesk.selectedTicketId = ticket.id;
    renderServiceDeskPreview(ticket);
    renderServiceDeskList(state.serviceDesk.items);
    setServiceDeskMessage();
  } catch (error) {
    setServiceDeskMessage(error.message, "is-error");
  }
}

async function loadServiceDeskTickets({ resetOffset = false, preserveSelection = false } = {}) {
  const desk = state.serviceDesk;
  if (resetOffset) desk.offset = 0;
  const parameters = new URLSearchParams({
    scope: desk.scope,
    limit: String(desk.limit),
    offset: String(desk.offset),
  });
  if (desk.query) parameters.set("query", desk.query);
  try {
    setServiceDeskMessage("正在加载待处理工单...", "is-pending");
    const page = await request(`/service-desk/tickets?${parameters.toString()}`, {
      headers: serviceDeskHeaders(),
    });
    desk.items = page.items;
    desk.total = page.total;
    renderServiceDeskList(page.items);
    const summary = select("#service-desk-result-summary");
    const count = select("#service-desk-result-count");
    if (summary) summary.textContent = page.total ? `共找到 ${page.total} 张待处理工单。` : "当前没有符合条件的工单。";
    if (count) count.textContent = String(page.total);
    renderServiceDeskPagination();
    if (!preserveSelection && !page.items.some((ticket) => ticket.id === desk.selectedTicketId)) {
      desk.selectedTicketId = null;
      renderServiceDeskPreview(null);
    }
    setServiceDeskMessage();
  } catch (error) {
    desk.items = [];
    desk.total = 0;
    renderServiceDeskList([]);
    renderServiceDeskPreview(null);
    renderServiceDeskPagination();
    setServiceDeskMessage(error.message, "is-error");
  }
}

async function refreshServiceDeskTicket(ticket) {
  state.serviceDesk.selectedTicketId = ticket.id;
  renderServiceDeskPreview(ticket);
  await loadServiceDeskTickets({ preserveSelection: true });
  loadDashboard();
  setServiceDeskMessage("工单处理记录已更新。", "is-success");
}

async function runServiceDeskAction(ticketId, action, promptText = "") {
  let reason = "";
  if (promptText) {
    const input = window.prompt(promptText);
    if (input === null) return;
    reason = input.trim();
    if (reason.length < 2) {
      setServiceDeskMessage("请至少填写两个字的处理说明。", "is-error");
      return;
    }
  }
  try {
    setServiceDeskMessage("正在更新工单...", "is-pending");
    const ticket = await request(`/service-desk/tickets/${encodeURIComponent(ticketId)}/${action}`, {
      method: "POST",
      headers: serviceDeskHeaders(),
      body: promptText ? JSON.stringify({ reason }) : undefined,
    });
    await refreshServiceDeskTicket(ticket);
  } catch (error) {
    setServiceDeskMessage(error.message, "is-error");
  }
}

async function assignServiceDeskTicket(ticketId) {
  const assignee = window.prompt("请输入要转派给的服务人员：");
  if (assignee === null) return;
  const normalized = assignee.trim();
  if (normalized.length < 2) {
    setServiceDeskMessage("处理人名称至少需要两个字。", "is-error");
    return;
  }
  try {
    setServiceDeskMessage("正在转派工单...", "is-pending");
    const ticket = await request(`/service-desk/tickets/${encodeURIComponent(ticketId)}/assign`, {
      method: "POST",
      headers: serviceDeskHeaders(),
      body: JSON.stringify({ assignee: normalized }),
    });
    await refreshServiceDeskTicket(ticket);
  } catch (error) {
    setServiceDeskMessage(error.message, "is-error");
  }
}

async function updateServiceDeskPriority(ticketId) {
  const priority = window.prompt("请输入新优先级：low、medium、high 或 urgent", "high");
  if (priority === null) return;
  const normalizedPriority = priority.trim().toLowerCase();
  if (!["low", "medium", "high", "urgent"].includes(normalizedPriority)) {
    setServiceDeskMessage("优先级必须是 low、medium、high 或 urgent。", "is-error");
    return;
  }
  const reason = window.prompt("请说明调整优先级的原因：");
  if (reason === null) return;
  if (reason.trim().length < 2) {
    setServiceDeskMessage("请至少填写两个字的调整原因。", "is-error");
    return;
  }
  try {
    setServiceDeskMessage("正在调整优先级...", "is-pending");
    const ticket = await request(`/service-desk/tickets/${encodeURIComponent(ticketId)}/priority`, {
      method: "POST",
      headers: serviceDeskHeaders(),
      body: JSON.stringify({ priority: normalizedPriority, reason: reason.trim() }),
    });
    await refreshServiceDeskTicket(ticket);
  } catch (error) {
    setServiceDeskMessage(error.message, "is-error");
  }
}

async function escalateServiceDeskTicket(ticketId) {
  const level = window.prompt("请输入升级等级：team_lead 或 manager", "team_lead");
  if (level === null) return;
  const normalizedLevel = level.trim().toLowerCase();
  if (!["team_lead", "manager"].includes(normalizedLevel)) {
    setServiceDeskMessage("升级等级必须是 team_lead 或 manager。", "is-error");
    return;
  }
  const reason = window.prompt("请说明升级原因：");
  if (reason === null) return;
  if (reason.trim().length < 2) {
    setServiceDeskMessage("请至少填写两个字的升级原因。", "is-error");
    return;
  }
  try {
    setServiceDeskMessage("正在升级工单...", "is-pending");
    const ticket = await request(`/service-desk/tickets/${encodeURIComponent(ticketId)}/escalate`, {
      method: "POST",
      headers: serviceDeskHeaders(),
      body: JSON.stringify({ level: normalizedLevel, reason: reason.trim() }),
    });
    await refreshServiceDeskTicket(ticket);
  } catch (error) {
    setServiceDeskMessage(error.message, "is-error");
  }
}

function bindServiceDesk() {
  selectAll('[data-view="service-desk"]').forEach((button) => {
    button.addEventListener("click", () => loadServiceDeskTickets());
  });
  select("#refresh-service-desk")?.addEventListener("click", () => loadServiceDeskTickets({ resetOffset: true }));
  select("#service-desk-actor")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadServiceDeskTickets({ resetOffset: true });
    }
  });
  selectAll("[data-service-desk-scope]").forEach((button) => {
    button.addEventListener("click", () => {
      state.serviceDesk.scope = button.dataset.serviceDeskScope ?? "unassigned";
      selectAll("[data-service-desk-scope]").forEach((tab) => tab.classList.toggle("is-active", tab === button));
      loadServiceDeskTickets({ resetOffset: true });
    });
  });
  select("#service-desk-search-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    state.serviceDesk.query = String(select("#service-desk-search-input")?.value ?? "").trim();
    loadServiceDeskTickets({ resetOffset: true });
  });
  select("#service-desk-previous-page")?.addEventListener("click", () => {
    state.serviceDesk.offset = Math.max(0, state.serviceDesk.offset - state.serviceDesk.limit);
    loadServiceDeskTickets();
  });
  select("#service-desk-next-page")?.addEventListener("click", () => {
    state.serviceDesk.offset += state.serviceDesk.limit;
    loadServiceDeskTickets();
  });
}
