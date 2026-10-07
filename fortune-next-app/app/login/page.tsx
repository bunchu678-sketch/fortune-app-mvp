"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "../auth";

export default function LoginPage() {
  const { user, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [resetDone, setResetDone] = useState(false);
  useEffect(() => { setResetDone(new URLSearchParams(window.location.search).get("reset") === "done"); }, []);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await login(email, password);
      const next = new URLSearchParams(window.location.search).get("next") ?? "/";
      router.replace(next === "/history" || /^\/history\/[a-f0-9-]+$/.test(next) ? next : "/");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "ログインに失敗しました。"); }
    finally { setPassword(""); setBusy(false); }
  }
  return <main className="appShell loginPage"><h1>ログイン</h1>
    {resetDone ? <p role="status">パスワードを変更しました。新しいパスワードでログインしてください。</p> : null}
    {user ? <p>ログイン済みです。<Link href="/">鑑定画面へ</Link></p> : <form onSubmit={submit}>
      <label>メールアドレス<input type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254} /></label>
      <label>パスワード<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required maxLength={1024} /></label>
      {error ? <p role="alert">{error}</p> : null}
      <button type="submit" disabled={busy}>{busy ? "ログイン中…" : "ログイン"}</button>
    </form>}
    <p><Link href="/forgot-password">パスワードを忘れた方</Link></p>
    <p>アカウント発行は管理者へお問い合わせください。</p>
    <Link href="/">通常鑑定へ戻る</Link>
  </main>;
}
