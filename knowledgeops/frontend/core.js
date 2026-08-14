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
    return false;
  }

  selectAll(".nav-item[data-view]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === viewName);
  });

  selectAll(".view").forEach((view) => {
    view.classList.toggle("is-active", view === target);
  });
  return true;
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
  selectAll("#dashboard-actor-greeting, #agent-actor").forEach((element) => {
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

function appendAgentElement(parent, tagName, text, className = "") {
  const element = document.createElement(tagName);
  element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
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


let frontendBootstrapped = false;

function bootstrapFrontend() {
  if (frontendBootstrapped) return;
  frontendBootstrapped = true;

  // Authentication stays available even when an optional page module has a UI error.
  const setupSteps = [
    () => bindNavigation(),
    () => {
      const requestedView = new URLSearchParams(window.location.search).get("view");
      if (requestedView && findView(requestedView)) activateView(requestedView);
    },
    () => bindKnowledgeBaseDialog(),
    () => bindKnowledgeDetail(),
    () => bindKnowledgeLocalFileImport(),
    () => bindKnowledgeWebImport(),
    () => bindDocumentIndexForm(),
    () => bindGraphSearchForm(),
    () => bindOperationalShortcuts(),
    () => bindDashboard(),
    () => bindTickets(),
    () => bindServiceDesk(),
    () => bindEngagementFeatures(),
    () => bindNotifications(),
    () => bindCreateTicketForm(),
    () => bindAgentWorkspace(),
    () => bindAgentForm(),
    () => renderConversationList(),
    () => renderAgentMessages(),
    () => bindAuthentication(),
    () => bindProfile(),
    () => select("#refresh-button")?.addEventListener("click", checkApi),
  ];

  setupSteps.forEach((setup) => {
    try {
      setup();
    } catch (error) {
      console.error("Failed to initialize a frontend module.", error);
    }
  });

  checkApi();
  initializeAuthentication();
}

if (!window.__knowledgeopsDeferredBootstrap) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrapFrontend, { once: true });
  } else {
    bootstrapFrontend();
  }
}
