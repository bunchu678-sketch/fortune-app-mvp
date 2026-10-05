"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createContext, Fragment, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useFortuneState } from "./fortune-state";
import "./auth.css";

export type AuthUser = { id: string; email: string; development?: boolean };
type AuthState = { user: AuthUser | null; loading: boolean; error: string; refresh: () => Promise<void>; login: (email: string, password: string) => Promise<void>; logout: () => Promise<void> };
const Context = createContext<AuthState | null>(null);
export const API_BASE = (process.env.NEXT_PUBLIC_FORTUNE_API_URL ?? "").replace(/\/+$/, "");

async function authRequest(action: string, payload?: object) {
  const response = await fetch(API_BASE + "/api/auth/" + action, {
    method: payload ? "POST" : "GET", credentials: "same-origin", cache: "no-store",
    headers: { "Content-Type": "application/json" }, ...(payload ? { body: JSON.stringify(payload) } : {}),
  });
  const body = await response.json();
  if (action === "me" && response.status === 401) return null;
  if (!response.ok || !body.ok) throw new Error(body.error || "認証を確認できません。");
  return body.data.user ?? null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const { setSaved, setDraft } = useFortuneState();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generation, setGeneration] = useState(0);
  const identity = useRef<string | null>(null);
  const requestSequence = useRef(0);
  const apply = useCallback((value: AuthUser | null) => {
    if (identity.current !== (value?.id ?? null)) {
      setSaved(null); setDraft(null); setGeneration(n => n + 1);
    }
    identity.current = value?.id ?? null;
    setUser(value); setLoading(false);
  }, [setSaved, setDraft]);
  const refresh = useCallback(async () => {
    const sequence = ++requestSequence.current;
    try { const value = await authRequest("me"); if (sequence === requestSequence.current) { apply(value); setError(""); } }
    catch (caught) { if (sequence === requestSequence.current) { apply(null); setError(caught instanceof Error ? caught.message : "認証を確認できません。"); } }
  }, [apply]);
  useEffect(() => {
    void refresh();
    const onFocus = () => { void refresh(); };
    window.addEventListener("focus", onFocus); window.addEventListener("pageshow", onFocus);
    const timer = window.setInterval(onFocus, 60000);
    return () => { window.removeEventListener("focus", onFocus); window.removeEventListener("pageshow", onFocus); window.clearInterval(timer); };
  }, [refresh]);
  async function login(email: string, password: string) {
    ++requestSequence.current;
    const value = await authRequest("login", { email, password }); ++requestSequence.current; apply(value); setError("");
  }
  async function logout() {
    ++requestSequence.current;
    await authRequest("logout", {}); ++requestSequence.current; apply(null); setError("");
  }
  return <Context.Provider value={{ user, loading, error, refresh, login, logout }}>
    <AuthBar /><Fragment key={generation}>{children}</Fragment>
  </Context.Provider>;
}

export function useAuth() {
  const state = useContext(Context);
  if (!state) throw new Error("認証状態を取得できません。");
  return state;
}

export function useActiveView() {
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  return () => active.current;
}

function AuthBar() {
  const { user, loading, error, logout } = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  async function exit() {
    setBusy(true); setFailure("");
    try { await logout(); router.replace("/"); }
    catch (caught) { setFailure(caught instanceof Error ? caught.message : "ログアウトに失敗しました。"); }
    finally { setBusy(false); }
  }
  return <div className="authBar" aria-label="ログイン状態">
    {loading ? <span role="status">認証を確認中…</span> : user ? <>
      <span>{user.development ? "開発用固定利用者" : user.email + " でログイン中"}</span>
      {!user.development ? <button type="button" disabled={busy} onClick={exit}>ログアウト</button> : null}
    </> : <Link href="/login">ログイン</Link>}
    {failure || error ? <p role="alert">{failure || error}</p> : null}
  </div>;
}

export function LoginRequired({ next = "/", children }: { next?: string; children?: ReactNode }) {
  const { loading } = useAuth();
  return <div className="loginRequired"><p role="status">{loading ? "認証を確認中…" : "履歴・保存・鑑定書出力を利用するにはログインしてください。"}</p>
    {!loading ? <Link href={"/login?next=" + encodeURIComponent(next)}>ログインへ</Link> : null}{children}</div>;
}
