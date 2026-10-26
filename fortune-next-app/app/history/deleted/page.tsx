"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { LoginRequired, useAuth, useActiveView } from "../../auth";
import { historyRequest, savedTime } from "../../history-client";
import "../history.css";

type Entry = { id: string; name: string; birth_date: string; reading_date: string; deleted_at: string; restore_until: string };
export default function DeletedHistoryPage() {
  const { user, loading: authLoading } = useAuth();
  const isActive = useActiveView();
  const [items, setItems] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const sequence = useRef(0);
  async function load() {
    const requestId = ++sequence.current;
    setLoading(true); setError("");
    try { const result = await historyRequest<Entry[]>("/deleted"); if (sequence.current === requestId) setItems(result); }
    catch (caught) { if (sequence.current === requestId) setError(caught instanceof Error ? caught.message : "履歴を取得できません。"); }
    finally { if (sequence.current === requestId) setLoading(false); }
  }
  useEffect(() => { if (user) void load(); else { ++sequence.current; setItems([]); } return () => { ++sequence.current; }; }, [user?.id]);
  async function restore(id: string) {
    const active = sequence.current;
    setBusy(true); setError("");
    try { await historyRequest("/" + id + "/restore", { method: "POST", body: "{}" }); if (sequence.current === active) await load(); }
    catch (caught) { if (sequence.current === active) setError(caught instanceof Error ? caught.message : "復旧できません。"); }
    finally { if (isActive()) setBusy(false); }
  }
  if (authLoading || !user) return <main className="appShell historyPage"><h1>削除した鑑定履歴</h1><LoginRequired next="/history/deleted" /></main>;
  return <main className="appShell historyPage"><header className="historyHeader"><h1>削除した鑑定履歴</h1><Link href="/history">鑑定履歴へ戻る</Link></header>
    <p>削除から30日以内の履歴を復旧できます。復旧すると通常の鑑定履歴へ戻ります。</p>
    {loading ? <p role="status">履歴を読み込み中…</p> : null}{error ? <p role="alert">{error}</p> : null}
    {!loading && !error && !items.length ? <p>復旧できる鑑定履歴はありません。</p> : null}
    {items.map(item => <article className="historyCard" key={item.id}><h2>{item.name}</h2>
      <p>生年月日：{item.birth_date}／鑑定日：{item.reading_date}</p><p>削除日時：{savedTime(item.deleted_at)}</p>
      <p>復旧期限：{savedTime(item.restore_until)} より前</p>
      <button type="button" disabled={busy} onClick={() => void restore(item.id)}>復旧する</button>
    </article>)}
  </main>;
}
