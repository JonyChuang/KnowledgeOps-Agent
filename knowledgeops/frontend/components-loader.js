"use strict";

const CACHE_VERSION = "20260814-module-bindings-1";

const fragmentPaths = [
  "components/topbar.html",
  "components/sidebar.html",
  "views/dashboard.html",
  "views/search.html",
  "views/tickets.html",
  "views/service-desk.html",
  "views/notifications.html",
  "views/personal-library.html",
  "views/user-management.html",
  "views/create-ticket.html",
  "views/knowledge.html",
  "views/documents.html",
  "views/graph.html",
  "views/agent.html",
  "views/profile.html",
  "components/dialogs.html",
  "components/profile-dialog.html",
];

const moduleScripts = [
  "core.js",
  "agent.js",
  "knowledge.js",
  "indexing.js",
  "dashboard.js",
  "tickets.js",
  "engagement.js",
  "notifications.js",
  "create-ticket.js",
  "profile.js",
];

// The application modules are dynamically loaded after the markup fragments.
// Core defers its regular DOM bootstrap until the final module has been loaded.
window.__knowledgeopsDeferredBootstrap = true;

async function fetchFragment(path) {
  const response = await fetch(`./${path}?v=${CACHE_VERSION}`, { cache: "no-cache" });
  if (!response.ok) throw new Error(`Could not load ${path}.`);
  return response.text();
}

function loadModule(path) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `./${path}?v=${CACHE_VERSION}`;
    script.async = false;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Could not load ${path}.`));
    document.body.append(script);
  });
}

async function mountApplication() {
  const mount = document.querySelector("#app-fragments");
  if (!mount) return;

  const fragments = await Promise.all(fragmentPaths.map(fetchFragment));
  const [topbar, sidebar, ...viewsAndDialogs] = fragments;
  const profileDialog = viewsAndDialogs.pop();
  const dialogs = viewsAndDialogs.pop();
  mount.innerHTML = `${topbar}<div class="workspace">${sidebar}<main class="content">${viewsAndDialogs.join("\n")}</main></div>${dialogs}${profileDialog}`;

  for (const script of moduleScripts) {
    await loadModule(script);
  }
  bootstrapFrontend();
  mount.setAttribute("aria-busy", "false");
}

mountApplication().catch((error) => {
  console.error("Unable to mount the application.", error);
  const mount = document.querySelector("#app-fragments");
  if (mount) {
    mount.replaceChildren();
    const errorPanel = document.createElement("main");
    errorPanel.className = "startup-error";
    const title = document.createElement("h1");
    title.textContent = "页面加载失败";
    const message = document.createElement("p");
    message.textContent = "请刷新页面；若问题持续，请检查浏览器控制台中的错误信息。";
    errorPanel.append(title, message);
    mount.append(errorPanel);
    mount.setAttribute("aria-busy", "false");
    return;
  }
});
