"use client";
import { useState } from "react";
import { Organization, productRequest, useProductData } from "../product-client";

type Plan = { can_delete: boolean; blockers: string[]; automatic_actions_enabled: boolean };
type Proof = { purchase_number: string; organization_id: string; purchased_on: string; review_on: string };
type Review = { id: string; record_kind: string; review_on: string; retention_basis: string };
const reasons: Record<string,string> = { b2c_active_or_unknown: "B2C利用中または未確認", b2c_readings: "B2Cの保存データあり",
  b2c_execution_records: "B2Cの実行記録あり", operating_administrator: "運営管理者", non_student_membership: "生徒以外の所属あり",
  contract_not_expired_or_dependency: "契約・保持期間未満了またはデータ参照あり", unknown_contract: "契約要確認", no_verified_contract_history: "確認済みの契約情報なし" };

export function UserRetentionPanel({ ownerId }: { ownerId: string }) {
  const base = `/api/operations/users/${encodeURIComponent(ownerId)}`;
  const result = useProductData<Plan>(base + "/retention");
  const [message,setMessage] = useState(""), [busy,setBusy] = useState(false);
  return <section><h2>User保持の確認</h2><p>B2Cが未確認の場合はUserを保護します。鑑定データが残る場合も削除対象にはしません。</p>
    {result.error ? <p role="alert">{result.error}</p> : null}
    {result.data?.blockers ? <p>削除ドライラン：{result.data.can_delete ? "全契約の保持期限満了・確認済み" : result.data.blockers.map(v => reasons[v] || "参照関係の確認が必要").join("／")}。物理削除の実行操作はありません。</p> : null}
    <form onSubmit={async e => { e.preventDefault(); const data = new FormData(e.currentTarget);
      if (!window.confirm("本人のB2C利用状況を確認しましたか？この記録だけでデータ削除や利用停止は行いません。")) return;
      setBusy(true); try { await productRequest(base + "/b2c-retention", { method: "POST", body: JSON.stringify({state: data.get("state")}) }); await result.reload(); setMessage("利用状況の確認を記録しました。"); }
      catch(error) { setMessage(error instanceof Error ? error.message : "記録できませんでした。"); } finally { setBusy(false); } }}>
      <label>本人確認済みB2C利用状況<select name="state"><option value="active">利用継続</option><option value="inactive">利用終了を確認</option></select></label><button disabled={busy}>B2C利用状況を記録</button></form>
    {message ? <p role="status">{message}</p> : null}</section>;
}

export default function PurchaseRetentionPanel({ organizations }: { organizations: Organization[] }) {
  const proofs = useProductData<Proof[]>("/api/operations/purchases"), reviews = useProductData<Review[]>("/api/operations/retention-reviews");
  const [message,setMessage] = useState(""), [busy,setBusy] = useState(false);
  async function write(path: string, body: object) {
    setBusy(true); setMessage(""); try { const result = await productRequest<{setup_pending?:boolean}>(path,{method:"POST",body:JSON.stringify(body)});
      await Promise.all([proofs.reload(),reviews.reload()]); setMessage(result?.setup_pending ? "再契約アカウントを発行しました。初回設定メールは未送信です。既存のUser管理から設定後に再送してください。" : "記録しました。");
    } catch(error) { setMessage(error instanceof Error ? error.message : "記録できませんでした。"); } finally { setBusy(false); }
  }
  const options = <><option value="">対象アプリを選択</option>{organizations.map(o => <option key={o.id} value={o.id}>{o.display_name}</option>)}</>;
  return <section><h2>初期購入証明・再契約</h2><p>同じ先生版アプリの購入済み確認に使います。別アプリの初期費用は免除しません。削除済み鑑定履歴は復元できません。</p>
    {proofs.error || reviews.error ? <p role="alert">{proofs.error || reviews.error}</p> : null}{message ? <p role="status">{message}</p> : null}
    <ul>{proofs.data?.map(p => <li key={p.purchase_number}>{p.purchase_number}／{organizations.find(o => o.id === p.organization_id)?.display_name || p.organization_id}／購入日{p.purchased_on}／保持見直し日{p.review_on}</li>)}</ul>
    <details><summary>手動確認済みの購入証明を登録</summary><form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); void write("/api/operations/purchases", {
      purchase_number:f.get("purchase_number"),organization_id:f.get("organization_id"),purchased_on:f.get("purchased_on"),email:f.get("email"),review_on:f.get("review_on"),payment_confirmed:f.get("paid") === "on",user_id:f.get("user_id") || null }); }}>
      <label>購入番号<input name="purchase_number" required maxLength={100}/></label><label>購入した先生版アプリ<select name="organization_id" required>{options}</select></label>
      <label>購入日<input name="purchased_on" type="date" required/></label><label>購入者確認メール<input name="email" type="email" required/></label>
      <label>既存User ID（登録済みの場合）<input name="user_id"/></label><label>購入証明の保持見直し日<input name="review_on" type="date" required/></label>
      <label className="check"><input name="paid" type="checkbox" required/>初期購入費用の入金確認済み</label><button disabled={busy}>購入証明を登録</button></form></details>
    <details><summary>購入証明・本人確認後の再契約</summary><form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget);
      if (!window.confirm("購入証明と本人確認、月額入金を確認しましたか？削除予定を取り消して再契約します。削除済み履歴は復元しません。")) return;
      void write(`/api/operations/purchases/${encodeURIComponent(String(f.get("purchase_number")))}/recontract`, {organization_id:f.get("organization_id"),email:f.get("email"),display_name:f.get("display_name"),paid_through:f.get("paid_through"),identity_verified:f.get("identity") === "on",monthly_payment_confirmed:f.get("monthly") === "on"}); }}>
      <label>再契約の購入番号<input name="purchase_number" required/></label><label>再契約する先生版アプリ<select name="organization_id" required>{options}</select></label>
      <label>本人確認したメール<input name="email" type="email" required/></label><label>再契約者氏名<input name="display_name" required maxLength={200}/></label>
      <label>再契約の支払済み期間末日<input name="paid_through" type="date" required/></label>
      <label className="check"><input name="identity" type="checkbox" required/>購入証明と本人確認済み</label><label className="check"><input name="monthly" type="checkbox" required/>月額料金の入金確認済み</label><button disabled={busy}>再契約を記録</button></form></details>
    <details><summary>契約・会計記録の保持見直し</summary><p>法定期間は自動判定しません。記録の種類と適用法令を確認し、次回見直し日と根拠を記録してください。</p>
      <ul>{reviews.data?.map(r => <li key={r.id}>{r.id}／{r.record_kind}／見直し日{r.review_on}／{r.retention_basis}</li>)}</ul>
      <form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); void write(`/api/operations/retention-reviews/${f.get("kind")}/${encodeURIComponent(String(f.get("id")))}`,{review_on:f.get("review_on"),basis:f.get("basis")}); }}>
        <label>保持記録の種類<select name="kind"><option value="purchase">購入証明</option><option value="record">契約・会計保管記録</option></select></label>
        <label>購入番号または保管記録ID<input name="id" required/></label><label>次回保持見直し日<input name="review_on" type="date" required/></label>
        <label>保持を継続する根拠<input name="basis" required maxLength={200}/></label><button disabled={busy}>保持見直しを記録</button></form></details>
  </section>;
}
