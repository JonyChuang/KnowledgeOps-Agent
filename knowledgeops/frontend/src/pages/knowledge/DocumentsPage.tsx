import { useEffect, useMemo, useState, type FormEvent } from "react";
import { ArrowRight, Database, FileText, FolderOpen, ListChecks } from "lucide-react";

import { api } from "../../api/client";
import type { KnowledgeBase, KnowledgeDocument } from "../../api/types";
import { EmptyState, LoadingBlock, StatusPill, formatDate } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

export function DocumentsPage() {
  const knowledgeBases = useAppStore((state) => state.knowledgeBases);
  const setKnowledgeBases = useAppStore((state) => state.setKnowledgeBases);
  const setActiveView = useAppStore((state) => state.setActiveView);
  const showNotice = useAppStore((state) => state.showNotice);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [content, setContent] = useState("");
  const [submitted, setSubmitted] = useState<KnowledgeDocument[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(knowledgeBases.length === 0);

  useEffect(() => {
    if (knowledgeBases.length) {
      setKnowledgeBaseId((value) => value || knowledgeBases[0].id);
      setLoading(false);
      return;
    }
    api<KnowledgeBase[]>("/knowledge-bases")
      .then((items) => {
        setKnowledgeBases(items);
        setKnowledgeBaseId(items[0]?.id ?? "");
      })
      .catch((reason) => showNotice(reason instanceof Error ? reason.message : "知识库加载失败。", "error"))
      .finally(() => setLoading(false));
  }, [knowledgeBases.length, setKnowledgeBases, showNotice]);

  const targetKnowledgeBase = useMemo(
    () => knowledgeBases.find((item) => item.id === knowledgeBaseId),
    [knowledgeBases, knowledgeBaseId],
  );

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!knowledgeBaseId) return;
    setSubmitting(true);
    try {
      const document = await api<KnowledgeDocument>(`/knowledge-bases/${knowledgeBaseId}/documents`, {
        method: "POST",
        body: JSON.stringify({ source_name: sourceName, content }),
      });
      await api(`/documents/${document.id}/index`, { method: "POST" });
      setSubmitted((items) => [document, ...items.filter((item) => item.id !== document.id)]);
      setSourceName("");
      setContent("");
      showNotice("文档已提交索引。", "success");
    } catch (reason) {
      showNotice(reason instanceof Error ? reason.message : "文档提交失败。", "error");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingBlock label="正在加载知识库..." />;
  if (!knowledgeBases.length) return <EmptyState title="请先创建知识库" description="文档索引需要明确的目标知识库。" />;

  return <section className="react-page index-workspace">
    <header className="tool-page-header">
      <div><p className="tool-eyebrow">Document Operations</p><h1>文档索引</h1><p>将临时说明、流程和操作手册提交为可检索的知识片段。</p></div>
      <span className="tool-status-label"><Database size={15} />异步处理</span>
    </header>
    <div className="index-layout">
      <form className="index-submit-panel" onSubmit={submit}>
        <div className="panel-heading"><span className="panel-icon"><FileText size={21} /></span><div><h2>添加文本资料</h2><p>适合补充临时说明、流程和操作手册。</p></div></div>
        <label>目标知识库<select value={knowledgeBaseId} onChange={(event) => setKnowledgeBaseId(event.target.value)} required>{knowledgeBases.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>资料名称<input value={sourceName} onChange={(event) => setSourceName(event.target.value)} maxLength={255} placeholder="例如：VPN 连接排障手册" required /></label>
        <label>文档内容<textarea value={content} onChange={(event) => setContent(event.target.value)} rows={11} maxLength={2_000_000} placeholder="粘贴或输入需要加入知识库的内容..." required /></label>
        <div className="index-submit-footer"><span>提交后将自动分块、向量化并建立关键词索引</span><button className="primary-action" disabled={submitting}>{submitting ? "正在提交..." : "提交索引"}</button></div>
      </form>
      <aside className="index-side-panel">
        <section className="index-summary-card"><div className="side-card-heading"><ListChecks size={18} /><h2>索引流程</h2></div><ol className="index-flow-list"><li><span>1</span>保存原始资料和元数据</li><li><span>2</span>Worker 解析、分块并生成 Embedding</li><li><span>3</span>写入向量、关键词和图谱索引</li><li><span>4</span>状态更新为 ready 或 failed</li></ol></section>
        <section className="index-side-note"><FolderOpen size={19} /><strong>更多导入方式</strong><p>本地文件和网页内容可在“知识库”中直接导入。</p><button type="button" className="secondary-action" onClick={() => setActiveView("knowledge")}>前往知识库<ArrowRight size={16} /></button></section>
      </aside>
    </div>
    <section className="index-activity-section"><header className="section-title-row"><div><h2>本次处理</h2><p>{targetKnowledgeBase ? `提交至 ${targetKnowledgeBase.name} 的资料会显示在这里。` : "查看当前页面提交的资料及处理状态。"}</p></div><span className="activity-count">{submitted.length}</span></header><div className="index-activity-list">{submitted.length ? submitted.map((document) => <article className="index-activity-item" key={document.id}><span className="index-file-icon">TXT</span><div><h3>{document.source_name}</h3><p>已提交于 {formatDate(document.created_at)}</p></div><StatusPill value={document.status} /></article>) : <EmptyState title="尚未提交资料" description="提交资料后，处理状态会显示在这里。" />}</div></section>
  </section>;
}
