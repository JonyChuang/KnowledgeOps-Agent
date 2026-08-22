import { useEffect, useMemo, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";

import { api } from "../../api/client";
import type { KnowledgeBase, KnowledgeDocument } from "../../api/types";
import { EmptyState, LoadingBlock, Modal, formatDate } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

type ImportMode = "text" | "file" | "web" | null;
type ImportKind = Exclude<ImportMode, null>;

interface ImportRequest {
  mode: ImportKind;
  initialFiles?: File[];
}

const statusLabels: Record<string, string> = {
  uploaded: "待索引",
  indexing: "索引中",
  ready: "已就绪",
  failed: "索引失败",
};

const lifecycleLabels: Record<KnowledgeDocument["lifecycle"], string> = {
  draft: "草稿",
  active: "生效中",
  archived: "已归档",
};

export function KnowledgePage() {
  const knowledgeBases = useAppStore((state) => state.knowledgeBases);
  const setKnowledgeBases = useAppStore((state) => state.setKnowledgeBases);
  const showNotice = useAppStore((state) => state.showNotice);
  const routeTarget = useAppStore((state) => state.routeTarget);
  const clearRouteTarget = useAppStore((state) => state.clearRouteTarget);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [createOpen, setCreateOpen] = useState(false);
  const [importRequest, setImportRequest] = useState<ImportRequest | null>(null);

  const selected = useMemo(() => knowledgeBases.find((item) => item.id === selectedId) ?? null, [knowledgeBases, selectedId]);

  const loadKnowledgeBases = async () => {
    setLoading(true);
    setError("");
    try {
      const list = await api<KnowledgeBase[]>("/knowledge-bases");
      setKnowledgeBases(list);
      const documentCounts = await Promise.all(list.map(async (knowledgeBase) => {
        try {
          return [knowledgeBase.id, (await api<KnowledgeDocument[]>(`/knowledge-bases/${knowledgeBase.id}/documents`)).length] as const;
        } catch {
          return [knowledgeBase.id, 0] as const;
        }
      }));
      setCounts(Object.fromEntries(documentCounts));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "知识库加载失败。");
    } finally {
      setLoading(false);
    }
  };

  const openKnowledgeBase = async (knowledgeBase: KnowledgeBase) => {
    setSelectedId(knowledgeBase.id);
    setDocuments([]);
    setError("");
    try {
      setDocuments(await api<KnowledgeDocument[]>(`/knowledge-bases/${knowledgeBase.id}/documents`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "文档列表加载失败。");
    }
  };

  useEffect(() => { void loadKnowledgeBases(); }, []);
  useEffect(() => {
    if (!routeTarget) return;
    const knowledgeBase = knowledgeBases.find((item) => item.id === routeTarget);
    if (!knowledgeBase) return;
    void openKnowledgeBase(knowledgeBase);
    clearRouteTarget();
  }, [routeTarget, knowledgeBases, clearRouteTarget]);

  const createKnowledgeBase = async (payload: { name: string; department: string; description: string }) => {
    try {
      const created = await api<KnowledgeBase>("/knowledge-bases", { method: "POST", body: JSON.stringify(payload) });
      setCreateOpen(false);
      showNotice("知识库已创建。", "success");
      await loadKnowledgeBases();
      await openKnowledgeBase(created);
    } catch (reason) {
      throw reason instanceof Error ? reason : new Error("创建知识库失败。");
    }
  };

  const queueDocument = async (document: KnowledgeDocument) => {
    await api(`/documents/${document.id}/index`, { method: "POST" });
    showNotice("资料已提交索引任务。", "success");
    if (selected) await openKnowledgeBase(selected);
  };

  const changeDocumentLifecycle = async (document: KnowledgeDocument) => {
    const lifecycle = document.lifecycle === "active" ? "archived" : "active";
    await api<KnowledgeDocument>(`/documents/${document.id}/lifecycle`, {
      method: "PATCH",
      body: JSON.stringify({ lifecycle }),
    });
    showNotice(lifecycle === "archived" ? "文档已归档。" : "文档已发布。", "success");
    if (selected) await openKnowledgeBase(selected);
  };

  if (loading) return <LoadingBlock label="正在加载知识库..." />;

  const queueDocuments = async (uploadedDocuments: KnowledgeDocument[]) => {
    for (const document of uploadedDocuments) {
      await api(`/documents/${document.id}/index`, { method: "POST" });
    }
    showNotice(`已提交 ${uploadedDocuments.length} 份资料的索引任务。`, "success");
    if (selected) await openKnowledgeBase(selected);
  };

  return (
    <section id="knowledge-view" className="view is-active">
      {selected ? (
        <KnowledgeDetail
          knowledgeBase={selected}
          documents={documents}
          error={error}
          onBack={() => { setSelectedId(null); setError(""); }}
          onRefresh={() => void openKnowledgeBase(selected)}
          onImport={(mode, initialFiles) => setImportRequest({ mode, initialFiles })}
          onQueue={queueDocument}
          onLifecycleChange={changeDocumentLifecycle}
        />
      ) : (
        <div className="knowledge-catalog">
          <header className="knowledge-page-header">
            <div>
              <p className="knowledge-eyebrow">Knowledge Center</p>
              <h1>知识库管理</h1>
              <p>将资料按主题分类，在对话中按知识库精准检索。</p>
            </div>
            <button className="primary-action" onClick={() => setCreateOpen(true)}>新建知识库</button>
          </header>
          {error && <p className="form-message is-error">{error}</p>}
          <div className="knowledge-card-grid">
            {knowledgeBases.length ? knowledgeBases.map((knowledgeBase) => (
              <article className="knowledge-card" key={knowledgeBase.id}>
                <button className="knowledge-card-open" onClick={() => void openKnowledgeBase(knowledgeBase)}>
                  <div className="knowledge-card-topline"><BookMark /><span className="knowledge-card-tag">已启用</span></div>
                  <div><h2>{knowledgeBase.name}</h2><p className="knowledge-card-description">{knowledgeBase.description || "暂未填写资料说明。"}</p></div>
                  <div className="knowledge-card-meta"><span>{counts[knowledgeBase.id] ?? 0} 篇文档</span><strong>{knowledgeBase.department}</strong></div>
                </button>
              </article>
            )) : <div className="knowledge-card-empty"><p>还没有知识库。新建后即可导入资料，让 Agent 基于真实内容回答。</p><button className="primary-action" onClick={() => setCreateOpen(true)}>新建知识库</button></div>}
          </div>
        </div>
      )}
      {createOpen && <CreateKnowledgeBaseModal onClose={() => setCreateOpen(false)} onSubmit={createKnowledgeBase} />}
      {importRequest && selected && <ImportModal mode={importRequest.mode} initialFiles={importRequest.initialFiles} knowledgeBase={selected} onClose={() => setImportRequest(null)} onUploaded={queueDocuments} />}
    </section>
  );
}

function BookMark() {
  return <span className="knowledge-card-illustration" aria-hidden="true"><span /><span /><span /></span>;
}

function KnowledgeDetail({ knowledgeBase, documents, error, onBack, onRefresh, onImport, onQueue, onLifecycleChange }: {
  knowledgeBase: KnowledgeBase;
  documents: KnowledgeDocument[];
  error: string;
  onBack: () => void;
  onRefresh: () => void;
  onImport: (mode: ImportKind, initialFiles?: File[]) => void;
  onQueue: (document: KnowledgeDocument) => Promise<void>;
  onLifecycleChange: (document: KnowledgeDocument) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const shown = documents.filter((document) => document.source_name.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const openDroppedFiles = (files: File[]) => {
    if (files.length) onImport("file", files);
  };
  const handleDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    setIsDragging(false);
    openDroppedFiles(Array.from(event.dataTransfer.files));
  };
  return <div className={`knowledge-detail${isDragging ? " is-dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }} onDragLeave={(event) => { if (event.currentTarget === event.target) setIsDragging(false); }} onDrop={handleDrop}>
    <header className="knowledge-detail-header">
      <button className="back-button" onClick={onBack}>返回知识库</button>
      <div className="knowledge-detail-title"><BookMark /><div><p className="knowledge-eyebrow">{knowledgeBase.department}</p><h1>{knowledgeBase.name}</h1><p>{knowledgeBase.description || "资料管理与检索范围。"}</p></div></div>
    </header>
    <div className="knowledge-detail-tabs"><button className="knowledge-tab" type="button">文档 <span>{documents.length}</span></button></div>
    <div className="knowledge-document-toolbar">
      <label className="knowledge-document-search"><span className="sr-only">检索文档</span><input type="search" placeholder="输入关键词筛选文档" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      <div className="knowledge-import-actions"><button className="secondary-action" onClick={() => onImport("file")}>本地上传</button><button className="secondary-action" onClick={() => onImport("web")}>网页导入</button><button className="secondary-action" onClick={() => onImport("text")}>添加文本</button></div>
    </div>
    <button className="knowledge-document-dropzone" type="button" onClick={() => onImport("file")}><span className="dropzone-symbol">+</span><strong>点击或拖放文件至此处上传</strong><span>支持 PDF、DOCX、Markdown、TXT 和 HTML，单个文件最大 10 MB</span></button>
    {error && <p className="form-message is-error">{error}</p>}
    <div className="knowledge-document-list">
      {shown.length ? shown.map((document) => <article className="knowledge-document-item" key={document.id}>
        <div><h2>{document.source_name}</h2><p>{document.source_type} · {document.chunk_count} 个片段 · 更新于 {formatDate(document.updated_at)}</p>{document.error_message && <p className="is-error">{document.error_message}</p>}</div>
        <div className="knowledge-document-item-meta"><span className={`document-status is-${document.status}`}>{statusLabels[document.status] || document.status}</span><span className={`document-status is-${document.lifecycle}`}>{lifecycleLabels[document.lifecycle]}</span>{(document.status === "uploaded" || document.status === "failed") && <button className="secondary-action" onClick={() => void onQueue(document)}>重新索引</button>}<button className="secondary-action" onClick={() => void onLifecycleChange(document)}>{document.lifecycle === "active" ? "归档" : "发布"}</button></div>
      </article>) : <p className="knowledge-document-empty">{query ? "没有匹配的文档。" : "这个知识库还没有资料。"}</p>}
    </div>
    <button className="text-action" onClick={onRefresh}>刷新文档状态</button>
  </div>;
}

function CreateKnowledgeBaseModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (payload: { name: string; department: string; description: string }) => Promise<void> }) {
  const [name, setName] = useState("");
  const [department, setDepartment] = useState("general");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try { await onSubmit({ name, department, description }); } catch (reason) { setError(reason instanceof Error ? reason.message : "创建失败。"); } finally { setSaving(false); }
  };
  return <Modal title="新建知识库" onClose={onClose}><form className="react-form" onSubmit={submit}><label>名称<input value={name} onChange={(event) => setName(event.target.value)} minLength={2} maxLength={120} required /></label><label>部门<input value={department} onChange={(event) => setDepartment(event.target.value)} minLength={1} maxLength={80} required /></label><label>描述<textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} maxLength={4000} /></label>{error && <p className="form-message is-error">{error}</p>}<div className="modal-actions"><button type="button" className="secondary-action" onClick={onClose}>取消</button><button className="primary-action" disabled={saving}>{saving ? "正在创建..." : "创建知识库"}</button></div></form></Modal>;
}

function ImportModal({ mode, initialFiles = [], knowledgeBase, onClose, onUploaded }: { mode: ImportKind; initialFiles?: File[]; knowledgeBase: KnowledgeBase; onClose: () => void; onUploaded: (documents: KnowledgeDocument[]) => Promise<void> }) {
  const [sourceName, setSourceName] = useState("");
  const [content, setContent] = useState("");
  const [url, setUrl] = useState("");
  const [files, setFiles] = useState<File[]>(initialFiles);
  const file = files[0] ?? null;
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (mode !== "file") return;
    document.querySelector<HTMLInputElement>(".file-input input[type='file']")?.setAttribute("multiple", "");
    setSourceName(files.length === 1 ? files[0].name : files.length ? `已选择 ${files.length} 个文件` : "");
  }, [files, mode]);
  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFiles = Array.from(event.target.files ?? []);
    setFiles(nextFiles);
    setSourceName(nextFiles.length === 1 ? nextFiles[0].name : nextFiles.length ? `已选择 ${nextFiles.length} 个文件` : "");
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      if (mode === "file" && files.length > 1) {
        const documents: KnowledgeDocument[] = [];
        for (const selectedFile of files) {
          const document = await api<KnowledgeDocument>(`/knowledge-bases/${knowledgeBase.id}/documents/upload?source_name=${encodeURIComponent(selectedFile.name)}`, { method: "POST", headers: { "Content-Type": selectedFile.type || "application/octet-stream" }, body: selectedFile });
          documents.push(document);
        }
        await onUploaded(documents);
        onClose();
        return;
      }
      let document: KnowledgeDocument;
      if (mode === "file") {
        if (!file) throw new Error("请选择要上传的文件。");
        document = await api<KnowledgeDocument>(`/knowledge-bases/${knowledgeBase.id}/documents/upload?source_name=${encodeURIComponent(file.name)}`, { method: "POST", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file });
      } else if (mode === "web") {
        document = await api<KnowledgeDocument>(`/knowledge-bases/${knowledgeBase.id}/documents/web-import`, { method: "POST", body: JSON.stringify({ url, source_name: sourceName || undefined }) });
      } else {
        document = await api<KnowledgeDocument>(`/knowledge-bases/${knowledgeBase.id}/documents`, { method: "POST", body: JSON.stringify({ source_name: sourceName, content }) });
      }
      await onUploaded([document]);
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "导入失败。");
    } finally {
      setSaving(false);
    }
  };
  const title = mode === "file" ? "上传本地文件" : mode === "web" ? "导入网页内容" : "添加文本资料";
  return <Modal title={title} onClose={onClose}><form className="react-form" onSubmit={submit}>{mode === "file" && <label className="file-input">选择文件<input type="file" accept=".pdf,.docx,.md,.markdown,.txt,.html,.htm" onChange={onFile} required /><span>{file?.name || "支持 PDF、DOCX、Markdown、TXT 和 HTML，最大 10 MB"}</span></label>}{mode === "web" && <label>网页地址<input type="url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com/article" maxLength={2048} required /></label>}<label>资料名称{mode === "file" ? <input value={sourceName} readOnly /> : <input value={sourceName} onChange={(event) => setSourceName(event.target.value)} maxLength={255} required={mode === "text"} placeholder={mode === "web" ? "可选" : "例如：VPN 排障手册"} />}</label>{mode === "text" && <label>文档内容<textarea value={content} onChange={(event) => setContent(event.target.value)} rows={9} maxLength={2_000_000} required /></label>}{error && <p className="form-message is-error">{error}</p>}<div className="modal-actions"><button type="button" className="secondary-action" onClick={onClose}>取消</button><button className="primary-action" disabled={saving}>{saving ? "正在导入..." : "导入并索引"}</button></div></form></Modal>;
}
