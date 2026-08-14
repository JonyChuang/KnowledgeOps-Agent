"use strict";

function userRoleLabel(role) {
  return {
    employee: "员工",
    service_desk: "服务台人员",
    admin: "管理员",
  }[role] ?? "-";
}

function formatProfileDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(date);
}

function renderProfile() {
  const user = currentUser();
  const displayName = user?.display_name || user?.username || "K";
  const setText = (selector, value) => {
    const element = select(selector);
    if (element) element.textContent = value;
  };

  const nameInput = select("#profile-display-name");
  if (nameInput) nameInput.value = user?.display_name ?? "";
  setText("#profile-avatar", displayName.slice(0, 1).toUpperCase());
  setText("#profile-account-summary", user?.username ?? "-");
  setText("#profile-username", user?.username ?? "-");
  setText("#profile-role", userRoleLabel(user?.role));
  setText("#profile-created-at", formatProfileDate(user?.created_at));
}

function setProfileMessage(message = "", stateName = "") {
  const area = select("#profile-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function setPasswordMessage(message = "", stateName = "") {
  const area = select("#change-password-message");
  if (!area) return;
  area.className = `form-message ${stateName}`;
  area.textContent = message;
}

function bindProfile() {
  const openProfile = () => {
    const popover = select("#account-menu-popover");
    const trigger = select("#account-menu-trigger");
    if (popover) popover.hidden = true;
    trigger?.setAttribute("aria-expanded", "false");
    renderProfile();
    if (!activateView("profile")) {
      setProfileMessage("个人中心暂时无法加载，请刷新页面后重试。", "is-error");
    }
  };
  select("#open-profile-button")?.addEventListener("click", openProfile);

  select("#profile-display-name-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const displayName = String(select("#profile-display-name")?.value ?? "").trim();
    if (!displayName) {
      setProfileMessage("请输入昵称。", "is-error");
      return;
    }
    const submit = select("#profile-display-name-submit");
    if (submit) submit.disabled = true;
    try {
      state.auth.user = await request("/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName }),
      });
      syncAuthenticatedUser();
      renderProfile();
      setProfileMessage("昵称已更新。", "is-success");
    } catch (error) {
      setProfileMessage(error.message, "is-error");
    } finally {
      if (submit) submit.disabled = false;
    }
  });

  const dialog = select("#change-password-dialog");
  const passwordForm = select("#change-password-form");
  select("#open-change-password-dialog")?.addEventListener("click", () => {
    passwordForm?.reset();
    setPasswordMessage();
    dialog?.showModal();
    select("#current-password")?.focus();
  });
  select("#close-change-password-dialog")?.addEventListener("click", () => dialog?.close());
  passwordForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const currentPassword = String(select("#current-password")?.value ?? "");
    const newPassword = String(select("#new-password")?.value ?? "");
    const confirmation = String(select("#confirm-new-password")?.value ?? "");
    if (newPassword !== confirmation) {
      setPasswordMessage("两次输入的新密码不一致。", "is-error");
      return;
    }
    const submit = select("#change-password-submit");
    if (submit) submit.disabled = true;
    try {
      await request("/auth/me/password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      dialog?.close();
      passwordForm.reset();
      setProfileMessage("密码已更新。", "is-success");
    } catch (error) {
      setPasswordMessage(error.message, "is-error");
    } finally {
      if (submit) submit.disabled = false;
    }
  });
}
