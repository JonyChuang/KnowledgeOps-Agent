// Recipient-owned notification center
state.notifications = {
  filter: "all",
  limit: 12,
  offset: 0,
  total: 0,
  unreadCount: 0,
};

function notificationsActor() {
  return currentActor();
}

function setNotificationsMessage(message = "", stateName = "") {
  const area = select("#notifications-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function setNotificationUnreadBadge(unreadCount = 0) {
  const badge = select("#notification-unread-badge");
  if (!badge) return;
  const count = Number(unreadCount) || 0;
  badge.textContent = count > 99 ? "99+" : String(count);
  badge.hidden = count === 0;
}

async function refreshNotificationUnreadCount(actor = notificationsActor()) {
  if (!actor) return;
  const page = await request("/notifications?limit=1&offset=0", {
    headers: { "X-Actor": actor },
  });
  state.notifications.unreadCount = page.unread_count ?? 0;
  setNotificationUnreadBadge(state.notifications.unreadCount);
}

function notificationTypePresentation(type) {
  const presentations = {
    ticket: ["工单协作", "is-ticket"],
    system: ["系统提醒", "is-system"],
  };
  return presentations[type] ?? ["动态提醒", "is-system"];
}

function renderNotificationsPagination() {
  const page = state.notifications;
  const totalPages = Math.max(1, Math.ceil(page.total / page.limit));
  const currentPage = Math.floor(page.offset / page.limit) + 1;
  const previous = select("#notifications-previous-page");
  const next = select("#notifications-next-page");
  const summary = select("#notifications-page-summary");
  if (previous) previous.disabled = page.offset === 0;
  if (next) next.disabled = page.offset + page.limit >= page.total;
  if (summary) summary.textContent = `第 ${currentPage} / ${totalPages} 页`;
}

function renderNotifications(items = []) {
  const container = select("#notifications-list");
  if (!container) return;
  container.replaceChildren();
  if (items.length === 0) {
    appendAgentElement(
      container,
      "p",
      state.notifications.filter === "unread" ? "没有未读通知。" : "暂时没有与你相关的通知。",
      "notifications-empty-state",
    );
    return;
  }

  items.forEach((notification) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "notification-list-item";
    if (!notification.is_read) item.classList.add("is-unread");

    const marker = document.createElement("span");
    marker.className = "notification-marker";
    marker.setAttribute("aria-hidden", "true");
    marker.textContent = notification.type === "ticket" ? "工" : "!";

    const body = document.createElement("div");
    const heading = document.createElement("div");
    appendAgentElement(heading, "strong", notification.title);
    const [typeLabel, typeClass] = notificationTypePresentation(notification.type);
    appendAgentElement(heading, "span", typeLabel, `notification-type ${typeClass}`);
    appendAgentElement(body, "p", notification.content);
    appendAgentElement(body, "time", formatDashboardDate(notification.created_at));
    body.prepend(heading);

    if (!notification.is_read) {
      const unread = document.createElement("span");
      unread.className = "notification-unread-dot";
      unread.setAttribute("aria-label", "未读");
      item.append(marker, body, unread);
    } else {
      item.append(marker, body);
    }
    item.addEventListener("click", () => openNotification(notification));
    container.append(item);
  });
}

async function openNotification(notification) {
  try {
    if (!notification.is_read) {
      await request(`/notifications/${encodeURIComponent(notification.id)}/read`, {
        method: "POST",
        headers: { "X-Actor": notificationsActor() },
      });
    }
    await refreshNotificationUnreadCount();
    if (notification.entity_type === "ticket") {
      await openTicketFromNotification(notification);
      return;
    }
    activateView(notification.target_view || "documents");
    setNotificationsMessage("已打开关联资料页面。", "is-success");
    if (notification.target_view === "documents") {
      select("#document-index-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (error) {
    setNotificationsMessage(error.message, "is-error");
  }
}

async function openTicketFromNotification(notification) {
  const isServiceDeskTarget = notification.target_view === "service-desk";
  if (isServiceDeskTarget) {
    const actorInput = select("#service-desk-actor");
    if (actorInput) actorInput.value = notificationsActor();
    state.serviceDesk.selectedTicketId = notification.entity_id;
    activateView("service-desk");
    await loadServiceDeskTickets({ preserveSelection: true });
    await loadServiceDeskTicketPreview(notification.entity_id);
  } else {
    const actorInput = select("#tickets-actor");
    if (actorInput) actorInput.value = notificationsActor();
    state.ticketWorkspace.selectedTicketId = notification.entity_id;
    activateView("tickets");
    await loadTickets({ preserveSelection: true });
    await loadTicketPreview(notification.entity_id);
  }
}

async function loadNotifications({ resetOffset = false } = {}) {
  const page = state.notifications;
  if (resetOffset) page.offset = 0;
  const parameters = new URLSearchParams({
    unread_only: String(page.filter === "unread"),
    limit: String(page.limit),
    offset: String(page.offset),
  });
  try {
    setNotificationsMessage("正在加载通知...", "is-pending");
    const result = await request(`/notifications?${parameters.toString()}`, {
      headers: { "X-Actor": notificationsActor() },
    });
    page.total = result.total;
    page.unreadCount = result.unread_count;
    setNotificationUnreadBadge(page.unreadCount);
    const summary = select("#notifications-result-summary");
    const count = select("#notifications-result-count");
    if (summary) summary.textContent = `共 ${result.total} 条${page.filter === "unread" ? "未读" : ""}通知，${page.unreadCount} 条未读。`;
    if (count) count.textContent = String(result.total);
    renderNotifications(result.items);
    renderNotificationsPagination();
    setNotificationsMessage();
  } catch (error) {
    renderNotifications([]);
    setNotificationsMessage(error.message, "is-error");
  }
}

async function markAllNotificationsRead() {
  try {
    const result = await request("/notifications/read-all", {
      method: "POST",
      headers: { "X-Actor": notificationsActor() },
    });
    await loadNotifications();
    setNotificationsMessage(`已将 ${result.updated_count} 条通知标为已读。`, "is-success");
  } catch (error) {
    setNotificationsMessage(error.message, "is-error");
  }
}

function bindNotifications() {
  select("#refresh-notifications")?.addEventListener("click", () => loadNotifications({ resetOffset: true }));
  select("#notifications-actor")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadNotifications({ resetOffset: true });
    }
  });
  selectAll("[data-notification-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      state.notifications.filter = button.dataset.notificationFilter ?? "all";
      selectAll("[data-notification-filter]").forEach((tab) => tab.classList.toggle("is-active", tab === button));
      loadNotifications({ resetOffset: true });
    });
  });
  select("#mark-all-notifications-read")?.addEventListener("click", markAllNotificationsRead);
  select("#notifications-previous-page")?.addEventListener("click", () => {
    state.notifications.offset = Math.max(0, state.notifications.offset - state.notifications.limit);
    loadNotifications();
  });
  select("#notifications-next-page")?.addEventListener("click", () => {
    state.notifications.offset += state.notifications.limit;
    loadNotifications();
  });
}
