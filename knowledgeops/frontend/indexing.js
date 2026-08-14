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
