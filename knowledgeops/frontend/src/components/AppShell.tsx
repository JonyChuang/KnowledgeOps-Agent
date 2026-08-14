import { useEffect, useState } from "react";
import {
  Bell,
  Bot,
  BookOpen,
  ChevronDown,
  FileSearch,
  LayoutDashboard,
  Library,
  LogOut,
  Network,
  PlusCircle,
  Search,
  ShieldCheck,
  TicketCheck,
  UserRound,
  UsersRound,
} from "lucide-react";

import { api } from "../api/client";
import type { NotificationPage, ViewId } from "../api/types";
import { useAppStore } from "../store/app-store";
import { ViewRouter } from "../pages/ViewRouter";

interface NavItem {
  view: ViewId;
  label: string;
  icon: typeof LayoutDashboard;
  visible?: (role: string) => boolean;
}

const navigation: Array<{ label: string; items: NavItem[] }> = [
  { label: "工作台", items: [
    { view: "dashboard", label: "我的工作台", icon: LayoutDashboard },
    { view: "agent", label: "智能助手", icon: Bot },
    { view: "search", label: "全局搜索", icon: Search },
  ] },
  { label: "工单协同", items: [
    { view: "tickets", label: "我提交的工单", icon: TicketCheck },
    { view: "create-ticket", label: "创建工单", icon: PlusCircle },
    { view: "service-desk", label: "待我处理", icon: ShieldCheck, visible: (role) => role === "service_desk" || role === "admin" },
  ] },
  { label: "知识与资料", items: [
    { view: "knowledge", label: "知识库", icon: Library },
    { view: "documents", label: "文档索引", icon: FileSearch },
    { view: "graph", label: "图谱检索", icon: Network },
  ] },
  { label: "个人与管理", items: [
    { view: "notifications", label: "通知中心", icon: Bell },
    { view: "personal-library", label: "收藏与最近访问", icon: BookOpen },
    { view: "user-management", label: "用户与权限", icon: UsersRound, visible: (role) => role === "admin" },
  ] },
];

export function AppShell() {
  const user = useAppStore((state) => state.user)!;
  const activeView = useAppStore((state) => state.activeView);
  const setActiveView = useAppStore((state) => state.setActiveView);
  const setUser = useAppStore((state) => state.setUser);
  const notice = useAppStore((state) => state.notice);
  const clearNotice = useAppStore((state) => state.clearNotice);
  const [accountOpen, setAccountOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    api<NotificationPage>("/notifications?limit=1&offset=0")
      .then((response) => setUnreadCount(response.unread_count))
      .catch(() => setUnreadCount(0));
  }, [activeView]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(clearNotice, 4200);
    return () => window.clearTimeout(timer);
  }, [notice, clearNotice]);

  const signOut = async () => {
    try {
      await api<void>("/auth/logout", { method: "POST" });
    } catch {
      // Clear client state even when an expired cookie cannot be revoked remotely.
    }
    setUser(null);
    setActiveView("dashboard");
  };

  return (
    <div className="app-shell react-app-shell">
      <header className="topbar react-topbar">
        <button className="react-brand" type="button" onClick={() => setActiveView("dashboard")} aria-label="返回工作台"><span>K</span><strong>KnowledgeOps</strong></button>
        <div className="topbar-actions">
          <span className="api-indicator">API 已连接</span>
          <button type="button" className="secondary-action" onClick={() => window.location.reload()}>刷新</button>
          <div className="account-menu">
            <button type="button" className="account-trigger" aria-expanded={accountOpen} onClick={() => setAccountOpen((open) => !open)}>
              <span className="account-avatar">{user.display_name.slice(0, 1).toUpperCase()}</span><span>{user.display_name}</span><ChevronDown size={16} />
            </button>
            {accountOpen && <div className="account-popover">
              <div className="account-summary"><span className="account-avatar">{user.display_name.slice(0, 1).toUpperCase()}</span><div><strong>{user.display_name}</strong><span>{user.username} · {user.role === "admin" ? "管理员" : user.role === "service_desk" ? "服务台" : "员工"}</span></div></div>
              <button type="button" onClick={() => { setAccountOpen(false); setActiveView("profile"); }}><UserRound size={16} />个人中心</button>
              <button type="button" onClick={signOut}><LogOut size={16} />退出登录</button>
            </div>}
          </div>
        </div>
      </header>
      <div className="workspace react-workspace">
        <aside className="react-sidebar" aria-label="主导航">
          {navigation.map((group) => {
            const entries = group.items.filter((item) => !item.visible || item.visible(user.role));
            if (!entries.length) return null;
            return <section className="nav-group react-nav-group" key={group.label}><p className="nav-group-label">{group.label}</p>{entries.map((item) => {
              return <button key={item.view} className={`nav-item ${activeView === item.view ? "is-active" : ""}`} type="button" onClick={() => setActiveView(item.view)}><span>{item.label}</span>{item.view === "notifications" && <b>{unreadCount}</b>}</button>;
            })}</section>;
          })}
        </aside>
        <main className="content react-content"><ViewRouter /></main>
      </div>
      {notice && <div className={`react-toast ${notice.tone}`} role="status">{notice.message}</div>}
    </div>
  );
}
