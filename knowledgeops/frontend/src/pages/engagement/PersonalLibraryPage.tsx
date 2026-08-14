import { useEffect, useState } from "react";

import { api } from "../../api/client";
import type { WorkspaceItem } from "../../api/types";
import { EmptyState, LoadingBlock } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

interface ItemsResponse {
  items: WorkspaceItem[];
}

const kindLabels: Record<string, string> = { knowledge_base: "知识库", document: "知识资料", graph: "图谱实体", ticket: "我的工单", conversation: "历史对话" };

export function PersonalLibraryPage() {
  const openWorkspaceItem = useAppStore((state) => state.openWorkspaceItem);
  const showNotice = useAppStore((state) => state.showNotice);
  const [favorites, setFavorites] = useState<WorkspaceItem[]>([]);
  const [recent, setRecent] = useState<WorkspaceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [favoriteResponse, recentResponse] = await Promise.all([api<ItemsResponse>("/favorites?limit=30"), api<ItemsResponse>("/recent-visits?limit=30")]);
      setFavorites(favoriteResponse.items);
      setRecent(recentResponse.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "个人资料库加载失败。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const open = async (item: WorkspaceItem) => {
    try {
      await api("/recent-visits", { method: "POST", body: JSON.stringify(toPayload(item)) });
      openWorkspaceItem(item.target_view, item.target_id || item.entity_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "打开内容失败。");
    }
  };

  const remove = async (item: WorkspaceItem) => {
    try {
      await api<void>(`/favorites/${encodeURIComponent(item.entity_type)}/${encodeURIComponent(item.entity_id)}`, { method: "DELETE" });
      setFavorites((items) => items.filter((entry) => !(entry.entity_type === item.entity_type && entry.entity_id === item.entity_id)));
      showNotice("已取消收藏。", "success");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "取消收藏失败。");
    }
  };

  return <section id="personal-library-view" className="view is-active"><div className="personal-library-workspace">
    <header className="tool-page-header personal-library-header"><div><p className="tool-eyebrow">Personal Workspace</p><h1>收藏与最近访问</h1><p>保留常用知识库、工单和对话入口，减少重复查找。</p></div><button className="secondary-action" onClick={() => void load()}>刷新</button></header>
    {error && <p className="form-message is-error">{error}</p>}
    {loading ? <LoadingBlock label="正在加载个人工作项..." /> : <div className="personal-library-grid"><LibrarySection title="我的收藏" description="手动保存的重要知识、工单或对话。" count={favorites.length} items={favorites} empty="还没有收藏。可以从全局搜索结果中收藏常用内容。" actionLabel="取消收藏" onOpen={open} onAction={remove} /><LibrarySection title="最近访问" description="从搜索和个人入口打开过的内容。" count={recent.length} items={recent} empty="还没有访问记录。打开搜索结果后会显示在这里。" onOpen={open} /></div>}
  </div></section>;
}

function LibrarySection({ title, description, count, items, empty, actionLabel, onOpen, onAction }: { title: string; description: string; count: number; items: WorkspaceItem[]; empty: string; actionLabel?: string; onOpen: (item: WorkspaceItem) => void; onAction?: (item: WorkspaceItem) => void }) {
  return <section className="personal-library-panel"><div className="personal-library-panel-heading"><div><h2>{title}</h2><p>{description}</p></div><span className="activity-count">{count}</span></div>{items.length ? <div className="personal-item-list">{items.map((item) => <article className="personal-item" key={`${item.entity_type}-${item.entity_id}`}><button className="personal-item-open" onClick={() => void onOpen(item)}><div><strong>{item.title}</strong><span className={`workspace-item-type is-${item.entity_type.replace("_", "-")}`}>{kindLabels[item.entity_type] || "工作项"}</span></div><p>{item.subtitle}</p></button>{onAction && <button className="workspace-remove-button" aria-label={actionLabel} onClick={() => void onAction(item)}>移除</button>}</article>)}</div> : <EmptyState title={title === "我的收藏" ? "暂无收藏" : "暂无访问记录"} description={empty} />}</section>;
}

function toPayload(item: WorkspaceItem) {
  return { entity_type: item.entity_type, entity_id: item.entity_id, title: item.title, subtitle: item.subtitle, target_view: item.target_view, target_id: item.target_id, metadata_json: item.metadata_json };
}
