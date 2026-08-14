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
