"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { formatJstDate } from "../jst-date";
import { useProductState } from "./product-state";

type Boundary = { kind: "birth" | "reading"; term_name: string; boundary_datetime: string; choice?: "before" | "after" };
type Result = { ok?: boolean; errors?: string[]; calendar?: { auto_boundaries?: Boundary[] } };
type Form = { name: string; furigana: string; birthDate: string; birthTime: string; birthTimeUnknown: boolean; gender: string; birthPlace: string; readingDate: string };
const API_BASE = (process.env.NEXT_PUBLIC_FORTUNE_API_URL ?? "").replace(/\/+$/, "");
const prefectures = ["未選択", "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"];
const initial = (): Form => ({ name: "", furigana: "", birthDate: "1950-01-01", birthTime: "00:00", birthTimeUnknown: false, gender: "未選択", birthPlace: "未選択", readingDate: formatJstDate(new Date()) });

export default function ProductInput() {
  const router = useRouter();
  const { setSaved } = useProductState();
  const [form, setForm] = useState<Form>(initial);
  const [manual, setManual] = useState(false);
  const [boundaries, setBoundaries] = useState<Boundary[]>([]);
  const [choices, setChoices] = useState<Record<string, "before" | "after">>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Form>(key: K, value: Form[K]) => { setForm(current => ({ ...current, [key]: value })); setBoundaries([]); setChoices({}); };

  async function request(payload: Record<string, unknown>): Promise<Result> {
    const response = await fetch(`${API_BASE}/api/fortune`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    return response.json();
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const base = { ...form, includeGogyoVariants: true, productAutoBoundary: true, includeKanteiYearGogyoEffects: true };
      // Ask the backend for its own boundary judgement. The browser does no calendar arithmetic.
      const automatic = await request(base);
      if (!automatic.ok) { setError(automatic.errors?.join(" / ") || "鑑定結果を取得できませんでした。"); return; }
      const found = automatic.calendar?.auto_boundaries ?? [];
      if (manual && found.length && !boundaries.length) { setBoundaries(found); return; }
      if (manual && found.some(item => !choices[item.kind])) { setBoundaries(found); setError("修正する境界の前後を選択してください。"); return; }
      let result = automatic;
      if (manual && found.length) {
        result = await request({ ...base, boundarySelections: Object.fromEntries(found.map(item => [item.kind, { boundary_datetime: item.boundary_datetime, choice: choices[item.kind] }])) });
        if (!result.ok) { setError(result.errors?.join(" / ") || "鑑定結果を取得できませんでした。"); return; }
      }
      setSaved({ result, form, boundaryInfo: found, manualChoices: manual ? choices : {} });
      router.push("/product/result");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "APIに接続できませんでした。");
    } finally { setBusy(false); }
  }

  return <main className="productPage productInputPage">
    <header className="productHeader"><h1>鑑定入力</h1><p>商品版の画面確認用</p></header>
    <form className="productForm" onSubmit={submit}>
      <div className="productFieldPair"><label>氏名<input value={form.name} onChange={e => set("name", e.target.value)} /></label><label>ふりがな<input value={form.furigana} onChange={e => set("furigana", e.target.value)} /></label></div>
      <div className="productFieldPair"><label>生年月日<input required type="date" value={form.birthDate} onChange={e => set("birthDate", e.target.value)} /></label><label>鑑定日<input required type="date" value={form.readingDate} onChange={e => set("readingDate", e.target.value)} /></label></div>
      <div className="productFieldPair"><div><label>出生時刻<input type="time" value={form.birthTime} disabled={form.birthTimeUnknown} onChange={e => set("birthTime", e.target.value)} /></label><label className="productCheck"><input type="checkbox" checked={form.birthTimeUnknown} onChange={e => set("birthTimeUnknown", e.target.checked)} />出生時刻不明</label></div><label>性別<select value={form.gender} onChange={e => set("gender", e.target.value)}><option>未選択</option><option>男性</option><option>女性</option><option>その他・回答しない</option></select></label></div>
      <label>出生地<select value={form.birthPlace} onChange={e => set("birthPlace", e.target.value)}>{prefectures.map(value => <option key={value}>{value}</option>)}</select></label>
      <div className="productBoundary"><h2>節入り・万年暦確認</h2>
        {boundaries.length ? boundaries.map(item => <div key={item.kind} className="productBoundaryItem"><p>{item.kind === "birth" ? "出生日時" : "鑑定日"}／{item.term_name}　現在のアプリ判定：節入り{item.choice === "before" ? "前" : "後"}</p>{manual ? <div className="productRadio"><label><input type="radio" name={`choice-${item.kind}`} checked={choices[item.kind] === "before"} onChange={() => setChoices(current => ({ ...current, [item.kind]: "before" }))} />節入り前を使う</label><label><input type="radio" name={`choice-${item.kind}`} checked={choices[item.kind] === "after"} onChange={() => setChoices(current => ({ ...current, [item.kind]: "after" }))} />節入り後を使う</label></div> : null}</div>) : <p>境界付近の場合、鑑定時に現在のアプリ判定を表示します。</p>}
        <label className="productCheck"><input type="checkbox" checked={manual} onChange={e => { setManual(e.target.checked); setChoices({}); }} />万年暦の確認結果で判定を修正する</label>
      </div>
      {error ? <p className="productError" role="alert">{error}</p> : null}
      <button className="productPrimary" disabled={busy || !form.birthDate || !form.readingDate}>{busy ? "計算中…" : boundaries.length && manual ? "選択した判定で鑑定" : "鑑定する"}</button>
    </form>
  </main>;
}
