"use client";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { API_BASE } from "../auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(API_BASE + "/api/auth/password-reset/request", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }),
      });
      const body = await response.json();
      if (!response.ok || !body.ok) throw new Error(response.status === 503 ? "現在、パスワード再設定を利用できません。管理者へお問い合わせください。" : body.error || "申請できませんでした。時間をおいて再度お試しください。");
      setMessage("登録されている場合は、パスワード再設定の案内を送信します。");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "申請できませんでした。"); }
    finally { setBusy(false); }
  }
  return <main className="appShell loginPage"><h1>パスワード再設定</h1>
    <p>登録したメールアドレスを入力してください。再設定リンクは30分間有効です。</p>
    <form onSubmit={submit}><label>メールアドレス<input type="email" autoComplete="email" required maxLength={254} value={email} onChange={event => setEmail(event.target.value)} /></label>
      <button type="submit" disabled={busy}>{busy ? "申請中…" : "再設定を申請"}</button>
    </form>
    {message ? <p role="status">{message}</p> : null}{error ? <p role="alert">{error}</p> : null}
    <Link href="/login">ログインへ戻る</Link>
  </main>;
}
