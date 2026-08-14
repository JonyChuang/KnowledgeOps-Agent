import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import { Check, CirclePlus, Send, X } from "lucide-react";

import { api } from "../../api/client";
import type { AgentMessage, AgentTurn, ConversationDetail, ConversationSummary } from "../../api/types";
import { LoadingBlock } from "../../components/ui";
import { useAppStore } from "../../store/app-store";

interface ConversationListResponse {
  items: ConversationSummary[];
}

const suggestions = [
  "总结工程规范",
  "查看未关闭工单",
  "创建 VPN 工单",
  "获取排查建议",
];

export function AgentPage() {
  const user = useAppStore((state) => state.user)!;
  const knowledgeBases = useAppStore((state) => state.knowledgeBases);
  const setKnowledgeBases = useAppStore((state) => state.setKnowledgeBases);
  const showNotice = useAppStore((state) => state.showNotice);
  const routeTarget = useAppStore((state) => state.routeTarget);
  const clearRouteTarget = useAppStore((state) => state.clearRouteTarget);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [active, setActive] = useState<ConversationDetail | null>(null);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [feedbackIds, setFeedbackIds] = useState<Set<string>>(new Set());
  const [feedbackLoading, setFeedbackLoading] = useState<string | null>(null);

  const loadConversations = async () => {
    const result = await api<ConversationListResponse>("/agent/conversations");
    setConversations(result.items);
  };

  const loadKnowledgeBases = async () => {
    if (knowledgeBases.length) return;
    const items = await api<typeof knowledgeBases>("/knowledge-bases");
    setKnowledgeBases(items);
  };

  const openConversation = async (conversationId: string) => {
    setError("");
    try {
      const detail = await api<ConversationDetail>(`/agent/conversations/${conversationId}`);
      setActive(detail);
      setKnowledgeBaseId(detail.knowledge_base_id ?? "");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "会话加载失败。");
    }
  };

  useEffect(() => {
    Promise.all([loadConversations(), loadKnowledgeBases()])
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Agent 初始化失败。"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!routeTarget) return;
    void openConversation(routeTarget);
    clearRouteTarget();
  }, [routeTarget, clearRouteTarget]);

  const send = async (event: FormEvent) => {
    event.preventDefault();
    const userMessage = message.trim();
    if (!userMessage || sending) return;

    const conversationId = active?.id || undefined;
    const sentAt = new Date().toISOString();
    const optimisticMessage: AgentMessage = {
      id: `optimistic-${crypto.randomUUID()}`,
      role: "user",
      content: userMessage,
      thread_id: null,
      status: "completed",
      created_at: sentAt,
      citations: [],
      pending_action: null,
      created_ticket_id: null,
      ticket_ids: [],
      error: null,
    };

    setSending(true);
    setError("");
    setMessage("");
    setActive((current) => {
      if (current) return { ...current, messages: [...current.messages, optimisticMessage] };
      return {
        id: "",
        title: userMessage.slice(0, 60),
        updated_at: sentAt,
        message_count: 1,
        last_message_preview: userMessage,
        actor: user.display_name,
        knowledge_base_id: knowledgeBaseId || null,
        messages: [optimisticMessage],
      };
    });
    try {
      const turn = await api<AgentTurn>("/agent/turns", {
        method: "POST",
        body: JSON.stringify({
          user_message: userMessage,
          conversation_id: conversationId,
          knowledge_base_id: knowledgeBaseId || undefined,
        }),
      });
      await loadConversations();
      if (turn.conversation_id) await openConversation(turn.conversation_id);
      if (turn.status === "failed") setError(turn.error || "Agent 暂时无法完成请求。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "发送失败。");
      setMessage(userMessage);
      setActive((current) => current ? {
        ...current,
        messages: current.messages.filter((item) => item.id !== optimisticMessage.id),
      } : current);
    } finally {
      setSending(false);
    }
  };

  const submitOnEnter = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  };

  const confirm = async (threadId: string, approved: boolean) => {
    try {
      const turn = await api<AgentTurn>(`/agent/turns/${threadId}/confirmation`, {
        method: "POST",
        body: JSON.stringify({ approved }),
      });
      if (turn.conversation_id) await openConversation(turn.conversation_id);
      await loadConversations();
      showNotice(approved ? "工单已确认创建。" : "已取消创建工单。", "success");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "确认操作失败。");
    }
  };

  const submitFeedback = async (messageId: string, feedbackType: "helpful" | "unhelpful") => {
    const comment = feedbackType === "unhelpful"
      ? window.prompt("请简要说明问题，便于后续维护知识库：", "")
      : "";
    if (comment === null) return;

    setFeedbackLoading(messageId);
    try {
      await api(`/agent-messages/${messageId}/feedback`, {
        method: "POST",
        body: JSON.stringify({ feedback_type: feedbackType, comment: comment.trim() }),
      });
      setFeedbackIds((current) => new Set(current).add(messageId));
      showNotice("反馈已记录。", "success");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "反馈提交失败。");
    } finally {
      setFeedbackLoading(null);
    }
  };

  if (loading) return <LoadingBlock label="正在加载 Agent 会话..." />;

  return (
    <section id="agent-view" className="view is-active">
      <div className="agent-workspace react-agent-page">
        <aside className="conversation-sidebar" aria-label="对话列表">
          <button
            className="new-chat-button"
            type="button"
            onClick={() => {
              setActive(null);
              setMessage("");
              setError("");
            }}
          >
            <CirclePlus size={18} />新对话
          </button>
          <div className="conversation-list-header">
            <span>最近对话</span>
            <span className="conversation-count">{conversations.length}</span>
          </div>
          <div className="conversation-list">
            {conversations.length ? conversations.map((conversation) => (
              <button
                key={conversation.id}
                className={`conversation-item ${active?.id === conversation.id ? "is-active" : ""}`}
                type="button"
                onClick={() => void openConversation(conversation.id)}
              >
                <strong>{conversation.title}</strong>
                <span>{conversation.last_message_preview || "等待输入消息"}</span>
              </button>
            )) : <p className="conversation-empty">还没有对话</p>}
          </div>
        </aside>

        <div className="conversation-main">
          <header className="conversation-header">
            <div>
              <p className="conversation-eyebrow">KnowledgeOps Agent</p>
              <h1>{active?.title || "开始一段对话"}</h1>
            </div>
            <span className="api-status">API 已连接</span>
          </header>

          <div className="agent-messages" aria-live="polite">
            {active?.messages.length ? active.messages.map((item) => (
              <article className={`react-message ${item.role}`} key={item.id}>
                <span className="message-avatar" aria-hidden="true">{item.role === "user" ? user.display_name.slice(0, 1).toUpperCase() : "K"}</span>
                <div className="message-content">
                  <header>
                    <span>{item.role === "user" ? user.display_name : "KnowledgeOps"}</span>
                    <time>{new Date(item.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</time>
                  </header>
                  <p>{item.content || item.error || "等待回复"}</p>
                  {item.citations.length > 0 && (
                    <div className="citation-list">
                      {item.citations.map((citation) => <span key={citation.chunk_id}>{citation.source_name}</span>)}
                    </div>
                  )}
                  {item.role === "agent" && item.status === "completed" && (
                    <div className="agent-feedback-actions">
                      {feedbackIds.has(item.id) ? <span className="agent-feedback-confirmation">反馈已记录</span> : <>
                        <span>这条回答有帮助吗？</span>
                        <button className="agent-feedback-button" type="button" disabled={feedbackLoading === item.id} onClick={() => void submitFeedback(item.id, "helpful")}>有帮助</button>
                        <button className="agent-feedback-button" type="button" disabled={feedbackLoading === item.id} onClick={() => void submitFeedback(item.id, "unhelpful")}>需改进</button>
                      </>}
                    </div>
                  )}
                  {item.pending_action && item.thread_id && (
                    <div className="confirmation-card">
                      <strong>需要确认创建工单</strong>
                      <p>{item.pending_action.arguments.title}</p>
                      <div>
                        <button className="secondary-action" type="button" onClick={() => void confirm(item.thread_id!, false)}><X size={16} />取消</button>
                        <button className="primary-action" type="button" onClick={() => void confirm(item.thread_id!, true)}><Check size={16} />确认创建</button>
                      </div>
                    </div>
                  )}
                </div>
              </article>
            )) : (
              <div className="agent-welcome">
                <div className="agent-welcome-mark" aria-hidden="true">K</div>
                <h2>有什么可以帮你？</h2>
                <p>可以查询知识库、查看工单，或协助创建需要确认的工单。</p>
                <div className="suggestion-list">
                  {suggestions.map((suggestion) => (
                    <button key={suggestion} type="button" onClick={() => setMessage(suggestion)}>{suggestion}</button>
                  ))}
                </div>
              </div>
            )}
            {sending && <article className="react-message agent react-message-processing" aria-label="KnowledgeOps 正在处理中">
              <span className="message-avatar" aria-hidden="true">K</span>
              <div className="message-content">
                <div className="agent-processing"><span className="agent-processing-dots" aria-hidden="true"><i /><i /><i /></span>KnowledgeOps 正在处理中</div>
                <p className="agent-processing-copy">正在分析问题并检索相关信息...</p>
              </div>
            </article>}
          </div>

          {error && <p className="form-message is-error">{error}</p>}
          <form className="agent-composer" onSubmit={send}>
            <div className="agent-context-row">
              <label className="agent-context-field">
                <span>知识库</span>
                <select value={knowledgeBaseId} onChange={(event) => setKnowledgeBaseId(event.target.value)}>
                  <option value="">不限知识库</option>
                  {knowledgeBases.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
                </select>
              </label>
              <span className="agent-actor-field">操作人 {user.display_name}</span>
            </div>
            <label className="agent-message-field">
              <span className="sr-only">发送给 Agent 的消息</span>
              <textarea rows={3} value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={submitOnEnter} maxLength={4000} placeholder="输入消息，Enter 发送，Shift + Enter 换行" />
            </label>
            <div className="agent-composer-footer">
              <span>AI 生成的内容可能不准确，请注意甄别</span>
              <button type="submit" className="send-agent-button" disabled={sending}><Send size={17} />{sending ? "处理中..." : "发送"}</button>
            </div>
          </form>
        </div>
      </div>
    </section>
  );
}
