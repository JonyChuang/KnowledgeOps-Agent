import { useEffect, useState } from "react";

import { api, ApiError } from "./api/client";
import type { AuthenticatedUser } from "./api/types";
import { AuthScreen } from "./components/AuthScreen";
import { AppShell } from "./components/AppShell";
import { useAppStore } from "./store/app-store";

export function App() {
  const [loading, setLoading] = useState(true);
  const user = useAppStore((state) => state.user);
  const setUser = useAppStore((state) => state.setUser);

  useEffect(() => {
    let active = true;
    api<AuthenticatedUser>("/auth/me")
      .then((result) => active && setUser(result.user))
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status !== 401) console.error(error);
        if (active) setUser(null);
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [setUser]);

  if (loading) {
    return <main className="react-startup"><div className="loading-spinner" /><p>正在连接 KnowledgeOps...</p></main>;
  }
  if (!user) return <AuthScreen />;
  return <AppShell />;
}
