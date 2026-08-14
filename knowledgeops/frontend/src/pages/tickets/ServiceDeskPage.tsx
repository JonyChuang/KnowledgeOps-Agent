import { useEffect, useState } from "react";
import { ArrowUpRight, CheckCircle2, CircleAlert, ClipboardCheck, SendHorizontal, UserRoundPlus } from "lucide-react";

import { api, query as toQuery } from "../../api/client";
import type { TicketDetail, TicketPage, TicketPriority, TicketStatus } from "../../api/types";
import { EmptyState, LoadingBlock, StatusPill, formatDate } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

type Scope = "all" | "mine" | "unassigned";
type ActionName = "accept" | "assign" | "request-information" | "priority" | "escalate" | "resolve";

const scopes: Array<{ value: Scope; label: string }> = [
  { value: "mine", label: "待我处理" },
  { value: "unassigned", label: "待领取" },
  { value: "all", label: "全部队列" },
];

const actionLabels: Record<ActionName, string> = {
  accept: "领取工单",
  assign: "转派处理人",
  "request-information": "请求补充",
  priority: "调整优先级",
  escalate: "升级工单",
  resolve: "标记解决",
};

export function ServiceDeskPage() {
  const user = useAppStore((state) => state.user)!;
  const routeTarget = useAppStore((state) => state.routeTarget);
  const clearRouteTarget = useAppStore((state) => state.clearRouteTarget);
  const showNotice = useAppStore((state) => state.showNotice);
  const [scope, setScope] = useState<Scope>("mine");
  const [status, setStatus] = useState<TicketStatus | "">("");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [page, setPage] = useState<TicketPage | null>(null);
  const [selected, setSelected] = useState<TicketDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [action, setAction] = useState<ActionName | null>(null);
  const [input, setInput] = useState("");
  const [choice, setChoice] = useState("high");
  const [saving, setSaving] = useState(false);

  const loadQueue = async (offset = 0) => {
    setLoading(true);
    setError("");
    try {
      const result = await api<TicketPage>(`/service-desk/tickets?${toQuery({ scope, status: status || undefined, query: appliedSearch, limit: 12, offset })}`);
      setPage(result);
      if (selected && !result.items.some((item) => item.id === selected.id)) setSelected(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "待处理队列加载失败。");
    } finally {
      setLoading(false);
    }
  };

  const openTicket = async (id: string) => {
    setDetailLoading(true);
    setError("");
    try {
      setSelected(await api<TicketDetail>(`/service-desk/tickets/${id}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "工单详情加载失败。");
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => { void loadQueue(); }, [scope, status, appliedSearch]);
  useEffect(() => {
    if (!routeTarget) return;
    void openTicket(routeTarget);
    clearRouteTarget();
  }, [routeTarget, clearRouteTarget]);

  const start = (next: ActionName) => {
    if (!selected) return;
    if (next === "accept") {
      void runAction("accept");
      return;
    }
    setInput("");
    setChoice(next === "escalate" ? "team_lead" : "high");
    setAction(next);
  };

  const runAction = async (next: ActionName) => {
    if (!selected) return;
    setSaving(true);
    setError("");
    try {
      let body: Record<string, string> | undefined;
      if (next === "assign") body = { assignee: input.trim() };
      if (next === "request-information" || next === "resolve") body = { reason: input.trim() };
      if (next === "priority") body = { priority: choice, reason: input.trim() };
      if (next === "escalate") body = { level: choice, reason: input.trim() };
      if (body && Object.values(body).some((value) => !value)) throw new Error("请填写完整的处理说明。");
      const detail = await api<TicketDetail>(`/service-desk/tickets/${selected.id}/${next}`, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      });
      setSelected(detail);
      setAction(null);
      if (next === "accept" && scope !== "mine") {
        setScope("mine");
      } else {
        await loadQueue(page?.offset ?? 0);
      }
      showNotice(`${actionLabels[next]}已完成。`, "success");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "工单操作失败。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section id="service-desk-view" className="view is-active">
      <div className="tickets-workspace service-desk-workspace">
        <header className="tickets-header">
          <div>
            <p className="tool-eyebrow">Service Operations</p>
            <h1>待我处理</h1>
            <p>领取待受理请求，协同分派，并将处理过程完整记录在工单时间线中。</p>
          </div>
          <label className="tickets-actor-field">
            <span>当前处理人</span>
            <div>
              <input value={user.display_name} readOnly />
              <button className="secondary-action" type="button" onClick={() => void loadQueue(page?.offset ?? 0)}>查看</button>
            </div>
          </label>
        </header>

        <section className="tickets-toolbar" aria-label="待我处理筛选">
          <div className="ticket-status-tabs" role="tablist">
            {scopes.map((item) => <button key={item.value} type="button" className={`ticket-status-tab ${scope === item.value ? "is-active" : ""}`} onClick={() => setScope(item.value)}>{item.label}</button>)}
          </div>
          <form className="ticket-search-form" onSubmit={(event) => { event.preventDefault(); setAppliedSearch(search.trim()); }}>
            <select value={status} onChange={(event) => setStatus(event.target.value as TicketStatus | "")}>
              <option value="">全部状态</option>
              <option value="open">待受理</option>
              <option value="in_progress">处理中</option>
              <option value="awaiting_requester">待补充</option>
              <option value="resolved">已解决</option>
            </select>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索标题、描述或申请人" />
            <button className="secondary-action">搜索</button>
          </form>
        </section>

        {error && <p className="form-message is-error">{error}</p>}
        <div className="tickets-layout">
          <section className="tickets-list-panel" aria-label="待处理工单队列">
            <div className="tickets-list-heading">
              <div><h2>处理队列</h2><p>{loading ? "正在加载待处理工单..." : `当前队列共 ${page?.total ?? 0} 张工单。`}</p></div>
              <span className="activity-count">{page?.total ?? 0}</span>
            </div>
            {loading ? <LoadingBlock label="正在加载队列..." /> : page?.items.length ? <div className="tickets-list">
              {page.items.map((ticket) => <button key={ticket.id} className={`ticket-list-item ${selected?.id === ticket.id ? "is-selected" : ""}`} onClick={() => void openTicket(ticket.id)}>
                <div><h3>{ticket.title}</h3><p>{ticket.requester} · {ticket.assignee ? `处理人：${ticket.assignee}` : "待领取"}</p></div>
                <div className="ticket-list-meta"><StatusPill value={ticket.status} /><span>{formatDate(ticket.updated_at)}</span></div>
              </button>)}
            </div> : <EmptyState title="当前队列为空" description="调整范围或筛选条件后再试。" />}
            {page && <div className="tickets-pagination">
              <button className="secondary-action" disabled={!page.offset} onClick={() => void loadQueue(Math.max(0, page.offset - page.limit))}>上一页</button>
              <span>{page.total} 条</span>
              <button className="secondary-action" disabled={page.offset + page.limit >= page.total} onClick={() => void loadQueue(page.offset + page.limit)}>下一页</button>
            </div>}
          </section>

          <aside className="ticket-preview-panel" aria-live="polite">
            {detailLoading ? <LoadingBlock label="正在加载工单..." /> : selected ? <ServiceDeskDetail key={selected.id} ticket={selected} operator={user.username} onAction={start} /> : <div className="ticket-preview-empty"><span className="ticket-preview-symbol">i</span><strong>选择一张服务请求</strong><p>待领取工单需要先受理；只有当前处理人才能继续处理或标记解决。</p></div>}
          </aside>
        </div>
      </div>
      {action && selected && <ActionDialog action={action} input={input} choice={choice} saving={saving} onInput={setInput} onChoice={setChoice} onClose={() => setAction(null)} onSubmit={() => void runAction(action)} />}
    </section>
  );
}

function ServiceDeskDetail({ ticket, operator, onAction }: { ticket: TicketDetail; operator: string; onAction: (action: ActionName) => void }) {
  const isAssignee = ticket.assignee === operator;
  const canAccept = ticket.status === "open" && (!ticket.assignee || isAssignee);
  const canAssign = ticket.status === "open" || (ticket.status === "in_progress" && isAssignee);
  const canManageActive = ticket.status === "in_progress" && isAssignee;
  const stateMessage = ticket.status === "open"
    ? ticket.assignee ? `已指派给 ${ticket.assignee}，等待对方开始处理。` : "工单尚未领取，可以由你受理，或先指派给其他服务台人员。"
    : ticket.status === "in_progress"
      ? isAssignee ? "你是当前处理人，可以推进处理、请求补充或标记解决。" : `当前由 ${ticket.assignee || "其他服务台人员"} 处理。`
      : ticket.status === "awaiting_requester"
        ? "已向申请人请求补充信息，收到补充后会自动回到处理中。"
        : ticket.status === "resolved"
          ? "已等待申请人确认处理结果。"
          : "工单已关闭，保留处理记录供后续追溯。";
  return <div className="ticket-preview">
    <header className="ticket-preview-header"><span className="ticket-preview-label">工单 #{ticket.id.slice(0, 8)} · {ticket.requester}</span><h2>{ticket.title}</h2><div className="ticket-preview-status"><StatusPill value={ticket.status} /></div></header>
    <dl className="ticket-preview-details">
      <div><dt>当前处理人</dt><dd>{ticket.assignee || "尚未领取"}</dd></div>
      <div><dt>优先级</dt><dd>{ticket.priority}</dd></div>
      <div><dt>服务时限</dt><dd>{formatDate(ticket.sla_due_at)}</dd></div>
      <div><dt>升级等级</dt><dd>{ticket.escalation_level === "none" ? "未升级" : ticket.escalation_level}</dd></div>
      <div className="ticket-preview-description"><dt>问题描述</dt><dd>{ticket.description}</dd></div>
    </dl>
    <div className="service-actions"><h3>处理操作</h3><p>{stateMessage}</p><div>
      {canAccept && <button className="primary-action" onClick={() => onAction("accept")}><ClipboardCheck size={16} />领取并开始处理</button>}
      {canAssign && <button className="secondary-action" onClick={() => onAction("assign")}><UserRoundPlus size={16} />{ticket.status === "open" ? "指派处理人" : "转派"}</button>}
      {canManageActive && <>
        <button className="secondary-action" onClick={() => onAction("request-information")}><SendHorizontal size={16} />请求补充</button>
        <button className="secondary-action" onClick={() => onAction("priority")}><CircleAlert size={16} />调整优先级</button>
        <button className="secondary-action" onClick={() => onAction("escalate")}><ArrowUpRight size={16} />升级</button>
        <button className="primary-action" onClick={() => onAction("resolve")}><CheckCircle2 size={16} />标记解决</button>
      </>}
    </div></div>
    <section className="ticket-timeline"><h3>处理时间线</h3><ol>{ticket.activities.map((activity) => <li key={activity.id}><strong>{activity.actor}</strong><time>{formatDate(activity.created_at)}</time><p>{activity.content || activity.event_type}</p></li>)}</ol></section>
  </div>;
}

function ActionDialog({ action, input, choice, saving, onInput, onChoice, onClose, onSubmit }: {
  action: ActionName;
  input: string;
  choice: string;
  saving: boolean;
  onInput: (value: string) => void;
  onChoice: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  const requiresInput = action !== "accept";
  return <div className="react-modal-backdrop" onMouseDown={onClose}><section className="react-modal action-dialog" onMouseDown={(event) => event.stopPropagation()}>
    <header><h2>{actionLabels[action]}</h2></header>
    {action === "assign" && <label>处理人<input autoFocus value={input} onChange={(event) => onInput(event.target.value)} placeholder="输入服务人员账号或姓名" /></label>}
    {action === "priority" && <label>新优先级<select value={choice} onChange={(event) => onChoice(event.target.value as TicketPriority)}><option value="low">低</option><option value="medium">中</option><option value="high">高</option><option value="urgent">紧急</option></select></label>}
    {action === "escalate" && <label>升级等级<select value={choice} onChange={(event) => onChoice(event.target.value)}><option value="team_lead">组长</option><option value="manager">负责人</option></select></label>}
    {requiresInput && action !== "assign" && <label>处理说明<textarea autoFocus rows={4} value={input} onChange={(event) => onInput(event.target.value)} placeholder="说明处理原因、解决方式或需要补充的信息" /></label>}
    <div className="modal-actions"><button className="secondary-action" onClick={onClose}>取消</button><button className="primary-action" disabled={saving || (requiresInput && !input.trim())} onClick={onSubmit}>{saving ? "正在提交..." : "确认操作"}</button></div>
  </section></div>;
}
