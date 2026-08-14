// Knowledge base catalog and document workspace
state.activeKnowledgeBaseId = null;
state.activeKnowledgeDocuments = [];
state.knowledgeDocumentCounts = new Map();

function getKnowledgeBaseList() {
  let container = select("#knowledge-base-list");
  if (container) return container;

  const view = findView("knowledge");
  if (!view) return null;

  container = document.createElement("div");
  container.id = "knowledge-base-list";
  container.className = "knowledge-card-grid";
  view.append(container);
  return container;
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

function showFormMessage(form, message = "") {
  let area = form.querySelector(".form-message");
  if (!area) {
    area = document.createElement("p");
    area.className = "form-message";
    form.append(area);
  }
  area.textContent = message;
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
  try {
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
  } catch (error) {
    state.knowledgeBases = [];
    state.knowledgeDocumentCounts = new Map();
    const container = getKnowledgeBaseList();
    if (container) {
      container.replaceChildren();
      const message = document.createElement("p");
      message.className = "knowledge-card-empty form-message is-error";
      message.textContent = `知识库加载失败：${error.message}`;
      container.append(message);
    }
    throw error;
  }
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
