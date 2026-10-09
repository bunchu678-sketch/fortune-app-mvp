"use client";
import { useState } from "react";
import { accountLabel, productRequest, useProductData } from "./product-client";
import { savedTime } from "./history-client";

type Contract = { state: string; activated_at: string | null; monthly_fee: number | null;
  first_billing_date: string | null; next_billing_date: string | null; paid_through: string | null;
  suspended_at: string | null; cancellation_requested_at: string | null; access_ends_at: string | null;
  deletion_due_at: string | null; recovered_at: string | null; cancellation_needs_review: boolean; deletion_hold: boolean;
  arrears?: { suspension_due: boolean; reminder_due: boolean; next_reminder_at?: string; suspension_eligible_at?: string };
  deletion_plan?: { can_delete: boolean; reading_ids: string[]; blocked_dependencies: object[] } };
const time = (value: string | null | undefined) => value ? savedTime(value) : "未確認";

export default function ServiceContractPanel({ organizationId, ownerId }: { organizationId: string; ownerId?: string }) {
  const operator = Boolean(ownerId);
  const base = operator ? `/api/operations/users/${encodeURIComponent(ownerId!)}/organizations/${encodeURIComponent(organizationId)}/contract`
    : `/api/account/organizations/${encodeURIComponent(organizationId)}`;
  const result = useProductData<Contract>(operator ? base : base + "/contract");
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(""), [error, setError] = useState("");
  async function change(action: string, body: object = {}) {
    setBusy(true); setError(""); setMessage("");
    try { await productRequest(base + "/" + action, { method: "POST", body: JSON.stringify(body) }); await result.reload();
      setMessage(action === "data-recovery" ? "データを復旧しました。アプリの利用は再開していません。" : "契約情報を記録しました。");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "記録できませんでした。"); }
    finally { setBusy(false); }
  }
  const value = result.data;
  return <section className="serviceContract"><h3>{operator ? "利用契約・請求・保持" : "自分の利用契約"}</h3>
    {result.error || error ? <p role="alert">{error || result.error}</p> : null}{message ? <p role="status">{message}</p> : null}
    {value?.state ? <><dl><dt>利用契約の状態</dt><dd>{accountLabel(value.state)}</dd>
      <dt>利用開始日</dt><dd>{time(value.activated_at)}</dd><dt>月額利用・保守費</dt><dd>{value.monthly_fee === null ? "未確認" : `${value.monthly_fee}円`}</dd>
      <dt>初回請求起算日</dt><dd>{value.first_billing_date || "未確認"}</dd><dt>次回請求起算日</dt><dd>{value.next_billing_date || "予定なし"}</dd>
      <dt>支払済み期間の末日</dt><dd>{value.paid_through || "未確認"}</dd><dt>休止開始日</dt><dd>{time(value.suspended_at)}</dd>
      <dt>解約受付日</dt><dd>{time(value.cancellation_requested_at)}</dd><dt>利用終了予定</dt><dd>{time(value.access_ends_at)}</dd>
      <dt>データ削除予定</dt><dd>{time(value.deletion_due_at)}</dd></dl>
      <p>初回利用月は購入代金に含みます。日割り料金は計算しません。日割り返金は原則行いません。</p>
      {value.cancellation_needs_review ? <p role="status">解約申請を受け付けました。支払済み期間を運営が確認するまで終了日は未確定です。</p> : null}
      {value.recovered_at ? <p role="status">データ復旧だけでは削除予定日は延長されません。再契約・利用再開は別途運営へ確認してください。</p> : null}
      {operator ? <>
        <p>未納判定：{value.arrears?.suspension_due ? "手動確認済み未納が猶予期限に達しています" : "自動休止の対象ではありません"}</p>
        <p>督促予定：{time(value.arrears?.next_reminder_at)}／自動送信は無効です。</p>
        <div className="managementActions"><button disabled={busy || Boolean(value.activated_at) || value.state !== "active"} onClick={() => {
          if (window.confirm("実際に利用資格が有効になったことを確認しましたか？現在日時を記録し、過去の日付は補完しません。")) void change("activate"); }}>利用開始を確認</button>
          <button disabled={busy || value.state !== "active" || Boolean(value.cancellation_requested_at)} onClick={() => { if (window.confirm("このOrganizationの利用だけを休止しますか？他の所属先とB2Cは維持します。")) void change("suspend"); }}>この契約を休止</button>
          <button disabled={busy || value.state !== "suspended" || Boolean(value.cancellation_requested_at)} onClick={() => { if (window.confirm("この契約の未納全額精算を確認し、再開後は原則2か月継続しますか？")) void change("resume"); }}>この契約を再開</button></div>
        <form onSubmit={e => { e.preventDefault(); const form = new FormData(e.currentTarget);
          if (window.confirm("入金確認済みの支払期間を記録しますか？")) void change("paid-period", { paid_through: form.get("paid_through") }); }}>
          <label>確認した支払済み期間末日<input name="paid_through" type="date" required /></label><button disabled={busy || Boolean(value.access_ends_at)}>支払済み期間を記録</button></form>
        {value.deletion_plan ? <p>削除ドライラン：対象履歴{value.deletion_plan.reading_ids.length}件／{value.deletion_plan.can_delete ? "期限到達・依存なし" : "未到達または要確認"}。物理削除の実行操作はありません。</p> : null}
      </> : null}
      <div className="managementActions"><button disabled={busy || Boolean(value.access_ends_at)} onClick={() => {
        if (window.confirm("正式解約を申請しますか？支払済み期間末日まで利用できます。利用終了後のデータ保持は30日です。")) void change("cancellation"); }}>{operator ? "正式解約を受付・確認" : "正式解約を申請"}</button>
        <button disabled={busy || value.state !== "terminated" || Boolean(value.recovered_at)} onClick={() => {
          if (window.confirm("利用終了後30日以内のデータだけを復旧しますか？アプリ利用の再開とは別の処理です。")) void change("data-recovery"); }}>解約データの復旧を申請</button></div>
      {operator ? <p>請求・休止・督促・物理削除の定期処理は無効です。</p> : null}
    </> : result.loading ? <p>契約を確認中…</p> : null}
  </section>;
}
