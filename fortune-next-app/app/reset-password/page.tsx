"use client";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { API_BASE } from "../auth";
import { readResetToken } from "../reset-link";

export default function ResetPasswordPage() {
  const captured = useRef(false);
  const [token, setToken] = useState("");
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const capture = () => {
      const value = readResetToken(window.location.href);
      if (value || window.location.hash || !captured.current) setToken(value);
      captured.current = true;
      window.history.replaceState(null, "", window.location.pathname);
      setReady(true);
    };
    capture();
    window.addEventListener("hashchange", capture);
    return () => window.removeEventListener("hashchange", capture);
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError("");
    if (password !== confirmation) { setError("確認用パスワードが一致しません。"); return; }
    setBusy(true);
    try {
      const response = await fetch(API_BASE + "/api/auth/password-reset/complete", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, password }),
      });
      const body = await response.json();
      if (!response.ok || !body.ok) throw new Error(body.error || "再設定できませんでした。再度申請してください。");
      setToken(""); setPassword(""); setConfirmation("");
      window.location.replace("/login?reset=done");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "再設定できませんでした。"); }
    finally { setBusy(false); }
  }
  return <main className="appShell loginPage"><h1>新しいパスワード</h1>
    {!ready ? <p role="status">リンクを確認中…</p> : !token ? <p role="alert">再設定リンクを確認できません。<Link href="/forgot-password">再度申請してください。</Link></p> : <form onSubmit={submit}>
      <label>新しいパスワード<input type="password" autoComplete="new-password" minLength={12} maxLength={1024} required value={password} onChange={event => setPassword(event.target.value)} /></label>
      <label>新しいパスワード（確認）<input type="password" autoComplete="new-password" minLength={12} maxLength={1024} required value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>
      <button type="submit" disabled={busy}>{busy ? "変更中…" : "パスワードを変更"}</button>
    </form>}
    {error ? <p role="alert">{error}</p> : null}<p><Link href="/login">ログインへ戻る</Link></p>
  </main>;
}
