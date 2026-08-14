"use strict";

const API_BASE = "/api/v1";
const state = { knowledgeBases: [] };
state.auth = { user: null, mode: "login" };

const select = (selector) => document.querySelector(selector);
const selectAll = (selector) => [...document.querySelectorAll(selector)];

function setApiStatus(text) {
  const status = select("#api-status");
  if (status) status.textContent = text;
}

function findView(viewName) {
  return select(
    `[data-view-panel="${viewName}"],
     .view[data-view="${viewName}"],
     #${viewName}-view`,
  );
}

function activateView(viewName) {
  const target = findView(viewName);

  if (!target) {
    console.error(`找不到 ${viewName} 对应的页面区域。`);
    return;
  }

  selectAll(".nav-item[data-view]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === viewName);
  });

  selectAll(".view").forEach((view) => {
    view.classList.toggle("is-active", view === target);
  });
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers ?? {});
  headers.set("Accept", "application/json");

  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
  });

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/me") showAuthenticationDialog();
    throw new Error(formatRequestError(body, response.status));
  }

  return body;
}

function currentUser() {
  return state.auth.user;
}

function currentActor() {
  return currentUser()?.username ?? "";
}

function syncAuthenticatedUser() {
  const user = currentUser();
  const actor = user?.username ?? "";
  const displayName = user?.display_name || actor;
  const currentUserElement = select("#current-user");
  if (currentUserElement) {
    currentUserElement.textContent = user ? displayName : "";
  }
  const accountMenu = select("#account-menu");
  if (accountMenu) accountMenu.hidden = !user;
  const accountPopover = select("#account-menu-popover");
  if (accountPopover && !user) accountPopover.hidden = true;
  const appShell = select("#app-fragments");
  if (appShell) appShell.classList.toggle("is-authenticated", Boolean(user));
  const avatar = select("#account-avatar");
  if (avatar) avatar.textContent = (displayName || "K").slice(0, 1).toUpperCase();
  const accountName = select("#account-menu-name");
  if (accountName) accountName.textContent = displayName;
  const accountRole = select("#account-menu-role");
  if (accountRole) accountRole.textContent = { employee: "员工", service_desk: "服务台", admin: "管理员" }[user?.role] ?? "";
  selectAll("#dashboard-actor-name, #dashboard-actor-greeting, #agent-actor").forEach((element) => {
    element.textContent = displayName || "未登录";
  });
  selectAll("input[id$='-actor']").forEach((input) => {
    input.value = actor;
    input.readOnly = true;
    input.setAttribute("aria-readonly", "true");
  });
  const serviceDeskButton = select('.nav-item[data-view="service-desk"]');
  if (serviceDeskButton) serviceDeskButton.hidden = !user || !["service_desk", "admin"].includes(user.role);
  const userManagementButton = select("#user-management-nav");
  if (userManagementButton) userManagementButton.hidden = !user || user.role !== "admin";
  if (typeof renderProfile === "function") renderProfile();
}

function setAuthMessage(message = "", stateName = "") {
  const area = select("#auth-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function renderAuthenticationMode() {
  const register = state.auth.mode === "register";
  const displayNameField = select("#auth-display-name-field");
  const displayNameInput = select("#auth-display-name");
  if (displayNameField) displayNameField.hidden = !register;
  if (displayNameInput) displayNameInput.required = register;
  const title = select(".auth-heading h1");
  if (title) title.textContent = "KnowledgeOps";
  const description = select("#auth-description");
  if (description) description.textContent = register ? "创建企业知识库与工单协同账号" : "企业知识库与工单协同平台";
  const submit = select("#auth-submit");
  if (submit) submit.textContent = register ? "注册" : "登录";
  selectAll(".auth-tab").forEach((tab) => {
    const active = tab.id === (register ? "auth-register-tab" : "auth-login-tab");
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  const password = select("#auth-password");
  if (password) password.autocomplete = register ? "new-password" : "current-password";
}

function showAuthenticationDialog() {
  const dialog = select("#auth-dialog");
  if (!dialog || dialog.open) return;
  renderAuthenticationMode();
  dialog.showModal();
  select("#auth-username")?.focus();
}

function closeAuthenticationDialog() {
  const dialog = select("#auth-dialog");
  if (dialog?.open) dialog.close();
}

async function refreshAuthenticatedWorkspace() {
  syncAuthenticatedUser();
  await Promise.allSettled([
    loadDashboard(),
    loadKnowledgeBases(),
    loadAgentConversations({ preserveActive: false }),
    loadTickets({ preserveSelection: false }),
    loadNotifications(),
    loadPersonalLibrary(),
    currentUser()?.role === "admin" ? loadUserManagement() : Promise.resolve(),
  ]);
}

function setUserManagementMessage(message = "", stateName = "") {
  const area = select("#user-management-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function renderUserManagement(users = []) {
  const list = select("#user-management-list");
  if (!list) return;
  const count = select("#user-management-count");
  if (count) count.textContent = String(users.length);
  list.replaceChildren();
  users.forEach((user) => {
    const row = document.createElement("article");
    row.className = "user-management-row";
    const details = document.createElement("div");
    appendAgentElement(details, "strong", user.display_name);
    appendAgentElement(details, "p", `${user.username} · ${user.is_active ? "启用" : "已停用"}`);
    const role = document.createElement("select");
    role.className = "user-role-control";
    role.setAttribute("aria-label", `${user.display_name} 的角色`);
    [
      ["employee", "员工"],
      ["service_desk", "服务台"],
      ["admin", "管理员"],
    ].forEach(([value, label]) => {
      const option = new Option(label, value, false, user.role === value);
      role.add(option);
    });
    role.addEventListener("change", async () => {
      role.disabled = true;
      try {
        await request(`/auth/users/${encodeURIComponent(user.id)}/role`, {
          method: "PATCH",
          body: JSON.stringify({ role: role.value }),
        });
        setUserManagementMessage("角色已更新。", "is-success");
        await loadUserManagement();
      } catch (error) {
        setUserManagementMessage(error.message, "is-error");
        role.value = user.role;
      } finally {
        role.disabled = false;
      }
    });
    row.append(details, role);
    list.append(row);
  });
}

async function loadUserManagement() {
  if (currentUser()?.role !== "admin") return;
  try {
    const users = await request("/auth/users");
    renderUserManagement(users);
    setUserManagementMessage();
  } catch (error) {
    setUserManagementMessage(error.message, "is-error");
  }
}

function bindAuthentication() {
  if (state.auth.bound) return;
  state.auth.bound = true;
  selectAll(".auth-tab").forEach((tab) => tab.addEventListener("click", () => {
    state.auth.mode = tab.id === "auth-register-tab" ? "register" : "login";
    setAuthMessage();
    renderAuthenticationMode();
  }));
  select("#auth-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = String(select("#auth-username")?.value ?? "").trim();
    const password = String(select("#auth-password")?.value ?? "");
    const displayName = String(select("#auth-display-name")?.value ?? "").trim();
    const registering = state.auth.mode === "register";
    if (!username || !password || (registering && !displayName)) {
      setAuthMessage("请完成必填信息。", "is-error");
      return;
    }
    const submit = select("#auth-submit");
    if (submit) submit.disabled = true;
    try {
      const body = registering ? { username, password, display_name: displayName } : { username, password };
      const result = await request(registering ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      });
      state.auth.user = result.user;
      closeAuthenticationDialog();
      await refreshAuthenticatedWorkspace();
    } catch (error) {
      setAuthMessage(error.message, "is-error");
    } finally {
      if (submit) submit.disabled = false;
    }
  });
  select("#logout-button")?.addEventListener("click", async () => {
    try {
      await request("/auth/logout", { method: "POST" });
    } catch (_) {
      // The current session may already have expired; clear local UI state either way.
    }
    state.auth.user = null;
    state.agentConversations = [];
    state.activeAgentConversationId = null;
    activateView("dashboard");
    syncAuthenticatedUser();
    setAuthMessage();
    state.auth.mode = "login";
    showAuthenticationDialog();
  });
  select("#auth-dialog")?.addEventListener("cancel", (event) => event.preventDefault());
  const accountTrigger = select("#account-menu-trigger");
  const accountPopover = select("#account-menu-popover");
  accountTrigger?.addEventListener("click", () => {
    if (!accountPopover) return;
    const open = accountPopover.hidden;
    accountPopover.hidden = !open;
    accountTrigger.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (event) => {
    const accountMenu = select("#account-menu");
    if (!accountMenu || accountMenu.contains(event.target)) return;
    if (accountPopover) accountPopover.hidden = true;
    accountTrigger?.setAttribute("aria-expanded", "false");
  });
  select("#refresh-users")?.addEventListener("click", loadUserManagement);
  select("#user-management-nav")?.addEventListener("click", loadUserManagement);
}

function userRoleLabel(role) {
  return { employee: "员工", service_desk: "服务台人员", admin: "管理员" }[role] ?? "-";
}

function renderProfile() {
  const user = currentUser();
  const displayName = user?.display_name || user?.username || "K";
  const setText = (selector, value) => {
    const element = select(selector);
    if (element) element.textContent = value;
  };
  const createdAt = user?.created_at ? new Date(user.created_at) : null;
  const createdLabel = createdAt && !Number.isNaN(createdAt.getTime())
    ? new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long", day: "numeric" }).format(createdAt)
    : "-";
  const nameInput = select("#profile-display-name");
  if (nameInput) nameInput.value = user?.display_name ?? "";
  setText("#profile-avatar", displayName.slice(0, 1).toUpperCase());
  setText("#profile-account-summary", user?.username ?? "-");
  setText("#profile-username", user?.username ?? "-");
  setText("#profile-role", userRoleLabel(user?.role));
  setText("#profile-created-at", createdLabel);
}

function setProfileMessage(message = "", stateName = "") {
  const area = select("#profile-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function bindProfile() {
  select("#open-profile-button")?.addEventListener("click", () => {
    const popover = select("#account-menu-popover");
    if (popover) popover.hidden = true;
    select("#account-menu-trigger")?.setAttribute("aria-expanded", "false");
    renderProfile();
    activateView("profile");
  });
  select("#profile-display-name-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const displayName = String(select("#profile-display-name")?.value ?? "").trim();
    if (!displayName) return setProfileMessage("请输入昵称。", "is-error");
    try {
      state.auth.user = await request("/auth/me", { method: "PATCH", body: JSON.stringify({ display_name: displayName }) });
      syncAuthenticatedUser();
      setProfileMessage("昵称已更新。", "is-success");
    } catch (error) {
      setProfileMessage(error.message, "is-error");
    }
  });
  const dialog = select("#change-password-dialog");
  const form = select("#change-password-form");
  const setPasswordMessage = (message = "", stateName = "") => {
    const area = select("#change-password-message");
    if (area) { area.className = `form-message ${stateName}`; area.textContent = message; }
  };
  select("#open-change-password-dialog")?.addEventListener("click", () => { form?.reset(); setPasswordMessage(); dialog?.showModal(); });
  select("#close-change-password-dialog")?.addEventListener("click", () => dialog?.close());
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const currentPassword = String(select("#current-password")?.value ?? "");
    const newPassword = String(select("#new-password")?.value ?? "");
    const confirmation = String(select("#confirm-new-password")?.value ?? "");
    if (newPassword !== confirmation) return setPasswordMessage("两次输入的新密码不一致。", "is-error");
    try {
      await request("/auth/me/password", { method: "POST", body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) });
      dialog?.close();
      setProfileMessage("密码已更新。", "is-success");
    } catch (error) {
      setPasswordMessage(error.message, "is-error");
    }
  });
}

async function initializeAuthentication() {
  try {
    const result = await request("/auth/me");
    state.auth.user = result.user;
    await refreshAuthenticatedWorkspace();
  } catch (_) {
    state.auth.user = null;
    syncAuthenticatedUser();
    showAuthenticationDialog();
  }
}

function formatRequestError(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const location = Array.isArray(item?.loc)
          ? item.loc.slice(1).join(".")
          : "";
        const message = item?.msg || "请求参数无效。";
        return location ? `${location}: ${message}` : message;
      })
      .join("；");
  }
  return `请求失败，状态码：${status}`;
}

function getKnowledgeBaseList() {
  let container = select("#knowledge-base-list");

  if (container) return container;

  const view = findView("knowledge");
  if (!view) return null;

  container = document.createElement("div");
  container.id = "knowledge-base-list";
  container.className = "resource-list";
  view.append(container);
  return container;
}

function renderKnowledgeBases() {
  const container = getKnowledgeBaseList();
  if (!container) return;

  container.replaceChildren();

  if (state.knowledgeBases.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "暂无知识库，请先创建一个。";
    container.append(empty);
    return;
  }

  const table = document.createElement("table");
  const header = document.createElement("thead");
  const headerRow = document.createElement("tr");

  ["名称", "部门", "描述"].forEach((label) => {
    const cell = document.createElement("th");
    cell.textContent = label;
    headerRow.append(cell);
  });

  header.append(headerRow);
  table.append(header);

  const body = document.createElement("tbody");

  state.knowledgeBases.forEach((knowledgeBase) => {
    const row = document.createElement("tr");

    [knowledgeBase.name, knowledgeBase.department, knowledgeBase.description]
      .map((value) => value || "—")
      .forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      });

    body.append(row);
  });

  table.append(body);
  container.append(table);
}

function updateKnowledgeBaseSelects() {
  const selectors = [
    "#document-knowledge-base",
    "#document-knowledge-base-id",
    "#agent-knowledge-base",
    "#agent-knowledge-base-id",
    "#graph-knowledge-base",
    "#create-ticket-knowledge-base",
  ];

  selectors.forEach((selector) => {
    const input = select(selector);
    if (!input) return;

    const currentValue = input.value;
    input.replaceChildren(new Option("请选择知识库", ""));

    state.knowledgeBases.forEach((knowledgeBase) => {
      input.append(
        new Option(
          knowledgeBase.name,
          knowledgeBase.id,
          false,
          String(knowledgeBase.id) === currentValue,
        ),
      );
    });
  });
}

async function loadKnowledgeBases() {
  state.knowledgeBases = await request("/knowledge-bases");
  renderKnowledgeBases();
  updateKnowledgeBaseSelects();
}

function showFormMessage(form, message = "") {
  let area = form.querySelector(".form-message");

  if (!area) {
    area = document.createElement("p");
    area.className = "form-message";
    form.append(area);
  }

  area.textContent = message;
}

function bindNavigation() {
  selectAll(".nav-item[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      activateView(button.dataset.view);
      if (button.dataset.view === "notifications") {
        loadNotifications({ resetOffset: true });
      }
    });
  });
}

function bindKnowledgeBaseDialog() {
  const dialog = select("#knowledge-base-dialog");
  const form = select("#knowledge-base-form");
  const openButton =
    select("#open-knowledge-base-dialog") ??
    selectAll("button").find(
      (button) => button.textContent.trim() === "新建知识库",
    );

  if (!dialog || !form || !openButton) return;

  openButton.addEventListener("click", () => dialog.showModal());

  selectAll("button")
    .filter(
      (button) =>
        dialog.contains(button) && button.textContent.trim() === "取消",
    )
    .forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        dialog.close();
      });
    });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showFormMessage(form);

    const data = new FormData(form);
    const name = String(data.get("name") ?? "").trim();

    if (!name) {
      showFormMessage(form, "请输入知识库名称。");
      return;
    }

    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;

    const payload = { name };
    const department = String(data.get("department") ?? "").trim();
    const description = String(data.get("description") ?? "").trim();

    if (department) payload.department = department;
    if (description) payload.description = description;

    try {
      await request("/knowledge-bases", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      form.reset();
      dialog.close();
      await loadKnowledgeBases();
    } catch (error) {
      showFormMessage(form, error.message);
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
}

function setDocumentIndexMessage(message, stateName = "") {
  const area = select("#document-index-message");
  if (!area) return;

  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

async function pollDocumentStatus(documentId, attempt = 0) {
  const document = await request(`/documents/${documentId}`);

  const isSuccessful = ["ready", "indexed"].includes(document.status);
  const isFailed = document.status === "failed";

  setDocumentIndexMessage(
    `索引状态：${document.status}`,
    isSuccessful ? "is-success" : isFailed ? "" : "is-pending",
  );

  if (isSuccessful || isFailed) {
    return;
  }

  if (attempt >= 30) {
    setDocumentIndexMessage(
      "索引任务仍在运行，可稍后点击顶部“刷新”再次查看。",
      "is-pending",
    );
    return;
  }

  window.setTimeout(() => {
    pollDocumentStatus(documentId, attempt + 1).catch((error) => {
      setDocumentIndexMessage(error.message);
    });
  }, 2000);
}

function bindDocumentIndexForm() {
  const form = select("#document-index-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setDocumentIndexMessage();

    const data = new FormData(form);
    const knowledgeBaseId = String(data.get("knowledge_base_id") ?? "");
    const actor = String(data.get("actor") ?? "").trim();
    const sourceName = String(data.get("source_name") ?? "").trim();
    const content = String(data.get("content") ?? "").trim();

    if (!knowledgeBaseId || !actor || !sourceName || !content) {
      setDocumentIndexMessage("请完整填写知识库、操作人、文件名和文档内容。");
      return;
    }

    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;

    try {
      setDocumentIndexMessage("正在上传文档。", "is-pending");

      const uploaded = await request(
        `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/documents`,
        {
          method: "POST",
          headers: { "X-Actor": actor },
          body: JSON.stringify({
            source_name: sourceName,
            content,
          }),
        },
      );

      const queued = await request(`/documents/${uploaded.id}/index`, {
        method: "POST",
        headers: { "X-Actor": actor },
      });

      setDocumentIndexMessage(
        `文档已上传，索引任务 ${queued.task_id} 已排队。`,
        "is-pending",
      );

      await pollDocumentStatus(uploaded.id);
    } catch (error) {
      setDocumentIndexMessage(error.message);
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
}

function setGraphSearchMessage(message, stateName = "") {
  const area = select("#graph-search-message");
  if (!area) return;

  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function renderGraphSearchResults(chunks) {
  const container = select("#graph-search-results");
  if (!container) return;

  container.replaceChildren();

  if (chunks.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "未找到与已识别实体关联的文档块。";
    container.append(empty);
    return;
  }

  chunks.forEach((chunk) => {
    const item = document.createElement("article");
    item.className = "graph-result";

    const title = document.createElement("h2");
    title.textContent = chunk.source_name;

    const meta = document.createElement("p");
    meta.className = "graph-result-meta";
    meta.textContent = `文档块 #${chunk.chunk_index + 1}`;

    const text = document.createElement("p");
    text.textContent = chunk.text;

    item.append(title, meta, text);
    container.append(item);
  });
}

function bindGraphSearchForm() {
  const form = select("#graph-search-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setGraphSearchMessage();

    const data = new FormData(form);
    const knowledgeBaseId = String(data.get("knowledge_base_id") ?? "");
    const query = String(data.get("query") ?? "").trim();
    const limit = Number(data.get("limit") ?? 5);

    if (!knowledgeBaseId || !query) {
      setGraphSearchMessage("请选择知识库并输入检索问题。");
      return;
    }

    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;

    try {
      setGraphSearchMessage("正在查询图谱。", "is-pending");

      const chunks = await request(
        `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/graph/search`,
        {
          method: "POST",
          body: JSON.stringify({ query, limit }),
        },
      );

      renderGraphSearchResults(chunks);
      setGraphSearchMessage(`找到 ${chunks.length} 个关联文档块。`, "is-success");
    } catch (error) {
      renderGraphSearchResults([]);
      setGraphSearchMessage(error.message);
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
}

function appendAgentElement(parent, tagName, text, className = "") {
  const element = document.createElement(tagName);
  element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
}

function showAgentMessage(message, stateName = "") {
  const container = select("#agent-result");
  if (!container) return;

  container.replaceChildren();
  appendAgentElement(container, "p", message, `form-message ${stateName}`);
}

function createAgentConfirmationButton(label, approved, threadId, actor) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;

  button.addEventListener("click", async () => {
    selectAll("#agent-result button").forEach((item) => {
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

function renderAgentResult(turn, actor) {
  const container = select("#agent-result");
  if (!container) return;

  container.replaceChildren();

  const labels = {
    completed: "已完成",
    confirmation_required: "等待确认",
    cancelled: "已取消",
    failed: "处理失败",
  };
  const stateName =
    turn.status === "completed"
      ? "is-success"
      : turn.status === "confirmation_required"
        ? "is-pending"
        : "";

  appendAgentElement(
    container,
    "p",
    `处理状态：${labels[turn.status] ?? turn.status}`,
    `form-message ${stateName}`,
  );

  if (turn.error) {
    appendAgentElement(container, "p", turn.error, "form-message");
  }

  if (turn.answer) {
    appendAgentElement(container, "p", turn.answer, "agent-answer");
  }

  if (turn.created_ticket_id) {
    appendAgentElement(
      container,
      "p",
      `已创建工单：${turn.created_ticket_id}`,
      "form-message is-success",
    );
  } else if ((turn.ticket_ids ?? []).length > 0) {
    appendAgentElement(
      container,
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

    container.append(citationSection);
  }

  if (turn.status === "confirmation_required") {
    const title = turn.pending_action?.arguments?.title ?? "未命名工单";
    appendAgentElement(
      container,
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
    container.append(actions);
  }
}

function bindAgentForm() {
  const form = select("#agent-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const actor = String(select("#agent-actor")?.value ?? "").trim();
    const message = String(select("#agent-message")?.value ?? "").trim();
    const knowledgeBaseId = String(
      select("#agent-knowledge-base")?.value ?? "",
    );

    if (!actor || !message) {
      showAgentMessage("请填写操作人和请求内容。");
      return;
    }

    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;

    const payload = { user_message: message };
    if (knowledgeBaseId) payload.knowledge_base_id = knowledgeBaseId;

    try {
      showAgentMessage("Agent 正在处理...", "is-pending");

      const result = await request("/agent/turns", {
        method: "POST",
        headers: { "X-Actor": actor },
        body: JSON.stringify(payload),
      });

      renderAgentResult(result, actor);
    } catch (error) {
      showAgentMessage(error.message);
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
}

async function checkApi() {
  if (window.location.protocol === "file:") {
    setApiStatus("API 等待容器服务");
    return;
  }

  setApiStatus("API 检查中");

  try {
    await request("/health");
    setApiStatus("API 已连接");
  } catch {
    setApiStatus("API 未连接");
  }
}

function initialize() {
  bindNavigation();
  const requestedView = new URLSearchParams(window.location.search).get("view");
  if (requestedView && findView(requestedView)) {
    activateView(requestedView);
  }
  bindKnowledgeBaseDialog();
  bindDocumentIndexForm();
  bindGraphSearchForm();
  bindAgentForm();
  bindAuthentication();

  select("#refresh-button")?.addEventListener("click", checkApi);

  checkApi();
  initializeAuthentication();
}

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

function initialize() {
  bindNavigation();
  const requestedView = new URLSearchParams(window.location.search).get("view");
  if (requestedView && findView(requestedView)) {
    activateView(requestedView);
  }
  bindKnowledgeBaseDialog();
  bindDocumentIndexForm();
  bindGraphSearchForm();
  bindAgentWorkspace();
  bindAgentForm();
  renderConversationList();
  renderAgentMessages();

  select("#refresh-button")?.addEventListener("click", checkApi);
  bindAuthentication();
  initializeAuthentication();
}

let frontendBootstrapped = false;

function bootstrapFrontend() {
  if (frontendBootstrapped) return;
  frontendBootstrapped = true;

  const setupSteps = [
    bindNavigation,
    bindKnowledgeBaseDialog,
    bindDocumentIndexForm,
    bindGraphSearchForm,
    bindAgentWorkspace,
    bindAgentForm,
    bindKnowledgeDetail,
    bindKnowledgeLocalFileImport,
    bindKnowledgeWebImport,
    bindDashboard,
    bindTickets,
    bindServiceDesk,
    bindEngagementFeatures,
    bindNotifications,
    bindCreateTicketForm,
    bindOperationalShortcuts,
    bindAuthentication,
    bindProfile,
  ];

  setupSteps.forEach((setup) => {
    try {
      setup();
    } catch (error) {
      console.error("Failed to initialize a frontend module.", error);
    }
  });

  const requestedView = new URLSearchParams(window.location.search).get("view");
  if (requestedView && findView(requestedView)) activateView(requestedView);
  renderConversationList();
  renderAgentMessages();
  select("#refresh-button")?.addEventListener("click", checkApi);
  checkApi();
  initializeAuthentication();
}
// Knowledge base catalog and document workspace
state.activeKnowledgeBaseId = null;
state.activeKnowledgeDocuments = [];
state.knowledgeDocumentCounts = new Map();

function getActiveKnowledgeBase() {
  return state.knowledgeBases.find(
    (knowledgeBase) => knowledgeBase.id === state.activeKnowledgeBaseId,
  );
}

function documentCountForKnowledgeBase(knowledgeBaseId) {
  return state.knowledgeDocumentCounts.get(knowledgeBaseId) ?? null;
}

function createKnowledgeCard(knowledgeBase) {
  const card = document.createElement("article");
  card.className = "knowledge-card";

  const openButton = document.createElement("button");
  openButton.type = "button";
  openButton.className = "knowledge-card-open";

  const topLine = document.createElement("div");
  topLine.className = "knowledge-card-topline";
  const illustration = document.createElement("div");
  illustration.className = "knowledge-card-illustration";
  illustration.setAttribute("aria-hidden", "true");
  illustration.append(document.createElement("span"), document.createElement("span"), document.createElement("span"));
  topLine.append(illustration);
  appendAgentElement(topLine, "span", "已启用", "knowledge-card-tag");

  const content = document.createElement("div");
  appendAgentElement(content, "h2", knowledgeBase.name);
  appendAgentElement(
    content,
    "p",
    knowledgeBase.description || knowledgeBase.department || "未设置资料说明",
    "knowledge-card-description",
  );

  const meta = document.createElement("div");
  meta.className = "knowledge-card-meta";
  const documentCount = documentCountForKnowledgeBase(knowledgeBase.id);
  appendAgentElement(
    meta,
    "span",
    documentCount === null ? "文档数待加载" : `${documentCount} 篇文档`,
  );
  appendAgentElement(meta, "strong", knowledgeBase.department || "通用");

  openButton.append(topLine, content, meta);
  openButton.addEventListener("click", () => {
    openKnowledgeBaseDetail(knowledgeBase.id).catch((error) => {
      setKnowledgeDocumentMessage(error.message);
    });
  });
  card.append(openButton);
  return card;
}

function renderKnowledgeBases() {
  const container = getKnowledgeBaseList();
  if (!container) return;

  container.className = "knowledge-card-grid";
  container.replaceChildren();

  if (state.knowledgeBases.length === 0) {
    const empty = document.createElement("article");
    empty.className = "knowledge-card-empty";
    appendAgentElement(empty, "p", "还没有知识库。新建一个知识库后，即可归类和检索资料。");
    container.append(empty);
    return;
  }

  state.knowledgeBases.forEach((knowledgeBase) => {
    container.append(createKnowledgeCard(knowledgeBase));
  });
}

function renderKnowledgeDocuments() {
  const container = select("#knowledge-document-list");
  const count = select("#knowledge-document-count");
  if (!container) return;

  const query = String(select("#knowledge-document-search-input")?.value ?? "")
    .trim()
    .toLocaleLowerCase();
  const documents = state.activeKnowledgeDocuments.filter((knowledgeDocument) => {
    return !query || String(knowledgeDocument.source_name ?? "").toLocaleLowerCase().includes(query);
  });

  if (count) count.textContent = String(state.activeKnowledgeDocuments.length);
  container.replaceChildren();

  if (documents.length === 0) {
    const empty = document.createElement("p");
    empty.className = "knowledge-document-empty";
    empty.textContent = query ? "没有匹配的文档。" : "这个知识库还没有文档。";
    container.append(empty);
    return;
  }

  documents.forEach((knowledgeDocument) => {
    const item = window.document.createElement("article");
    item.className = "knowledge-document-item";
    const info = document.createElement("div");
    appendAgentElement(info, "h2", knowledgeDocument.source_name || "未命名文档");
    appendAgentElement(
      info,
      "p",
      knowledgeDocument.status ? `索引状态：${knowledgeDocument.status}` : "等待索引",
    );

    const status = document.createElement("span");
    const isReady = ["ready", "indexed"].includes(knowledgeDocument.status);
    status.className = `document-status${isReady ? " is-ready" : knowledgeDocument.status === "failed" ? " is-failed" : ""}`;
    status.textContent = isReady ? "已就绪" : knowledgeDocument.status === "failed" ? "索引失败" : "处理中";
    item.append(info, status);
    container.append(item);
  });
}

function setKnowledgeDocumentMessage(message = "", stateName = "") {
  const area = select("#knowledge-document-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function showKnowledgeCatalog() {
  select("#knowledge-catalog")?.removeAttribute("hidden");
  select("#knowledge-detail")?.setAttribute("hidden", "");
  state.activeKnowledgeBaseId = null;
  state.activeKnowledgeDocuments = [];
  setKnowledgeDocumentMessage();
}

async function loadKnowledgeDocuments(knowledgeBaseId) {
  const documents = await request(
    `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/documents`,
  );
  state.activeKnowledgeDocuments = documents;
  state.knowledgeDocumentCounts.set(knowledgeBaseId, documents.length);
  renderKnowledgeDocuments();
  renderKnowledgeBases();
}

async function openKnowledgeBaseDetail(knowledgeBaseId) {
  const knowledgeBase = state.knowledgeBases.find(
    (item) => item.id === knowledgeBaseId,
  );
  if (!knowledgeBase) return;

  state.activeKnowledgeBaseId = knowledgeBaseId;
  select("#knowledge-catalog")?.setAttribute("hidden", "");
  select("#knowledge-detail")?.removeAttribute("hidden");
  const name = select("#knowledge-detail-name");
  const description = select("#knowledge-detail-description");
  const target = select("#knowledge-document-import-target");
  if (name) name.textContent = knowledgeBase.name;
  if (description) {
    description.textContent = knowledgeBase.description || knowledgeBase.department || "资料管理与检索范围";
  }
  if (target) target.textContent = `将内容添加到“${knowledgeBase.name}”`;
  select("#knowledge-document-search-input").value = "";
  setKnowledgeDocumentMessage("正在加载文档...", "is-pending");
  renderKnowledgeDocuments();

  try {
    await loadKnowledgeDocuments(knowledgeBaseId);
    setKnowledgeDocumentMessage();
  } catch (error) {
    state.activeKnowledgeDocuments = [];
    renderKnowledgeDocuments();
    setKnowledgeDocumentMessage(error.message);
    throw error;
  }
}

async function loadKnowledgeBases() {
  state.knowledgeBases = await request("/knowledge-bases");
  const counts = await Promise.all(
    state.knowledgeBases.map(async (knowledgeBase) => {
      try {
        const documents = await request(
          `/knowledge-bases/${encodeURIComponent(knowledgeBase.id)}/documents`,
        );
        return [knowledgeBase.id, documents.length];
      } catch {
        return [knowledgeBase.id, null];
      }
    }),
  );
  state.knowledgeDocumentCounts = new Map(counts);
  renderKnowledgeBases();
  updateKnowledgeBaseSelects();
}

function openKnowledgeDocumentImport() {
  if (!getActiveKnowledgeBase()) return;
  const dialog = select("#knowledge-document-import-dialog");
  if (!dialog) return;
  select("#knowledge-document-import-message").textContent = "";
  dialog.showModal();
  select("#knowledge-document-import-name")?.focus();
}

function bindKnowledgeDetail() {
  select("#back-to-knowledge-catalog")?.addEventListener("click", showKnowledgeCatalog);
  select("#open-document-import")?.addEventListener("click", openKnowledgeDocumentImport);
  select("#knowledge-document-dropzone")?.addEventListener("click", openKnowledgeDocumentImport);
  select("#knowledge-document-search-input")?.addEventListener("input", renderKnowledgeDocuments);

  const dialog = select("#knowledge-document-import-dialog");
  const form = select("#knowledge-document-import-form");
  select("#close-document-import-dialog")?.addEventListener("click", () => dialog?.close());
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const knowledgeBase = getActiveKnowledgeBase();
    if (!knowledgeBase) return;

    const actor = String(select("#knowledge-document-import-actor")?.value ?? "").trim();
    const sourceName = String(select("#knowledge-document-import-name")?.value ?? "").trim();
    const content = String(select("#knowledge-document-import-content")?.value ?? "").trim();
    const message = select("#knowledge-document-import-message");
    if (!actor || !sourceName || !content) {
      if (message) message.textContent = "请填写操作人、文档名称和文档内容。";
      return;
    }

    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    if (message) {
      message.className = "form-message is-pending";
      message.textContent = "正在添加文档...";
    }

    try {
      const uploaded = await request(
        `/knowledge-bases/${encodeURIComponent(knowledgeBase.id)}/documents`,
        {
          method: "POST",
          headers: { "X-Actor": actor },
          body: JSON.stringify({ source_name: sourceName, content }),
        },
      );
      const queued = await request(`/documents/${uploaded.id}/index`, {
        method: "POST",
        headers: { "X-Actor": actor },
      });

      form.reset();
      dialog?.close();
      setKnowledgeDocumentMessage(`文档已添加，索引任务 ${queued.task_id} 正在处理。`, "is-pending");
      await loadKnowledgeDocuments(knowledgeBase.id);
    } catch (error) {
      if (message) {
        message.className = "form-message";
        message.textContent = error.message;
      }
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
}

document.addEventListener("DOMContentLoaded", bindKnowledgeDetail);
// Local file and webpage document imports
function importActor() {
  return String(select("#knowledge-document-import-actor")?.value ?? "anonymous").trim() || "anonymous";
}

async function queueImportedDocument(document, actor) {
  return request(`/documents/${encodeURIComponent(document.id)}/index`, {
    method: "POST",
    headers: { "X-Actor": actor },
  });
}

async function refreshKnowledgeDocumentsAfterImport(knowledgeBaseId, taskId) {
  setKnowledgeDocumentMessage(`资料已导入，索引任务 ${taskId} 正在处理。`, "is-pending");
  await loadKnowledgeDocuments(knowledgeBaseId);
}

async function uploadKnowledgeLocalFile(file) {
  const knowledgeBase = getActiveKnowledgeBase();
  if (!knowledgeBase || !file) return;

  if (file.size > 10_000_000) {
    setKnowledgeDocumentMessage("文件超过 10 MB 的导入上限。");
    return;
  }

  const actor = importActor();
  setKnowledgeDocumentMessage(`正在导入 ${file.name}...`, "is-pending");
  try {
    const uploaded = await request(
      `/knowledge-bases/${encodeURIComponent(knowledgeBase.id)}/documents/upload?source_name=${encodeURIComponent(file.name)}`,
      {
        method: "POST",
        headers: {
          "Content-Type": file.type || "application/octet-stream",
          "X-Actor": actor,
        },
        body: file,
      },
    );
    const queued = await queueImportedDocument(uploaded, actor);
    await refreshKnowledgeDocumentsAfterImport(knowledgeBase.id, queued.task_id);
  } catch (error) {
    setKnowledgeDocumentMessage(error.message);
  }
}

function bindKnowledgeLocalFileImport() {
  const input = select("#knowledge-local-file-input");
  const openButton = select("#open-local-file-import");
  const dropzone = select("#knowledge-local-file-dropzone");
  if (!input || !dropzone) return;

  const chooseFile = () => input.click();
  openButton?.addEventListener("click", chooseFile);
  dropzone.addEventListener("click", chooseFile);
  input.addEventListener("change", async () => {
    const [file] = input.files ?? [];
    if (file) await uploadKnowledgeLocalFile(file);
    input.value = "";
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-dragging");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-dragging");
    });
  });
  dropzone.addEventListener("drop", async (event) => {
    const [file] = event.dataTransfer?.files ?? [];
    if (file) await uploadKnowledgeLocalFile(file);
  });
}

function bindKnowledgeWebImport() {
  const dialog = select("#knowledge-web-import-dialog");
  const form = select("#knowledge-web-import-form");
  select("#open-web-import")?.addEventListener("click", () => {
    select("#knowledge-web-import-message").textContent = "";
    dialog?.showModal();
    select("#knowledge-web-import-url")?.focus();
  });
  select("#close-web-import-dialog")?.addEventListener("click", () => dialog?.close());
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const knowledgeBase = getActiveKnowledgeBase();
    if (!knowledgeBase) return;

    const url = String(select("#knowledge-web-import-url")?.value ?? "").trim();
    const sourceName = String(select("#knowledge-web-import-name")?.value ?? "").trim();
    const actor = String(select("#knowledge-web-import-actor")?.value ?? "").trim();
    const message = select("#knowledge-web-import-message");
    if (!url || !actor) {
      if (message) message.textContent = "请填写网页地址和操作人。";
      return;
    }

    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    if (message) {
      message.className = "form-message is-pending";
      message.textContent = "正在获取网页内容...";
    }

    try {
      const payload = { url };
      if (sourceName) payload.source_name = sourceName;
      const uploaded = await request(
        `/knowledge-bases/${encodeURIComponent(knowledgeBase.id)}/documents/web-import`,
        {
          method: "POST",
          headers: { "X-Actor": actor },
          body: JSON.stringify(payload),
        },
      );
      const queued = await queueImportedDocument(uploaded, actor);
      form.reset();
      dialog?.close();
      await refreshKnowledgeDocumentsAfterImport(knowledgeBase.id, queued.task_id);
    } catch (error) {
      if (message) {
        message.className = "form-message";
        message.textContent = error.message;
      }
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bindKnowledgeLocalFileImport();
  bindKnowledgeWebImport();
});
// Document indexing and graph search workspaces
state.indexActivity = [];

function documentStatusLabel(status) {
  const labels = {
    uploaded: "等待索引",
    indexing: "处理中",
    ready: "已就绪",
    indexed: "已就绪",
    failed: "索引失败",
  };
  return labels[status] ?? status;
}

function renderIndexActivity() {
  const container = select("#document-list");
  const count = select("#index-activity-count");
  if (!container) return;

  if (count) count.textContent = String(state.indexActivity.length);
  container.replaceChildren();
  if (state.indexActivity.length === 0) {
    appendAgentElement(
      container,
      "p",
      "提交资料后，处理状态会显示在这里。",
      "index-activity-empty",
    );
    return;
  }

  state.indexActivity.forEach((activity) => {
    const item = document.createElement("article");
    item.className = "index-activity-item";
    const icon = document.createElement("div");
    icon.className = "index-file-icon";
    icon.textContent = activity.sourceName.slice(0, 1).toUpperCase();

    const body = document.createElement("div");
    appendAgentElement(body, "h3", activity.sourceName);
    appendAgentElement(
      body,
      "p",
      `${activity.knowledgeBaseName} · ${activity.taskId ? `任务 ${activity.taskId}` : "准备提交"}`,
    );

    const status = document.createElement("span");
    const ready = ["ready", "indexed"].includes(activity.status);
    status.className = `document-status${ready ? " is-ready" : activity.status === "failed" ? " is-failed" : ""}`;
    status.textContent = documentStatusLabel(activity.status);
    item.append(icon, body, status);
    container.append(item);
  });
}

function addIndexActivity(document, knowledgeBaseId, taskId = "") {
  const knowledgeBase = state.knowledgeBases.find((item) => item.id === knowledgeBaseId);
  const activity = {
    documentId: document.id,
    sourceName: document.source_name,
    knowledgeBaseName: knowledgeBase?.name ?? "知识库",
    taskId,
    status: document.status ?? "uploaded",
  };
  state.indexActivity = [activity, ...state.indexActivity.filter((item) => item.documentId !== document.id)];
  renderIndexActivity();
  return activity;
}

async function pollDocumentStatus(documentId, attempt = 0) {
  const document = await request(`/documents/${documentId}`);
  const activity = state.indexActivity.find((item) => item.documentId === documentId);
  if (activity) {
    activity.status = document.status;
    renderIndexActivity();
  }

  const isSuccessful = ["ready", "indexed"].includes(document.status);
  const isFailed = document.status === "failed";
  setDocumentIndexMessage(
    `索引状态：${documentStatusLabel(document.status)}`,
    isSuccessful ? "is-success" : isFailed ? "" : "is-pending",
  );

  if (isSuccessful || isFailed) return;
  if (attempt >= 30) {
    setDocumentIndexMessage("索引任务仍在处理，可稍后刷新查看最新状态。", "is-pending");
    return;
  }

  window.setTimeout(() => {
    pollDocumentStatus(documentId, attempt + 1).catch((error) => {
      setDocumentIndexMessage(error.message);
    });
  }, 2000);
}

function bindDocumentIndexForm() {
  const form = select("#document-index-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setDocumentIndexMessage();

    const data = new FormData(form);
    const knowledgeBaseId = String(data.get("knowledge_base_id") ?? "");
    const actor = String(data.get("actor") ?? "").trim();
    const sourceName = String(data.get("source_name") ?? "").trim();
    const content = String(data.get("content") ?? "").trim();
    if (!knowledgeBaseId || !actor || !sourceName || !content) {
      setDocumentIndexMessage("请选择知识库，并填写资料名称、操作人和内容。");
      return;
    }

    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;

    try {
      setDocumentIndexMessage("正在保存资料...", "is-pending");
      const uploaded = await request(
        `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/documents`,
        {
          method: "POST",
          headers: { "X-Actor": actor },
          body: JSON.stringify({ source_name: sourceName, content }),
        },
      );
      addIndexActivity(uploaded, knowledgeBaseId);

      const queued = await request(`/documents/${uploaded.id}/index`, {
        method: "POST",
        headers: { "X-Actor": actor },
      });
      addIndexActivity(uploaded, knowledgeBaseId, queued.task_id);
      setDocumentIndexMessage(`已提交索引任务 ${queued.task_id}。`, "is-pending");
      form.reset();
      await pollDocumentStatus(uploaded.id);
    } catch (error) {
      setDocumentIndexMessage(error.message);
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
}

function setGraphSearchMessage(message, stateName = "") {
  const area = select("#graph-search-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function renderGraphSearchResults(chunks) {
  const container = select("#graph-search-results");
  const count = select("#graph-result-count");
  const summary = select("#graph-result-summary");
  if (!container) return;

  if (count) count.textContent = String(chunks.length);
  if (summary) {
    summary.textContent = chunks.length
      ? `已找到 ${chunks.length} 条与问题中实体相关的文档证据。`
      : "没有发现可关联的实体文档块。";
  }
  container.replaceChildren();

  if (chunks.length === 0) {
    const empty = document.createElement("div");
    empty.className = "graph-empty-state";
    appendAgentElement(empty, "div", "⌘", "graph-empty-symbol");
    appendAgentElement(empty, "strong", "未找到关联证据");
    appendAgentElement(empty, "span", "尝试更换实体组合，或确认资料已完成图谱索引。");
    container.append(empty);
    return;
  }

  chunks.forEach((chunk) => {
    const item = document.createElement("article");
    item.className = "graph-result";
    const marker = document.createElement("div");
    marker.className = "graph-result-marker";
    marker.textContent = String(chunk.chunk_index + 1);
    const content = document.createElement("div");
    const titleRow = document.createElement("div");
    titleRow.className = "graph-result-title-row";
    appendAgentElement(titleRow, "h2", chunk.source_name);
    appendAgentElement(titleRow, "span", "关联文档块", "graph-result-chip");
    const meta = document.createElement("p");
    meta.className = "graph-result-meta";
    meta.textContent = `文档块 #${chunk.chunk_index + 1} · 由实体关系命中`;
    const text = document.createElement("p");
    text.className = "graph-result-text";
    text.textContent = chunk.text;
    content.append(titleRow, meta, text);
    item.append(marker, content);
    container.append(item);
  });
}

function bindGraphSearchForm() {
  const form = select("#graph-search-form");
  if (!form) return;

  selectAll("[data-graph-example]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = select("#graph-query");
      if (!input) return;
      input.value = button.dataset.graphExample;
      input.focus();
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setGraphSearchMessage();
    const data = new FormData(form);
    const knowledgeBaseId = String(data.get("knowledge_base_id") ?? "");
    const query = String(data.get("query") ?? "").trim();
    const limit = Number(data.get("limit") ?? 5);
    if (!knowledgeBaseId || !query) {
      setGraphSearchMessage("请选择知识库并输入问题或实体组合。");
      return;
    }

    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    try {
      setGraphSearchMessage("正在分析实体关系...", "is-pending");
      const chunks = await request(
        `/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/graph/search`,
        { method: "POST", body: JSON.stringify({ query, limit }) },
      );
      renderGraphSearchResults(chunks);
      setGraphSearchMessage(
        chunks.length ? `已返回 ${chunks.length} 条关联证据。` : "未找到关联证据。",
        chunks.length ? "is-success" : "",
      );
    } catch (error) {
      renderGraphSearchResults([]);
      setGraphSearchMessage(error.message);
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
}

function bindOperationalShortcuts() {
  select("#go-to-knowledge-import")?.addEventListener("click", () => activateView("knowledge"));
  renderIndexActivity();
}

document.addEventListener("DOMContentLoaded", bindOperationalShortcuts);

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
  setDashboardText("#dashboard-actor-name", dashboard.actor);
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

document.addEventListener("DOMContentLoaded", bindDashboard);

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

document.addEventListener("DOMContentLoaded", bindTickets);

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

document.addEventListener("DOMContentLoaded", bindServiceDesk);

// Cross-workspace search, favorites, visits, and Agent-answer feedback
state.personalLibrary = { favorites: [], recentVisits: [] };

function searchActor() {
  return currentActor();
}

function personalLibraryActor() {
  return currentActor();
}

function setGlobalSearchMessage(message = "", stateName = "") {
  const area = select("#global-search-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function setPersonalLibraryMessage(message = "", stateName = "") {
  const area = select("#personal-library-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function workspaceItemTypePresentation(type) {
  const presentations = {
    knowledge_base: ["知识库", "is-knowledge"],
    document: ["知识资料", "is-document"],
    graph: ["图谱实体", "is-graph"],
    ticket: ["我的工单", "is-ticket"],
    conversation: ["历史对话", "is-conversation"],
  };
  return presentations[type] ?? ["工作项", "is-document"];
}

function workspaceItemPayload(item) {
  return {
    entity_type: item.entity_type,
    entity_id: item.entity_id,
    title: item.title,
    subtitle: item.summary ?? item.subtitle ?? "",
    target_view: item.target_view,
    target_id: item.target_id ?? null,
    metadata_json: item.metadata_json ?? {},
  };
}

function renderGlobalSearchResults(items = []) {
  const container = select("#global-search-results");
  if (!container) return;
  container.replaceChildren();
  if (items.length === 0) {
    appendAgentElement(container, "p", "没有找到匹配的资料、图谱实体、对话或工单。", "global-search-empty");
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("article");
    row.className = "global-search-item";
    const main = document.createElement("button");
    main.type = "button";
    main.className = "global-search-open";
    const heading = document.createElement("div");
    appendAgentElement(heading, "strong", item.title);
    const [typeLabel, typeClass] = workspaceItemTypePresentation(item.entity_type);
    appendAgentElement(heading, "span", typeLabel, `workspace-item-type ${typeClass}`);
    appendAgentElement(main, "div", item.summary, "global-search-item-summary");
    main.prepend(heading);
    main.addEventListener("click", () => openWorkspaceItem(item, searchActor()));
    const favorite = document.createElement("button");
    favorite.type = "button";
    favorite.className = "workspace-favorite-button";
    favorite.textContent = "收藏";
    favorite.addEventListener("click", () => saveFavorite(item, searchActor(), favorite));
    row.append(main, favorite);
    container.append(row);
  });
}

async function runGlobalSearch() {
  const query = String(select("#global-search-input")?.value ?? "").trim();
  if (!query) return;
  try {
    setGlobalSearchMessage("正在搜索工作区...", "is-pending");
    const result = await request(`/search?${new URLSearchParams({ query, limit: "20" }).toString()}`, {
      headers: { "X-Actor": searchActor() },
    });
    const summary = select("#global-search-summary");
    const count = select("#global-search-count");
    if (summary) summary.textContent = `“${result.query}”共找到 ${result.total} 条结果。`;
    if (count) count.textContent = String(result.total);
    renderGlobalSearchResults(result.items);
    setGlobalSearchMessage();
  } catch (error) {
    renderGlobalSearchResults([]);
    setGlobalSearchMessage(error.message, "is-error");
  }
}

async function saveFavorite(item, actor, button = null) {
  if (button) button.disabled = true;
  try {
    await request("/favorites", {
      method: "POST",
      headers: { "X-Actor": actor },
      body: JSON.stringify(workspaceItemPayload(item)),
    });
    if (button) button.textContent = "已收藏";
    if (actor === personalLibraryActor()) await loadPersonalLibrary();
  } catch (error) {
    setGlobalSearchMessage(error.message, "is-error");
    if (button) button.disabled = false;
  }
}

async function openWorkspaceItem(item, actor) {
  try {
    await request("/recent-visits", {
      method: "POST",
      headers: { "X-Actor": actor },
      body: JSON.stringify(workspaceItemPayload(item)),
    });
    if (actor === personalLibraryActor()) loadPersonalLibrary();
    if (item.target_view === "tickets") {
      const input = select("#tickets-actor");
      if (input) input.value = actor;
      state.ticketWorkspace.selectedTicketId = item.target_id || item.entity_id;
      activateView("tickets");
      await loadTickets({ preserveSelection: true });
      await loadTicketPreview(item.target_id || item.entity_id);
      return;
    }
    if (item.target_view === "agent") {
      await openAgentForActor(actor, item.target_id || item.entity_id);
      return;
    }
    if (item.target_view === "knowledge") {
      activateView("knowledge");
      await loadKnowledgeBases();
      if (item.target_id) await openKnowledgeBaseDetail(item.target_id);
      return;
    }
    if (item.target_view === "graph") {
      activateView("graph");
      const query = select("#graph-search-query");
      if (query) query.value = item.target_id || item.metadata_json?.entity || "";
      return;
    }
    activateView(item.target_view);
  } catch (error) {
    setPersonalLibraryMessage(error.message, "is-error");
  }
}

function renderPersonalLibraryItems(containerSelector, items, emptyMessage, isFavorite) {
  const container = select(containerSelector);
  if (!container) return;
  container.replaceChildren();
  if (items.length === 0) {
    appendAgentElement(container, "p", emptyMessage, "personal-library-empty");
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("article");
    row.className = "personal-item";
    const openButton = document.createElement("button");
    openButton.type = "button";
    openButton.className = "personal-item-open";
    const heading = document.createElement("div");
    appendAgentElement(heading, "strong", item.title);
    const [typeLabel, typeClass] = workspaceItemTypePresentation(item.entity_type);
    appendAgentElement(heading, "span", typeLabel, `workspace-item-type ${typeClass}`);
    appendAgentElement(openButton, "p", item.subtitle);
    openButton.prepend(heading);
    openButton.addEventListener("click", () => openWorkspaceItem(item, personalLibraryActor()));
    row.append(openButton);
    if (isFavorite) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "workspace-remove-button";
      remove.textContent = "取消收藏";
      remove.addEventListener("click", () => removeFavorite(item, remove));
      row.append(remove);
    }
    container.append(row);
  });
}

async function removeFavorite(item, button) {
  button.disabled = true;
  try {
    await request(`/favorites/${encodeURIComponent(item.entity_type)}/${encodeURIComponent(item.entity_id)}`, {
      method: "DELETE",
      headers: { "X-Actor": personalLibraryActor() },
    });
    await loadPersonalLibrary();
  } catch (error) {
    setPersonalLibraryMessage(error.message, "is-error");
    button.disabled = false;
  }
}

async function loadPersonalLibrary() {
  try {
    setPersonalLibraryMessage("正在加载个人工作项...", "is-pending");
    const actor = personalLibraryActor();
    const [favorites, recentVisits] = await Promise.all([
      request("/favorites?limit=20", { headers: { "X-Actor": actor } }),
      request("/recent-visits?limit=20", { headers: { "X-Actor": actor } }),
    ]);
    state.personalLibrary.favorites = favorites.items;
    state.personalLibrary.recentVisits = recentVisits.items;
    const favoritesCount = select("#favorites-count");
    const visitsCount = select("#recent-visits-count");
    if (favoritesCount) favoritesCount.textContent = String(favorites.items.length);
    if (visitsCount) visitsCount.textContent = String(recentVisits.items.length);
    renderPersonalLibraryItems("#favorites-list", favorites.items, "还没有收藏。可在全局搜索结果中收藏常用内容。", true);
    renderPersonalLibraryItems("#recent-visits-list", recentVisits.items, "还没有访问记录。打开搜索结果后会出现在这里。", false);
    setPersonalLibraryMessage();
  } catch (error) {
    setPersonalLibraryMessage(error.message, "is-error");
  }
}

async function submitAgentFeedback(messageId, feedbackType, button) {
  const actor = activeAgentActor();
  let comment = "";
  if (feedbackType !== "helpful") {
    const input = window.prompt("请简要说明问题，便于后续维护知识库：", "");
    if (input === null) return;
    comment = input.trim();
  }
  selectAll(".agent-feedback-button").forEach((item) => { item.disabled = true; });
  try {
    await request(`/agent-messages/${encodeURIComponent(messageId)}/feedback`, {
      method: "POST",
      headers: { "X-Actor": actor },
      body: JSON.stringify({ feedback_type: feedbackType, comment }),
    });
    const feedback = button.parentElement;
    if (feedback) {
      feedback.replaceChildren();
      appendAgentElement(feedback, "span", "反馈已记录，感谢你的帮助。", "agent-feedback-confirmation");
    }
  } catch (error) {
    selectAll(".agent-feedback-button").forEach((item) => { item.disabled = false; });
    showAgentMessage(error.message);
  }
}

function bindEngagementFeatures() {
  selectAll('[data-view="search"]').forEach((button) => button.addEventListener("click", () => select("#global-search-input")?.focus()));
  selectAll('[data-view="personal-library"]').forEach((button) => button.addEventListener("click", loadPersonalLibrary));
  select("#global-search-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    runGlobalSearch();
  });
  select("#refresh-personal-library")?.addEventListener("click", loadPersonalLibrary);
  select("#personal-library-actor")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadPersonalLibrary();
    }
  });
}

document.addEventListener("DOMContentLoaded", bindEngagementFeatures);

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

document.addEventListener("DOMContentLoaded", bindNotifications);

// Standardized service request form
function setCreateTicketMessage(message = "", stateName = "") {
  const area = select("#create-ticket-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function createTicketActor() {
  return currentActor();
}

function clearCreateTicketSuggestions() {
  select("#create-ticket-knowledge-results")?.replaceChildren();
  select("#create-ticket-similar-results")?.replaceChildren();
  const summary = select("#create-ticket-assist-summary");
  if (summary) summary.textContent = "填写标题和描述后，系统会检查可用资料与历史工单。";
}

function renderCreateTicketKnowledgeSuggestions(results) {
  const container = select("#create-ticket-knowledge-results");
  if (!container) return;
  container.replaceChildren();
  if (results.length === 0) {
    appendAgentElement(container, "p", "未找到可直接参考的知识库资料。", "create-ticket-empty");
    return;
  }
  results.forEach((result) => {
    const item = document.createElement("article");
    item.className = "create-ticket-result";
    appendAgentElement(item, "strong", result.source_name);
    appendAgentElement(item, "p", result.text);
    container.append(item);
  });
}

function renderSimilarTicketSuggestions(page) {
  const container = select("#create-ticket-similar-results");
  if (!container) return;
  container.replaceChildren();
  if (page.items.length === 0) {
    appendAgentElement(container, "p", "没有找到你的相似历史工单。", "create-ticket-empty");
    return;
  }
  page.items.forEach((ticket) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "create-ticket-result is-ticket";
    appendAgentElement(item, "strong", ticket.title);
    const [statusLabel] = ticketStatusPresentation(ticket.status);
    appendAgentElement(item, "span", `${statusLabel} · ${formatDashboardDate(ticket.updated_at)}`);
    item.addEventListener("click", () => {
      state.ticketWorkspace.selectedTicketId = ticket.id;
      activateView("tickets");
      loadTickets({ preserveSelection: true }).then(() => loadTicketPreview(ticket.id));
    });
    container.append(item);
  });
}

async function loadCreateTicketSuggestions() {
  const title = String(select("#create-ticket-title")?.value ?? "").trim();
  const description = String(select("#create-ticket-description")?.value ?? "").trim();
  const query = `${title} ${description}`.trim();
  const knowledgeBaseId = String(select("#create-ticket-knowledge-base")?.value ?? "");
  const actor = createTicketActor();
  const checkButton = select("#check-ticket-suggestions");

  if (query.length < 2) {
    setCreateTicketMessage("请先填写问题标题或描述，再检查建议。", "is-error");
    return;
  }
  if (checkButton) checkButton.disabled = true;
  const summary = select("#create-ticket-assist-summary");
  if (summary) summary.textContent = "正在检查知识资料和你的历史工单...";

  try {
    const similarRequest = request(`/tickets?${new URLSearchParams({ query, limit: "3", offset: "0" }).toString()}`, {
      headers: { "X-Actor": actor },
    });
    const knowledgeRequest = knowledgeBaseId
      ? request(`/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/search`, {
        method: "POST",
        body: JSON.stringify({ query, limit: 3 }),
      })
      : Promise.resolve([]);
    const [similarTickets, knowledgeResults] = await Promise.all([similarRequest, knowledgeRequest]);
    renderSimilarTicketSuggestions(similarTickets);
    renderCreateTicketKnowledgeSuggestions(knowledgeResults);
    if (summary) {
      summary.textContent = `找到 ${knowledgeResults.length} 条知识资料和 ${similarTickets.total} 张相似历史工单。`;
    }
    setCreateTicketMessage();
  } catch (error) {
    clearCreateTicketSuggestions();
    setCreateTicketMessage(error.message, "is-error");
  } finally {
    if (checkButton) checkButton.disabled = false;
  }
}

function bindCreateTicketForm() {
  const form = select("#create-ticket-form");
  if (!form) return;

  selectAll('[data-view="create-ticket"]').forEach((button) => {
    button.addEventListener("click", () => {
      clearCreateTicketSuggestions();
      loadKnowledgeBases().catch((error) => setCreateTicketMessage(error.message, "is-error"));
    });
  });
  select("#check-ticket-suggestions")?.addEventListener("click", loadCreateTicketSuggestions);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const actor = String(data.get("actor") ?? "").trim();
    const payload = {
      title: String(data.get("title") ?? "").trim(),
      description: String(data.get("description") ?? "").trim(),
      category: String(data.get("category") ?? "general"),
      impact: String(data.get("impact") ?? "single_user"),
      priority: String(data.get("priority") ?? "medium"),
    };
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    try {
      setCreateTicketMessage("正在提交服务请求...", "is-pending");
      const ticket = await request("/tickets", {
        method: "POST",
        headers: { "X-Actor": actor },
        body: JSON.stringify(payload),
      });
      form.reset();
      const actorInput = select("#create-ticket-actor");
      if (actorInput) actorInput.value = actor;
      state.ticketWorkspace.selectedTicketId = ticket.id;
      setCreateTicketMessage("工单已创建，正在打开详情。", "is-success");
      activateView("tickets");
      await loadTickets({ preserveSelection: true });
      await loadTicketPreview(ticket.id);
      loadDashboard();
    } catch (error) {
      setCreateTicketMessage(error.message, "is-error");
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  });
}

if (!window.__knowledgeopsDeferredBootstrap) {
  document.addEventListener("DOMContentLoaded", bootstrapFrontend, { once: true });
}
