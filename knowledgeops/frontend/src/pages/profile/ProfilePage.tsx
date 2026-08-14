import { useState, type FormEvent } from "react";
import { KeyRound } from "lucide-react";

import { api } from "../../api/client";
import type { User } from "../../api/types";
import { Modal, formatDate } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

export function ProfilePage() {
  const user = useAppStore((state) => state.user)!;
  const setUser = useAppStore((state) => state.setUser);
  const showNotice = useAppStore((state) => state.showNotice);
  const [displayName, setDisplayName] = useState(user.display_name);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [error, setError] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault();
    setProfileSaving(true);
    setError("");
    try {
      const updated = await api<User>("/auth/me", { method: "PATCH", body: JSON.stringify({ display_name: displayName.trim() }) });
      setUser(updated);
      showNotice("个人信息已更新。", "success");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "个人信息保存失败。");
    } finally {
      setProfileSaving(false);
    }
  };

  const changePassword = async (event: FormEvent) => {
    event.preventDefault();
    setPasswordSaving(true);
    setError("");
    try {
      await api<void>("/auth/me/password", { method: "POST", body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) });
      setCurrentPassword("");
      setNewPassword("");
      setPasswordOpen(false);
      showNotice("密码已更新，其他设备会自动退出。", "success");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "密码更新失败。");
    } finally {
      setPasswordSaving(false);
    }
  };

  const role = user.role === "admin" ? "管理员" : user.role === "service_desk" ? "服务台" : "员工";
  return <section id="profile-view" className="view is-active"><div className="profile-page">
    <header className="profile-cover" aria-hidden="true" />
    <section className="profile-card" aria-labelledby="profile-title">
      <div className="profile-identity"><span className="profile-avatar" aria-hidden="true">{user.display_name.slice(0, 1).toUpperCase()}</span><div><p className="profile-eyebrow">个人中心</p><h1 id="profile-title">账户信息</h1><p className="profile-account-summary">{user.username} · {role}</p></div></div>
      <form className="profile-details" onSubmit={saveProfile}>
        <div className="profile-detail-row"><div><span className="profile-detail-label">显示名称</span><span className="profile-detail-help">用于工作台、对话和工单中的展示</span></div><div className="profile-edit-control"><input value={displayName} onChange={(event) => setDisplayName(event.target.value)} minLength={2} maxLength={80} required /><button className="secondary-action" disabled={profileSaving || displayName.trim() === user.display_name}>{profileSaving ? "正在保存..." : "保存"}</button></div></div>
        <div className="profile-detail-row"><span className="profile-detail-label">账号</span><strong>{user.username}</strong></div>
        <div className="profile-detail-row"><span className="profile-detail-label">角色</span><strong>{role}</strong></div>
        <div className="profile-detail-row"><span className="profile-detail-label">注册时间</span><strong>{formatDate(user.created_at)}</strong></div>
        <div className="profile-detail-row"><div><span className="profile-detail-label">密码</span><span className="profile-detail-help">定期更换密码有助于保护账户安全</span></div><button className="secondary-action" type="button" onClick={() => setPasswordOpen(true)}>修改密码</button></div>
        {error && <p className="form-message is-error">{error}</p>}
      </form>
    </section>
    {passwordOpen && <Modal title="修改密码" onClose={() => setPasswordOpen(false)}><form className="react-form" onSubmit={changePassword}><label>当前密码<input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} minLength={8} required autoComplete="current-password" /></label><label>新密码<input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} minLength={8} maxLength={128} required autoComplete="new-password" /></label><div className="modal-actions"><button type="button" className="secondary-action" onClick={() => setPasswordOpen(false)}>取消</button><button className="primary-action" disabled={passwordSaving || !currentPassword || !newPassword}><KeyRound size={16} />{passwordSaving ? "正在更新..." : "更新密码"}</button></div></form></Modal>}
  </div></section>;
}
