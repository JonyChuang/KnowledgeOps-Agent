import { useState, type FormEvent } from "react";

import { api } from "../../api/client";
import type { SearchItem } from "../../api/types";
import { EmptyState, LoadingBlock } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

interface SearchResponse {
  query: string;
  items: SearchItem[];
  total: number;
}

const kindLabels: Record<string, string> = { knowledge_base: "知识库", document: "知识资料", graph: "图谱实体", ticket: "我的工单", conversation: "历史对话" };

export function SearchPage() {
  const openWorkspaceItem = useAppStore((state) => state.openWorkspaceItem);
  const showNotice = useAppStore((state) => state.showNotice);
  const [term, setTerm] = useState("");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<Set<string>>(new Set());

  const search = async (event: FormEvent) => {
    event.preventDefault();
    if (!term.trim()) return;
    setLoading(true);
    setError("");
    try {
      setResult(await api<SearchResponse>(`/search?query=${encodeURIComponent(term.trim())}&limit=30`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "搜索失败。");
    } finally {
      setLoading(false);
    }
  };

  const saveFavorite = async (item: SearchItem) => {
    const key = `${item.entity_type}:${item.entity_id}`;
    try {
      await api("/favorites", { method: "POST", body: JSON.stringify(toPayload(item)) });
      setSaved((current) => new Set(current).add(key));
      showNotice("已收藏到个人资料库。", "success");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "收藏失败。");
    }
  };

  const open = async (item: SearchItem) => {
    try {
      await api("/recent-visits", { method: "POST", body: JSON.stringify(toPayload(item)) });
      openWorkspaceItem(item.target_view, item.target_id || item.entity_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "打开内容失败。");
    }
  };

  return <section id="search-view" className="view is-active"><div className="search-workspace">
    <header className="tool-page-header search-header"><div><p className="tool-eyebrow">Global Search</p><h1>全局搜索</h1><p>同时检索已导入资料、图谱实体、你的历史 Agent 对话和工单。</p></div></header>
    <form className="global-search-form" onSubmit={search}><input autoFocus value={term} onChange={(event) => setTerm(event.target.value)} placeholder="搜索知识资料、图谱实体、历史对话或我的工单" maxLength={200} required /><button className="primary-action" disabled={loading}>{loading ? "正在搜索..." : "搜索"}</button></form>
    {error && <p className="form-message is-error">{error}</p>}
    <section className="global-search-panel" aria-live="polite"><div className="section-title-row"><div><h2>搜索结果</h2><p>{result ? `“${result.query}”共找到 ${result.total} 条结果。` : "输入关键词后开始跨工作区检索。"}</p></div><span className="activity-count">{result?.total ?? 0}</span></div>
      {loading ? <LoadingBlock label="正在搜索工作区..." /> : result?.items.length ? <div className="global-search-results">{result.items.map((item) => {
        const key = `${item.entity_type}:${item.entity_id}`;
        return <article className="global-search-item" key={key}><button className="global-search-open" onClick={() => void open(item)}><div><strong>{item.title}</strong><span className={`workspace-item-type is-${item.entity_type.replace("_", "-")}`}>{kindLabels[item.entity_type] || "工作项"}</span></div><p className="global-search-item-summary">{item.summary}</p></button><button className="workspace-favorite-button" disabled={saved.has(key)} onClick={() => void saveFavorite(item)}>{saved.has(key) ? "已收藏" : "收藏"}</button></article>;
      })}</div> : result ? <EmptyState title="没有匹配结果" description="可以尝试使用更具体的业务术语、文档标题或工单标题。" /> : <p className="global-search-empty">输入关键词后开始跨工作区检索。</p>}
    </section>
  </div></section>;
}

function toPayload(item: SearchItem) {
  return { entity_type: item.entity_type, entity_id: item.entity_id, title: item.title, subtitle: item.summary, target_view: item.target_view, target_id: item.target_id, metadata_json: item.metadata_json };
}
