"use client";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { historyRequest, savedTime } from "../history-client";
import { useFortuneState } from "../fortune-state";
import "./history.css";

type Entry = { id: string; name: string; birth_date: string; reading_date: string; saved_at: string };
export default function HistoryPage() {
  const { setDraft, setSaved } = useFortuneState();
  const [items, setItems] = useState<Entry[]>([]);
  const [keyword, setKeyword] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [menu, setMenu] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Entry | null>(null);
  const [busy, setBusy] = useState(false);
  const latestRequest = useRef(0);
  async function load(event?: FormEvent) {
    event?.preventDefault();
    const requestId = ++latestRequest.current;
    setLoading(true); setError("");
    try {
      const result = await historyRequest<Entry[]>("?" + new URLSearchParams({ keyword, start, end }));
      if (requestId === latestRequest.current) setItems(result);
    } catch (caught) { if (requestId === latestRequest.current) setError(caught instanceof Error ? caught.message : "履歴を取得できません。"); }
    finally { if (requestId === latestRequest.current) setLoading(false); }
  }
  useEffect(() => { void load(); }, []); // Initial query; later search is explicit.
  useEffect(() => {
    const key = (event: KeyboardEvent) => { if (event.key === "Escape") { setDeleting(null); setMenu(null); } };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  async function remove() {
    if (!deleting) return;
    setBusy(true); setError("");
    try {
      await historyRequest("/" + deleting.id, { method: "DELETE" });
      setDeleting(null); setMenu(null); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "削除に失敗しました。"); }
    finally { setBusy(false); }
  }
  const actions = (item: Entry) => <div className="historyActions">
    <Link href={"/history/" + item.id}>開く</Link>
    <button type="button" aria-label={item.name + "のメニュー"} aria-expanded={menu === item.id}
      onClick={() => setMenu(menu === item.id ? null : item.id)}>⋮</button>
    {menu === item.id ? <button type="button" onClick={() => { setDeleting(item); setMenu(null); }}>削除</button> : null}
  </div>;
  return <main className="appShell historyPage">
    <header className="historyHeader"><h1>鑑定履歴</h1>
      <Link href="/" onClick={() => { setDraft(null); setSaved(null); }}>新しく鑑定する</Link>
    </header>
    <form className="historySearch" onSubmit={load}>
      <label>キーワード<input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="氏名・ふりがな・生年月日" /></label>
      <label>鑑定日（開始）<input type="date" value={start} onChange={e => setStart(e.target.value)} /></label>
      <label>鑑定日（終了）<input type="date" value={end} onChange={e => setEnd(e.target.value)} /></label>
      <button type="submit" disabled={loading}>検索</button>
    </form>
    <p>保存日時の新しい順</p>
    {error ? <p role="alert">{error}</p> : null}
    {loading ? <p role="status">履歴を読み込み中…</p> : null}
    {!loading && !error && !items.length ? <p>該当する鑑定履歴はありません。</p> : null}
    <div className="historyDesktop">
      <table><thead><tr><th>氏名／識別</th><th>生年月日</th><th>鑑定日</th><th>保存日時</th><th>操作</th></tr></thead>
        <tbody>{items.map(item => <tr key={item.id}><td>{item.name}</td><td>{item.birth_date}</td>
          <td>{item.reading_date}</td><td>{savedTime(item.saved_at)}</td><td>{actions(item)}</td></tr>)}</tbody>
      </table>
    </div>
    <div className="historyMobile">{items.map(item => <article className="historyCard" key={item.id}>
      <h2>{item.name}</h2><p>生年月日：{item.birth_date}</p><p>鑑定日：{item.reading_date}</p>
      <p>保存日時：{savedTime(item.saved_at)}</p>{actions(item)}
    </article>)}</div>
    {deleting ? <div className="historyModal"><section role="dialog" aria-modal="true" aria-labelledby="delete-heading" className="historyCard">
      <h2 id="delete-heading">この鑑定履歴を削除しますか？</h2>
      <p>{deleting.name}／{deleting.birth_date}／鑑定日 {deleting.reading_date}</p>
      <div className="historyActions"><button type="button" autoFocus disabled={busy} onClick={() => setDeleting(null)}>キャンセル</button>
        <button type="button" disabled={busy} onClick={remove}>削除する</button></div>
    </section></div> : null}
  </main>;
}
