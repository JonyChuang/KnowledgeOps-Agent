import { useEffect, useState, type FormEvent } from "react";
import { CheckCircle2, MessageSquarePlus, RotateCcw } from "lucide-react";

import { api, query as toQuery } from "../../api/client";
import type { Ticket, TicketDetail, TicketPage, TicketStatus } from "../../api/types";
import { EmptyState, LoadingBlock, StatusPill, formatDate } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

const statusFilters: Array<{ value: TicketStatus | ""; label: string }> = [
  { value: "", label: "全部" },
  { value: "open", label: "待受理" },
  { value: "in_progress", label: "处理中" },
  { value: "awaiting_requester", label: "待我补充" },
  { value: "resolved", label: "已解决" },
  { value: "closed", label: "已关闭" },
];

const priorityLabels: Record<string, string> = { low: "低优先级", medium: "中优先级", high: "高优先级", urgent: "紧急" };
const impactLabels: Record<string, string> = { single_user: "单个员工", team: "影响团队", department: "影响部门", company: "影响全公司" };
const activityLabels: Record<string, string> = {
  "ticket.created": "已提交服务请求",
  "ticket.accepted": "已受理",
  "ticket.assigned": "已转派",
  "ticket.priority_changed": "优先级已调整",
  "ticket.escalated": "已升级",
  "requester.comment_added": "已补充信息",
  "ticket.status_changed": "状态已更新",
  "ticket.reopened": "已重新打开",
};

export function TicketsPage() {
  const user = useAppStore((state) => state.user)!;
  const routeTarget = useAppStore((state) => state.routeTarget);
  const clearRouteTarget = useAppStore((state) => state.clearRouteTarget);
  const showNotice = useAppStore((state) => state.showNotice);
  const [status, setStatus] = useState<TicketStatus | "">("");
  const [search, setSearch] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [page, setPage] = useState<TicketPage | null>(null);
  const [selected, setSelected] = useState<TicketDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState("");
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  const loadTickets = async (offset = 0) => {
    setLoading(true);
    setError("");
    try {
      const result = await api<TicketPage>(`/tickets?${toQuery({ status: status || undefined, query: appliedQuery, limit: 12, offset })}`);
      setPage(result);
      if (selected && !result.items.some((item) => item.id === selected.id)) setSelected(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "工单列表加载失败。");
    } finally {
      setLoading(false);
    }
  };

  const openTicket = async (ticketId: string) => {
    setLoadingDetail(true);
    setError("");
    try {
      setSelected(await api<TicketDetail>(`/tickets/${ticketId}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "工单详情加载失败。");
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => { void loadTickets(); }, [status, appliedQuery]);
  useEffect(() => {
    if (!routeTarget) return;
    void openTicket(routeTarget);
    clearRouteTarget();
  }, [routeTarget, clearRouteTarget]);

  const refreshDetail = async (detail: TicketDetail) => {
    setSelected(detail);
    await loadTickets(page?.offset ?? 0);
  };

  const submitComment = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || !comment.trim()) return;
    setSaving(true);
    setError("");
    try {
      await refreshDetail(await api<TicketDetail>(`/tickets/${selected.id}/comments`, {
        method: "POST",
        body: JSON.stringify({ content: comment.trim() }),
      }));
      setComment("");
      showNotice("补充信息已提交。", "success");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "补充信息提交失败。");
    } finally {
      setSaving(false);
    }
  };

  const confirmResolution = async () => {
    if (!selected) return;
    setSaving(true);
    setError("");
    try {
      await refreshDetail(await api<TicketDetail>(`/tickets/${selected.id}/confirm-resolution`, { method: "POST" }));
      showNotice("工单已确认关闭。", "success");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "操作失败。");
    } finally {
      setSaving(false);
    }
  };

  const reopen = async () => {
    if (!selected) return;
    const reason = window.prompt("请说明仍需继续处理的原因：");
    if (!reason?.trim()) return;
    setSaving(true);
    setError("");
    try {
      await refreshDetail(await api<TicketDetail>(`/tickets/${selected.id}/reopen`, {
        method: "POST",
        body: JSON.stringify({ reason: reason.trim() }),
      }));
      showNotice("工单已重新打开。", "success");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重开工单失败。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section id="tickets-view" className="view is-active">
      <div className="tickets-workspace">
        <header className="tickets-header">
          <div>
            <p className="tool-eyebrow">Service Desk</p>
            <h1>我提交的工单</h1>
            <p>只展示由当前账号提交的服务请求。处理人由服务台分配，不影响你跟踪处理进度。</p>
          </div>
          <label className="tickets-actor-field">
            <span>当前操作人</span>
            <div>
              <input value={user.display_name} readOnly />
              <button type="button" className="secondary-action" onClick={() => void loadTickets(page?.offset ?? 0)}>查看</button>
            </div>
          </label>
        </header>

        <section className="tickets-toolbar" aria-label="工单筛选">
          <div className="ticket-status-tabs" role="tablist">
            {statusFilters.map((item) => (
              <button key={item.value} type="button" className={`ticket-status-tab ${status === item.value ? "is-active" : ""}`} onClick={() => setStatus(item.value)}>{item.label}</button>
            ))}
          </div>
          <form className="ticket-search-form" onSubmit={(event) => { event.preventDefault(); setAppliedQuery(search.trim()); }}>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索标题或问题描述" />
            <button className="secondary-action">搜索</button>
          </form>
        </section>

        {error && <p className="form-message is-error">{error}</p>}
        <div className="tickets-layout">
          <section className="tickets-list-panel" aria-label="工单列表">
            <div className="tickets-list-heading">
              <div>
                <h2>工单列表</h2>
                <p>{loading ? "正在加载你提交的工单..." : `共找到 ${page?.total ?? 0} 张由当前账号提交的工单。`}</p>
              </div>
              <span className="activity-count">{page?.total ?? 0}</span>
            </div>
            {loading ? <LoadingBlock label="正在加载工单..." /> : page?.items.length ? (
              <div className="tickets-list">
                {page.items.map((ticket) => <TicketRow key={ticket.id} ticket={ticket} selected={selected?.id === ticket.id} onClick={() => void openTicket(ticket.id)} />)}
              </div>
            ) : <EmptyState title="没有匹配的工单" description="可以调整筛选条件，或从侧边栏创建一个新的服务请求。" />}
            {page && <div className="tickets-pagination">
              <button className="secondary-action" disabled={page.offset === 0} onClick={() => void loadTickets(Math.max(0, page.offset - page.limit))}>上一页</button>
              <span>{page.total ? `${page.offset + 1}-${Math.min(page.offset + page.limit, page.total)} / ${page.total}` : "0 条"}</span>
              <button className="secondary-action" disabled={page.offset + page.limit >= page.total} onClick={() => void loadTickets(page.offset + page.limit)}>下一页</button>
            </div>}
          </section>

          <aside className="ticket-preview-panel" aria-live="polite">
            {loadingDetail ? <LoadingBlock label="正在加载工单详情..." /> : selected ? (
              <TicketDetailView key={selected.id} ticket={selected} comment={comment} setComment={setComment} saving={saving} onComment={submitComment} onConfirm={() => void confirmResolution()} onReopen={() => void reopen()} />
            ) : (
              <div className="ticket-preview-empty">
                <span className="ticket-preview-symbol" aria-hidden="true">i</span>
                <strong>选择一张工单</strong>
                <p>从列表中选择后，可查看详情、处理进度和补充信息。</p>
              </div>
            )}
          </aside>
        </div>
      </div>
    </section>
  );
}

function TicketRow({ ticket, selected, onClick }: { ticket: Ticket; selected: boolean; onClick: () => void }) {
  return (
    <button type="button" className={`ticket-list-item ${selected ? "is-selected" : ""}`} onClick={onClick}>
      <div>
        <h3>{ticket.title}</h3>
        <p>{ticket.category || "通用服务"} · 更新于 {formatDate(ticket.updated_at)}</p>
      </div>
      <div className="ticket-list-meta">
        <StatusPill value={ticket.status} />
        <span className={`priority-label priority-${ticket.priority}`}>{priorityLabels[ticket.priority]} · {formatDate(ticket.updated_at)}</span>
      </div>
    </button>
  );
}

function TicketDetailView({ ticket, comment, setComment, saving, onComment, onConfirm, onReopen }: {
  ticket: TicketDetail;
  comment: string;
  setComment: (value: string) => void;
  saving: boolean;
  onComment: (event: FormEvent) => void;
  onConfirm: () => void;
  onReopen: () => void;
}) {
  return (
    <div className="ticket-preview">
      <header className="ticket-preview-header">
        <span className="ticket-preview-label">工单 #{ticket.id.slice(0, 8)}</span>
        <h2>{ticket.title}</h2>
        <div className="ticket-preview-status"><StatusPill value={ticket.status} /></div>
      </header>
      <dl className="ticket-preview-details">
        <div><dt>优先级</dt><dd>{priorityLabels[ticket.priority]}</dd></div>
        <div><dt>服务分类</dt><dd>{ticket.category || "通用服务"}</dd></div>
        <div><dt>影响范围</dt><dd>{impactLabels[ticket.impact]}</dd></div>
        <div><dt>当前处理人</dt><dd>{ticket.assignee || "等待服务台分派"}</dd></div>
        <div><dt>服务时限</dt><dd>{formatDate(ticket.sla_due_at)}</dd></div>
        <div><dt>提交时间</dt><dd>{formatDate(ticket.created_at)}</dd></div>
        <div className="ticket-preview-description"><dt>问题描述</dt><dd>{ticket.description}</dd></div>
      </dl>
      <RequesterWorkflow ticket={ticket} />
      {ticket.status === "resolved" && <div className="ticket-preview-actions">
        <button className="secondary-action" disabled={saving} onClick={onReopen}><RotateCcw size={16} />仍未解决</button>
        <button className="primary-action" disabled={saving} onClick={onConfirm}><CheckCircle2 size={16} />确认解决</button>
      </div>}
      <section className="ticket-timeline">
        <h3>处理时间线</h3>
        {ticket.activities.length ? <ol>{ticket.activities.map((activity) => (
          <li key={activity.id}>
            <span className="ticket-activity-type">{activityLabels[activity.event_type] || "处理动态"}</span>
            <time>{formatDate(activity.created_at)}</time>
            <strong>{activity.actor || "系统"}</strong>
            <p>{activity.content || "已记录一条工单处理动态。"}</p>
          </li>
        ))}</ol> : <p className="ticket-timeline-empty">暂时没有可展示的处理记录。</p>}
      </section>
      {ticket.status !== "closed" && <form className="ticket-comment-form" onSubmit={onComment}>
        <label>补充信息<textarea rows={3} value={comment} onChange={(event) => setComment(event.target.value)} maxLength={4000} placeholder="补充错误现象、发生时间或已尝试的处理方式" /></label>
        <button className="secondary-action" disabled={saving || !comment.trim()}><MessageSquarePlus size={16} />提交补充</button>
      </form>}
    </div>
  );
}

function RequesterWorkflow({ ticket }: { ticket: TicketDetail }) {
  const workflow = {
    open: {
      title: "等待服务台受理",
      description: "工单尚未分派。服务台领取后会开始处理，并在有更新时通知你。",
    },
    in_progress: {
      title: "服务台正在处理中",
      description: ticket.assignee ? `当前由 ${ticket.assignee} 处理。你可以补充信息，但不需要重复提交工单。` : "服务台正在处理此请求。",
    },
    awaiting_requester: {
      title: "等待你补充信息",
      description: "请在下方补充发生时间、错误截图或已尝试的操作；提交后工单会自动回到处理中。",
    },
    resolved: {
      title: "请确认处理结果",
      description: "若问题已解决，请确认关闭；若仍未解决，请说明原因并重新打开工单。",
    },
    closed: {
      title: "工单已关闭",
      description: "该请求已完成归档。如问题再次出现，请创建新的工单。",
    },
  }[ticket.status];

  return <section className={`ticket-requester-guidance is-${ticket.status}`}>
    <span>下一步</span>
    <strong>{workflow.title}</strong>
    <p>{workflow.description}</p>
  </section>;
}
