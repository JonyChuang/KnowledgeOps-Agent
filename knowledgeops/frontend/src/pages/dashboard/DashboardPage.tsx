import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

import { api } from "../../api/client";
import type { Dashboard } from "../../api/types";
import { EmptyState, LoadingBlock, StatusPill, formatDate } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

export function DashboardPage() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const setActiveView = useAppStore((state) => state.setActiveView);
  const openWorkspaceItem = useAppStore((state) => state.openWorkspaceItem);
  const setKnowledgeBases = useAppStore((state) => state.setKnowledgeBases);

  const load = async () => {
    setError("");
    try {
      const response = await api<Dashboard>("/dashboard");
      setDashboard(response);
      setKnowledgeBases(response.knowledge_bases);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "工作台加载失败。");
    }
  };

  useEffect(() => { void load(); }, []);
  if (!dashboard && !error) return <LoadingBlock label="正在加载工作台..." />;
  if (!dashboard) return <EmptyState title="工作台暂时无法加载" description={error} action={<button className="secondary-action" onClick={() => void load()}><RefreshCw size={16} />重试</button>} />;

  const activeTickets = dashboard.tickets.open_count + dashboard.tickets.in_progress_count;
  const metrics = [
    ["待受理", dashboard.tickets.open_count, "我提交后等待响应"],
    ["处理中", dashboard.tickets.in_progress_count, "正在由服务团队处理"],
    ["待关注索引", dashboard.indexing.pending_count, "资料正在进入检索库"],
    ["索引失败", dashboard.indexing.failed_count, "需要检查资料或重新提交"],
  ] as const;

  return (
    <section id="dashboard-view" className="view is-active">
      <div className="dashboard-workspace">
        <section className="dashboard-overview" aria-label="工作概览">
          <article className="dashboard-highlight">
            <div>
              <p>你好，<strong>{dashboard.actor}</strong></p>
              <h2>{activeTickets ? `你有 ${activeTickets} 项工单正在等待跟进。` : "今天先从处理中的事项开始。"}</h2>
              <span>已有 {dashboard.indexing.ready_count} 份资料可供 Agent 检索。</span>
            </div>
            <div className="dashboard-highlight-actions">
              <button className="primary-action" onClick={() => setActiveView("agent")}>询问 Agent</button>
              <button className="secondary-action" onClick={() => setActiveView("knowledge")}>查看知识库</button>
            </div>
          </article>
          <div className="dashboard-metric-grid">
            {metrics.map(([label, value, description], index) => (
              <article className={`dashboard-metric ${index === 3 ? "dashboard-metric-alert" : ""}`} key={label}>
                <span className="dashboard-metric-label">{label}</span>
                <strong>{value}</strong>
                <small>{description}</small>
              </article>
            ))}
          </div>
        </section>

        <div className="dashboard-content-grid">
          <section className="dashboard-panel dashboard-ticket-panel">
            <div className="dashboard-panel-heading">
              <div><h2>最近工单</h2><p>只显示由当前操作人创建的工单。</p></div>
              <span className="activity-count">{dashboard.recent_tickets.length}</span>
            </div>
            <div className="dashboard-ticket-list">
              {dashboard.recent_tickets.length ? dashboard.recent_tickets.map((ticket) => (
                <button className="dashboard-ticket-item" key={ticket.id} onClick={() => openWorkspaceItem("tickets", ticket.id)}>
                  <div><div className="dashboard-ticket-title-row"><h3>{ticket.title}</h3><StatusPill value={ticket.status} /></div><p>{ticket.priority} 优先级 · 更新于 {formatDate(ticket.updated_at)}</p></div>
                </button>
              )) : <p className="dashboard-empty-state">还没有工单。</p>}
            </div>
            <button className="dashboard-text-action" onClick={() => setActiveView("agent")}>通过 Agent 查询或创建工单</button>
          </section>

          <section className="dashboard-panel dashboard-knowledge-panel">
            <div className="dashboard-panel-heading">
              <div><h2>常用知识库</h2><p>进入资料库继续查看、上传或发起检索。</p></div>
              <span className="activity-count">{dashboard.knowledge_bases.length}</span>
            </div>
            <div className="dashboard-knowledge-list">
              {dashboard.knowledge_bases.length ? dashboard.knowledge_bases.slice(0, 4).map((knowledgeBase) => (
                <button className="dashboard-knowledge-item" key={knowledgeBase.id} onClick={() => openWorkspaceItem("knowledge", knowledgeBase.id)}>
                  <span className="dashboard-knowledge-badge">{knowledgeBase.name.slice(0, 1).toUpperCase()}</span>
                  <span><strong>{knowledgeBase.name}</strong><small>{knowledgeBase.description || knowledgeBase.department}</small></span>
                </button>
              )) : <p className="dashboard-empty-state">尚未创建知识库。</p>}
            </div>
            <button className="dashboard-text-action" onClick={() => setActiveView("knowledge")}>管理全部知识库</button>
          </section>
        </div>

        <div className="dashboard-content-grid dashboard-lower-grid">
          <section className="dashboard-panel">
            <div className="dashboard-panel-heading"><div><h2>索引健康</h2><p>共享知识资料的处理情况。</p></div></div>
            <dl className="dashboard-index-summary">
              <div><dt>知识库</dt><dd>{dashboard.indexing.knowledge_base_count}</dd></div>
              <div><dt>资料总数</dt><dd>{dashboard.indexing.document_count}</dd></div>
              <div><dt>已就绪</dt><dd>{dashboard.indexing.ready_count}</dd></div>
            </dl>
            <button className="dashboard-text-action" onClick={() => setActiveView("documents")}>前往文档索引</button>
          </section>
          <section className="dashboard-panel">
            <div className="dashboard-panel-heading">
              <div><h2>本次会话</h2><p>当前操作人的近期 Agent 对话。</p></div>
              <span className="activity-count">{dashboard.recent_conversations.length}</span>
            </div>
            <div className="dashboard-conversation-list">
              {dashboard.recent_conversations.length ? dashboard.recent_conversations.slice(0, 3).map((conversation) => (
                <button className="dashboard-conversation-item" key={conversation.id} onClick={() => openWorkspaceItem("agent", conversation.id)}>
                  <strong>{conversation.title}</strong><span>{conversation.last_message_preview || "继续与 Agent 对话"}</span>
                </button>
              )) : <p className="dashboard-empty-state">还没有会话。</p>}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}
