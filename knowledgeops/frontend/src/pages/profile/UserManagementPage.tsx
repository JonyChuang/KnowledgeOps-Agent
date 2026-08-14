import { useEffect, useState } from "react";

import { api } from "../../api/client";
import type { User, UserRole } from "../../api/types";
import { EmptyState, LoadingBlock, formatDate } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

const roleLabels: Record<UserRole, string> = { employee: "员工", service_desk: "服务台", admin: "管理员" };

export function UserManagementPage() {
  const currentUser = useAppStore((state) => state.user)!;
  const showNotice = useAppStore((state) => state.showNotice);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try { setUsers(await api<User[]>("/auth/users")); } catch (reason) { setError(reason instanceof Error ? reason.message : "用户列表加载失败。"); } finally { setLoading(false); }
  };

  useEffect(() => { void load(); }, []);

  const updateRole = async (user: User, role: UserRole) => {
    if (role === user.role) return;
    setUpdating(user.id);
    setError("");
    try {
      const updated = await api<User>(`/auth/users/${user.id}/role`, { method: "PATCH", body: JSON.stringify({ role }) });
      setUsers((items) => items.map((item) => item.id === updated.id ? updated : item));
      showNotice(`${updated.display_name} 的角色已更新。`, "success");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "角色更新失败。");
    } finally {
      setUpdating(null);
    }
  };

  return <section id="user-management-view" className="view is-active"><div className="user-management-workspace">
    <header className="tool-page-header"><div><p className="tool-eyebrow">Administration</p><h1>用户与权限</h1><p>为员工分配服务台或管理员角色。角色变更会在该用户下次请求时立即生效。</p></div><button className="secondary-action" onClick={() => void load()}>刷新</button></header>
    {error && <p className="form-message is-error">{error}</p>}
    <section className="user-management-panel" aria-live="polite"><div className="user-management-panel-heading"><div><h2>平台用户</h2><p>员工可提交和跟踪工单；服务台可处理队列；管理员可配置角色。</p></div><span className="activity-count">{users.length}</span></div>
      {loading ? <LoadingBlock label="正在加载用户..." /> : users.length ? users.map((user) => <div className="user-management-row" key={user.id}><div><strong>{user.display_name}</strong><p>{user.username} · 注册于 {formatDate(user.created_at)}</p></div><label className="user-role-control">角色<select value={user.role} disabled={updating === user.id || user.id === currentUser.id} onChange={(event) => void updateRole(user, event.target.value as UserRole)}>{(Object.keys(roleLabels) as UserRole[]).map((role) => <option key={role} value={role}>{roleLabels[role]}</option>)}</select></label></div>) : <EmptyState title="还没有用户" description="用户注册后会显示在这里。" />}
    </section>
  </div></section>;
}
