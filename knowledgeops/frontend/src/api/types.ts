export type UserRole = "employee" | "service_desk" | "admin";
export type TicketStatus = "open" | "in_progress" | "awaiting_requester" | "resolved" | "closed";
export type TicketPriority = "low" | "medium" | "high" | "urgent";
export type TicketImpact = "single_user" | "team" | "department" | "company";
export type ViewId =
  | "dashboard"
  | "agent"
  | "search"
  | "tickets"
  | "create-ticket"
  | "service-desk"
  | "knowledge"
  | "documents"
  | "graph"
  | "notifications"
  | "personal-library"
  | "user-management"
  | "profile";

export interface User {
  id: string;
  username: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface AuthenticatedUser {
  user: User;
  expires_at: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  department: string;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocument {
  id: string;
  knowledge_base_id: string;
  source_name: string;
  source_type: string;
  status: "uploaded" | "indexing" | "ready" | "failed";
  lifecycle: "draft" | "active" | "archived";
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  source_name: string;
  source_type: string;
  chunk_index: number;
  start_char: number;
  end_char: number;
  text: string;
  score: number;
  sources: string[];
  rerank_score: number | null;
}

export interface GraphSearchResult {
  chunk_id: string;
  document_id: string;
  knowledge_base_id: string;
  source_name: string;
  chunk_index: number;
  text: string;
}

export interface Ticket {
  id: string;
  title: string;
  description: string;
  priority: TicketPriority;
  status: TicketStatus;
  requester: string;
  category: string;
  impact: TicketImpact;
  assignee: string | null;
  escalation_level: string;
  sla_due_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TicketActivity {
  id: string;
  event_type: string;
  actor: string;
  content: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface TicketDetail extends Ticket {
  activities: TicketActivity[];
}

export interface TicketPage {
  items: Ticket[];
  total: number;
  limit: number;
  offset: number;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
  message_count: number;
  last_message_preview: string | null;
}

export interface AgentMessage {
  id: string;
  role: "user" | "agent";
  content: string | null;
  thread_id: string | null;
  status: "completed" | "confirmation_required" | "cancelled" | "failed" | null;
  created_at: string;
  citations: SearchResult[];
  pending_action: { action_type: "ticket.create"; arguments: Record<string, string> } | null;
  created_ticket_id: string | null;
  ticket_ids: string[];
  error: string | null;
}

export interface ConversationDetail extends ConversationSummary {
  actor: string;
  knowledge_base_id: string | null;
  messages: AgentMessage[];
}

export interface AgentTurn {
  thread_id: string;
  conversation_id: string | null;
  status: "completed" | "confirmation_required" | "cancelled" | "failed";
  answer: string | null;
  citations: SearchResult[];
  pending_action: { action_type: "ticket.create"; arguments: Record<string, string> } | null;
  created_ticket_id: string | null;
  ticket_ids: string[];
  error: string | null;
}

export interface Dashboard {
  actor: string;
  tickets: Record<"open_count" | "in_progress_count" | "resolved_count" | "closed_count", number>;
  indexing: Record<"knowledge_base_count" | "document_count" | "ready_count" | "pending_count" | "failed_count", number>;
  recent_tickets: Ticket[];
  knowledge_bases: KnowledgeBase[];
  recent_conversations: ConversationSummary[];
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  content: string;
  entity_type: string;
  entity_id: string;
  target_view: ViewId;
  is_read: boolean;
  created_at: string;
}

export interface NotificationPage {
  items: Notification[];
  total: number;
  unread_count: number;
  limit: number;
  offset: number;
}

export interface WorkspaceItem {
  id: string;
  entity_type: string;
  entity_id: string;
  title: string;
  subtitle: string;
  target_view: ViewId;
  target_id: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  visited_at: string | null;
}

export interface SearchItem {
  entity_type: string;
  entity_id: string;
  title: string;
  summary: string;
  target_view: ViewId;
  target_id: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string | null;
}
