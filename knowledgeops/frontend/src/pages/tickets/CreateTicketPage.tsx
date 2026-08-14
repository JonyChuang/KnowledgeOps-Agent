import { useMemo, useState, type FormEvent } from "react";
import { Send } from "lucide-react";

import { api } from "../../api/client";
import type { TicketImpact, TicketPriority } from "../../api/types";
import { useAppStore } from "../../store/app-store";

export function CreateTicketPage() {
  const user = useAppStore((state) => state.user)!;
  const knowledgeBases = useAppStore((state) => state.knowledgeBases);
  const setActiveView = useAppStore((state) => state.setActiveView);
  const showNotice = useAppStore((state) => state.showNotice);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("network");
  const [impact, setImpact] = useState<TicketImpact>("single_user");
  const [priority, setPriority] = useState<TicketPriority>("medium");
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("");
  const [checked, setChecked] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const suggestions = useMemo(() => {
    if (!checked) return [];
    const items = [
      "确认错误提示、发生时间和已尝试的处理方式已写入描述。",
      "按实际受影响人数选择影响范围和紧急程度。",
    ];
    if (knowledgeBaseId) items.unshift("已选择参考知识库，可先核对是否已有可用的排查说明。");
    if (title.trim().toLowerCase().includes("vpn")) items.push("VPN 问题建议补充网络是否正常、是否已重新登录客户端。" );
    return items;
  }, [checked, knowledgeBaseId, title]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api("/tickets", {
        method: "POST",
        body: JSON.stringify({ title, description, category, impact, priority }),
      });
      showNotice("工单已创建，服务台将尽快处理。", "success");
      setActiveView("tickets");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建工单失败。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section id="create-ticket-view" className="view is-active">
      <div className="create-ticket-workspace">
        <header className="tool-page-header">
          <div>
            <p className="tool-eyebrow">Service Request</p>
            <h1>创建工单</h1>
            <p>提交前先查看相关知识资料和你历史上提交过的相似请求，避免重复提单。</p>
          </div>
        </header>

        <div className="create-ticket-layout">
          <form className="create-ticket-form" onSubmit={submit}>
            <div className="create-ticket-form-heading">
              <h2>描述你的服务请求</h2>
              <p>信息越完整，服务团队越容易判断影响范围和处理优先级。</p>
            </div>
            <label>
              当前操作人
              <input value={user.display_name} readOnly />
            </label>
            <div className="create-ticket-field-row">
              <label>
                服务分类
                <select value={category} onChange={(event) => setCategory(event.target.value)}>
                  <option value="network">网络与 VPN</option>
                  <option value="account">账号与权限</option>
                  <option value="device">办公设备</option>
                  <option value="software">软件申请</option>
                  <option value="data_access">数据访问</option>
                  <option value="general">其他服务</option>
                </select>
              </label>
              <label>
                影响范围
                <select value={impact} onChange={(event) => setImpact(event.target.value as TicketImpact)}>
                  <option value="single_user">仅影响我</option>
                  <option value="team">影响团队</option>
                  <option value="department">影响部门</option>
                  <option value="company">影响全公司</option>
                </select>
              </label>
            </div>
            <label>
              问题标题
              <input value={title} onChange={(event) => setTitle(event.target.value)} minLength={2} maxLength={200} placeholder="例如：无法连接企业 VPN" required />
            </label>
            <label>
              问题描述
              <textarea rows={6} value={description} onChange={(event) => setDescription(event.target.value)} maxLength={20_000} placeholder="请说明发生时间、受影响对象、错误提示，以及已经尝试过的处理方式。" required />
            </label>
            <label className="create-ticket-priority-field">
              紧急程度
              <select value={priority} onChange={(event) => setPriority(event.target.value as TicketPriority)}>
                <option value="low">低：不影响日常工作</option>
                <option value="medium">中：影响部分工作</option>
                <option value="high">高：主要工作受阻</option>
                <option value="urgent">紧急：业务中断或广泛影响</option>
              </select>
            </label>
            <div className="create-ticket-form-footer">
              <span>附件功能将在文件存储与病毒扫描接入后开放。</span>
              <button className="primary-action" disabled={saving}><Send size={17} />{saving ? "正在提交..." : "提交工单"}</button>
            </div>
            {error && <p className="form-message is-error">{error}</p>}
          </form>

          <aside className="create-ticket-assist" aria-live="polite">
            <section>
              <div className="create-ticket-assist-heading">
                <div>
                  <h2>提交前建议</h2>
                  <p>填写标题和描述后，检查可用资料与填写完整性。</p>
                </div>
                <button className="secondary-action" type="button" onClick={() => setChecked(true)}>检查建议</button>
              </div>
              <label>
                参考知识库（可选）
                <select value={knowledgeBaseId} onChange={(event) => setKnowledgeBaseId(event.target.value)}>
                  <option value="">请选择知识库</option>
                  {knowledgeBases.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </label>
              <div className="create-ticket-result-list">
                {suggestions.length ? suggestions.map((suggestion) => <div className="create-ticket-result" key={suggestion}><p>{suggestion}</p></div>) : <p className="create-ticket-empty">点击“检查建议”后显示提交前提醒。</p>}
              </div>
            </section>
            <section>
              <h2>相似历史工单</h2>
              <div className="create-ticket-result-list">
                <p className="create-ticket-empty">提交前检查会在后续版本中结合检索结果显示相似历史请求。</p>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </section>
  );
}
