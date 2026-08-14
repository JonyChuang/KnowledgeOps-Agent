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
