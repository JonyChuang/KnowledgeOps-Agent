import { useState, type FormEvent } from "react";
import { Eye, EyeOff, KeyRound, UserRound } from "lucide-react";

import { api } from "../api/client";
import type { AuthenticatedUser } from "../api/types";
import { useAppStore } from "../store/app-store";

type AuthMode = "login" | "register";

const rememberedUsernameKey = "knowledgeops.remembered-username";

function readRememberedUsername() {
  try {
    return window.localStorage.getItem(rememberedUsernameKey) ?? "";
  } catch {
    return "";
  }
}

export function AuthScreen() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState(readRememberedUsername);
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberUsername, setRememberUsername] = useState(() => Boolean(readRememberedUsername()));
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const setUser = useAppStore((state) => state.setUser);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const response = await api<AuthenticatedUser>(mode === "login" ? "/auth/login" : "/auth/register", {
        method: "POST",
        body: JSON.stringify(
          mode === "login"
            ? { username: username.trim(), password }
            : { username: username.trim(), display_name: displayName.trim(), password },
        ),
      });
      if (mode === "login") {
        try {
          if (rememberUsername) window.localStorage.setItem(rememberedUsernameKey, username.trim());
          else window.localStorage.removeItem(rememberedUsernameKey);
        } catch {
          // The sign-in flow also works in privacy-restricted browsers.
        }
      }
      setUser(response.user);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setError("");
  };

  return (
    <main className="auth-screen">
      <section className="auth-panel" aria-labelledby="auth-title">
        <header className="auth-copy">
          <span className="auth-logo" aria-hidden="true">K</span>
          <h1 id="auth-title">KnowledgeOps</h1>
          <p>登录以继续你的企业协作工作台</p>
        </header>

        <form className="auth-form" onSubmit={submit} noValidate>
          <div className="auth-tabs" role="tablist" aria-label="账号操作">
            <button className={mode === "login" ? "is-active" : ""} type="button" onClick={() => switchMode("login")}>登录</button>
            <button className={mode === "register" ? "is-active" : ""} type="button" onClick={() => switchMode("register")}>注册</button>
          </div>

          {mode === "register" && (
            <label className="auth-field">
              <span className="visually-hidden">显示名称</span>
              <span className="input-with-icon">
                <UserRound size={18} />
                <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="name" maxLength={120} placeholder="显示名称" required />
              </span>
            </label>
          )}

          <label className="auth-field">
            <span className="visually-hidden">用户名</span>
            <span className="input-with-icon">
              <UserRound size={18} />
              <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" minLength={3} maxLength={120} placeholder="用户名" required />
            </span>
          </label>

          <label className="auth-field">
            <span className="visually-hidden">密码</span>
            <span className="input-with-icon">
              <KeyRound size={18} />
              <input value={password} onChange={(event) => setPassword(event.target.value)} type={showPassword ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={8} maxLength={128} placeholder="密码（至少 8 位）" required />
              <button className="auth-password-toggle" type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "隐藏密码" : "显示密码"}>
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </span>
          </label>

          {mode === "login" && <label className="auth-remember"><input type="checkbox" checked={rememberUsername} onChange={(event) => setRememberUsername(event.target.checked)} />记住账号</label>}
          {error && <p className="form-message is-error" role="alert">{error}</p>}
          <button className="primary-action auth-submit" type="submit" disabled={submitting}>{submitting ? "正在处理..." : mode === "login" ? "登录" : "创建账号"}</button>
        </form>

        <p className="auth-footnote">企业知识库与工单协同平台</p>
      </section>
    </main>
  );
}
