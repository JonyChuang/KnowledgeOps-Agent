import type { ReactNode } from "react";
import { X } from "lucide-react";

export function LoadingBlock({ label = "正在加载..." }: { label?: string }) {
  return <div className="react-loading-block"><span className="loading-spinner" />{label}</div>;
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <div className="react-empty-state"><strong>{title}</strong>{description && <p>{description}</p>}{action}</div>;
}

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return <div className="react-modal-backdrop" role="presentation" onMouseDown={onClose}>
    <section className="react-modal" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(event) => event.stopPropagation()}>
      <header><h2>{title}</h2><button type="button" className="icon-button" aria-label="关闭" onClick={onClose}><X size={18} /></button></header>
      {children}
    </section>
  </div>;
}

export function StatusPill({ value }: { value: string }) {
  const labels: Record<string, string> = { open: "待受理", in_progress: "处理中", awaiting_requester: "待补充", resolved: "已解决", closed: "已关闭", uploaded: "待索引", indexing: "索引中", ready: "已就绪", failed: "索引失败" };
  return <span className={`react-status status-${value}`}>{labels[value] ?? value}</span>;
}

export const formatDate = (value: string | null | undefined) => {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "-" : new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
};
