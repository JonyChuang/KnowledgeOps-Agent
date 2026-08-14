import { useEffect, useState, type FormEvent } from "react";
import { GitFork, Network, Search } from "lucide-react";

import { api } from "../../api/client";
import type { GraphSearchResult, KnowledgeBase } from "../../api/types";
import { EmptyState, LoadingBlock } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

const examples = ["VPN", "Redis", "账号 权限", "错误日志"];

export function GraphPage() {
  const knowledgeBases = useAppStore((state) => state.knowledgeBases);
  const setKnowledgeBases = useAppStore((state) => state.setKnowledgeBases);
  const routeTarget = useAppStore((state) => state.routeTarget);
  const clearRouteTarget = useAppStore((state) => state.clearRouteTarget);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(5);
  const [results, setResults] = useState<GraphSearchResult[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(knowledgeBases.length === 0);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    if (knowledgeBases.length) {
      setKnowledgeBaseId((value) => value || knowledgeBases[0].id);
      setLoading(false);
      return;
    }
    api<KnowledgeBase[]>("/knowledge-bases")
      .then((items) => { setKnowledgeBases(items); setKnowledgeBaseId(items[0]?.id ?? ""); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "知识库加载失败。"))
      .finally(() => setLoading(false));
  }, [knowledgeBases.length, setKnowledgeBases]);

  useEffect(() => { if (!routeTarget) return; setQuery(routeTarget); clearRouteTarget(); }, [routeTarget, clearRouteTarget]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSearching(true); setError(""); setSearched(true);
    try {
      setResults(await api<GraphSearchResult[]>(`/knowledge-bases/${knowledgeBaseId}/graph/search`, {
        method: "POST",
        body: JSON.stringify({ query, limit }),
      }));
    } catch (reason) {
      setResults([]);
      setError(reason instanceof Error ? reason.message : "图谱检索失败。");
    } finally {
      setSearching(false);
    }
  };

  if (loading) return <LoadingBlock label="正在加载图谱检索..." />;
  if (!knowledgeBases.length) return <EmptyState title="请先创建知识库" description="图谱检索依赖已导入并完成索引的资料。" />;

  return <section className="react-page graph-workspace">
    <header className="tool-page-header"><div><p className="tool-eyebrow">Entity Relationship Search</p><h1>图谱检索</h1><p>通过技术实体和业务术语，找到跨文档的关联证据。</p></div><span className="tool-status-label graph-status-label"><GitFork size={15} />GraphRAG</span></header>
    <div className="graph-search-shell">
      <form className="graph-search-panel" onSubmit={submit}>
        <div className="graph-scope-row"><label>检索范围<select value={knowledgeBaseId} onChange={(event) => setKnowledgeBaseId(event.target.value)}>{knowledgeBases.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="graph-limit-field">返回数量<input type="number" min="1" max="20" value={limit} onChange={(event) => setLimit(Math.min(20, Math.max(1, Number(event.target.value) || 1)))} /></label></div>
        <label className="graph-query-field"><span>输入问题或实体组合</span><textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={4} maxLength={4000} placeholder="例如：VPN 与 Redis 连接异常可能关联哪些排查资料？" required /></label>
        <div className="graph-search-footer"><div className="graph-entity-hints">{examples.map((example) => <button type="button" key={example} onClick={() => setQuery(example)}>{example}</button>)}</div><button className="primary-action" disabled={searching}><Search size={17} />{searching ? "正在检索..." : "检索关联"}</button></div>
      </form>
      <aside className="graph-explainer"><Network size={22} /><h2>关联检索如何工作？</h2><p>系统识别问题中的实体，再从同一知识库中查找与这些实体相连的文档块。</p><span>适用于故障定位、影响分析与跨资料核对。</span></aside>
    </div>
    {error && <p className="form-message is-error">{error}</p>}
    <section className="graph-results-section"><header className="section-title-row"><div><h2>关联证据</h2><p>{searched ? `已找到 ${results.length} 条关联文档片段。` : "等待一次图谱检索"}</p></div><span className="activity-count">{results.length}</span></header><div className="graph-results-list">{results.map((result, index) => <article className="graph-result" key={result.chunk_id}><span className="graph-result-marker">{index + 1}</span><div><div className="graph-result-title-row"><h2>{result.source_name}</h2><span className="graph-result-chip">片段 {result.chunk_index + 1}</span></div><p className="graph-result-text">{result.text}</p></div></article>)}</div>{searched && !searching && !error && !results.length && <EmptyState title="没有找到关联片段" description="尝试使用文档中出现的实体、系统名称或流程关键词。" />}</section>
  </section>;
}
