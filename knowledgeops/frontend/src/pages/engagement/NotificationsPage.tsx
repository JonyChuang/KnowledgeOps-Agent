import { useEffect, useState } from "react";

import { api } from "../../api/client";
import type { Notification, NotificationPage as NotificationResponse } from "../../api/types";
import { EmptyState, LoadingBlock, formatDate } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

export function NotificationsPage() {
  const openWorkspaceItem = useAppStore((state) => state.openWorkspaceItem);
  const showNotice = useAppStore((state) => state.showNotice);
  const [response, setResponse] = useState<NotificationResponse | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setResponse(await api<NotificationResponse>(`/notifications?unread_only=${unreadOnly}&limit=50&offset=0`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "通知加载失败。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [unreadOnly]);

  const open = async (notification: Notification) => {
    try {
      if (!notification.is_read) await api(`/notifications/${notification.id}/read`, { method: "POST" });
      openWorkspaceItem(notification.target_view, notification.entity_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "打开通知失败。");
    }
  };

  const readAll = async () => {
    try {
      await api("/notifications/read-all", { method: "POST" });
      showNotice("所有通知已标记为已读。", "success");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "操作失败。");
    }
  };

  return <section id="notifications-view" className="view is-active"><div className="notifications-workspace">
    <header className="tool-page-header notifications-header"><div><p className="tool-eyebrow">Notification Center</p><h1>通知中心</h1><p>查看与你有关的工单协作和资料索引动态，处理后可直接进入对应事项。</p></div></header>
    <section className="notifications-toolbar" aria-label="通知筛选"><div className="notification-filter-tabs" role="tablist"><button type="button" className={`notification-filter-tab ${!unreadOnly ? "is-active" : ""}`} onClick={() => setUnreadOnly(false)}>全部通知</button><button type="button" className={`notification-filter-tab ${unreadOnly ? "is-active" : ""}`} onClick={() => setUnreadOnly(true)}>未读</button></div><button className="secondary-action" disabled={!response?.unread_count} onClick={() => void readAll()}>全部标为已读</button></section>
    {error && <p className="form-message is-error">{error}</p>}
    <section className="notifications-panel" aria-live="polite"><div className="notifications-panel-heading"><div><h2>消息列表</h2><p>{loading ? "正在加载你的通知..." : unreadOnly ? "仅显示未读通知。" : "显示全部通知。"}</p></div><span className="activity-count">{response?.unread_count ?? 0}</span></div>
      {loading ? <LoadingBlock label="正在加载通知..." /> : response?.items.length ? <div className="notifications-list">{response.items.map((notification) => <button className={`notification-list-item ${notification.is_read ? "" : "is-unread"}`} key={notification.id} onClick={() => void open(notification)}><span className="notification-marker">知</span><div><div><strong>{notification.title}</strong><span className={`notification-type is-${notification.target_view === "tickets" ? "ticket" : "system"}`}>{notification.target_view === "tickets" ? "工单" : "系统"}</span></div><p>{notification.content}</p><time>{formatDate(notification.created_at)}</time></div>{!notification.is_read && <span className="notification-unread-dot" />}</button>)}</div> : <EmptyState title="暂时没有通知" description={unreadOnly ? "所有通知都已读。" : "新的工单进度和系统提醒会显示在这里。"} />}
    </section>
  </div></section>;
}
