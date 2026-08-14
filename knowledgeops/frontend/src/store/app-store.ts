import { create } from "zustand";

import type { KnowledgeBase, User, ViewId } from "../api/types";

interface Notice {
  id: number;
  message: string;
  tone: "success" | "error" | "info";
}

interface AppState {
  activeView: ViewId;
  routeTarget: string | null;
  user: User | null;
  knowledgeBases: KnowledgeBase[];
  notice: Notice | null;
  setActiveView: (view: ViewId) => void;
  openWorkspaceItem: (view: ViewId, targetId?: string | null) => void;
  clearRouteTarget: () => void;
  setUser: (user: User | null) => void;
  setKnowledgeBases: (knowledgeBases: KnowledgeBase[]) => void;
  showNotice: (message: string, tone?: Notice["tone"]) => void;
  clearNotice: () => void;
}

let noticeId = 0;

export const useAppStore = create<AppState>((set) => ({
  activeView: "dashboard",
  routeTarget: null,
  user: null,
  knowledgeBases: [],
  notice: null,
  setActiveView: (activeView) => set({ activeView, routeTarget: null }),
  openWorkspaceItem: (activeView, routeTarget = null) => set({ activeView, routeTarget }),
  clearRouteTarget: () => set({ routeTarget: null }),
  setUser: (user) => set({ user }),
  setKnowledgeBases: (knowledgeBases) => set({ knowledgeBases }),
  showNotice: (message, tone = "info") => set({ notice: { id: ++noticeId, message, tone } }),
  clearNotice: () => set({ notice: null }),
}));
