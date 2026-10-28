"use client";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { LoginRequired, useAuth } from "../auth";
import { accountLabel, Organization, productRequest, useProductData, Totals } from "../product-client";
import { savedTime } from "../history-client";
import "../management.css";
import ServiceContractPanel from "../service-contract";
import PurchaseRetentionPanel, { UserRetentionPanel } from "./retention-controls";
import InvitationsPanel from "./invitations-panel";

type Member = { user_id: string; display_name: string | null; email: string; role: string; account_state: string };
type OrgDetail = Organization & { logo_reference: string | null; members: Member[]; teacher_contracts: Array<{ id: string; state: string }> };
type User = Totals & { id: string; email: string; display_name: string | null; account_state: string; setup_pending: boolean;
  last_login_at: string | null; last_execution_at: string | null; saved_histories_current: number;
  memberships: Array<{ organization_id: string; role: string; display_name: string; monthly_fee: number | null; contract_state: string | null; minimum_term_until: string | null }>;
  dues: Array<{ id: string; organization_id: string; due_date: string; amount: number; settled_at: string | null }> };
type Audit = { id: string; action: string; actor_user_id: string; target_id: string; occurred_at: string };
const auditLabels: Record<string, string> = {
  "administrator-bootstrap": "運営管理者の初期設定",
  "organization-create": "教室・講師の登録",
  "organization-update": "教室・講師名・設定の更新",
  "membership-set": "所属の設定",
  "account-issue": "アカウント発行",
  "user-name-set": "ユーザー氏名の設定",
  "account-suspend": "アカウント利用停止",
  "account-resume": "アカウント利用再開",
  "arrears-record": "未納の記録",
  "arrears-settle": "未納の精算",
  "teacher-contract-set": "先生との提携契約の設定",
  "invitation-create-free-trial": "無料試用の招待作成",
  "invitation-mail-queued": "招待メールの送信受付",
  "invitation-cancel": "招待の取消し",
  "b2c-retention-confirm": "一般向けアプリの利用状況確認",
  "purchase-proof-register": "購入証明の登録",
  "purchase-recontract": "再契約の記録",
  "retention-review-purchase": "購入証明の保持見直し",
  "retention-review-record": "契約・会計記録の保持見直し",
  "user-purge-test": "ユーザー情報削除の検証",
  "service-grant-activate": "利用権の有効化",
  "service-activate": "利用開始の確認",
  "paid-period-confirm": "支払済み期間の確認",
  "service-suspend": "利用契約の休止",
  "service-resume": "利用契約の再開",
  "service-cancellation-request": "解約の申請",
  "service-data-recover": "解約データの復旧",
  "service-data-purge-test": "契約データ削除の検証",
  "service-initial-activate": "初回利用開始"
};
const when = (value: string | null) => value ? savedTime(value) : "記録なし";

export default function OperationsView({ view = "list", id = "" }: { view?: "list" | "organization" | "user"; id?: string }) {
  const { user } = useAuth();
  const path = view === "organization" ? "/api/operations/organizations/" + encodeURIComponent(id) : view === "user" ? "/api/operations/users/" + encodeURIComponent(id) : "/api/operations/organizations";
  const result = useProductData<Organization[] | OrgDetail | User>(path);
  const organizations = useProductData<Organization[]>("/api/operations/organizations");
  const users = useProductData<User[]>("/api/operations/users");
  const audit = useProductData<Audit[]>("/api/operations/audit");
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(""), [failure, setFailure] = useState("");
  const [name, setName] = useState(""), [slug, setSlug] = useState(""), [logo, setLogo] = useState("");
  const [email, setEmail] = useState(""), [paid, setPaid] = useState(false), [fee, setFee] = useState("");
  const [organization, setOrganization] = useState(""), [role, setRole] = useState("student"), [dueDate, setDueDate] = useState(""), [amount, setAmount] = useState("");
  async function action(path: string, body: object, method = "POST") {
    setBusy(true); setMessage(""); setFailure("");
    try { const value = await productRequest<{ mail_status?: string } | null>(path, { method, body: JSON.stringify(body) });
      setMessage(value?.mail_status === "disabled" || value?.mail_status === "unavailable" ? "保存しました。初回設定メールは未送信です。メール設定後に再送してください。" : value?.mail_status === "queued" ? "保存しました。初回設定メールを送信処理へ渡しました。" : "保存しました。");
      await Promise.all([result.reload(), organizations.reload(), users.reload(), audit.reload()]);
    } catch (caught) { setFailure(caught instanceof Error ? caught.message : "操作に失敗しました。"); }
    finally { setBusy(false); }
  }
  const org = view === "organization" ? result.data as OrgDetail | null : null;
  const target = view === "user" ? result.data as User | null : null;
  const organizationOptions = <><option value="">所属先を選択</option>{organizations.data?.map(item => <option key={item.id} value={item.id}>{item.display_name}</option>)}</>;
  const base = "/api/operations/users/" + encodeURIComponent(id);
  return <main className="appShell managementPage"><h1>しぜんとらぼ 運営管理</h1>
    <nav><Link href="/operations">教室・講師一覧／ユーザー一覧</Link><Link href="/mypage">アカウント設定</Link></nav>
    {!user ? <LoginRequired next="/operations" /> : <>
      {result.loading ? <p role="status">確認中…</p> : null}{result.error ? <p role="alert">{result.error}</p> : null}
      {failure ? <p role="alert">{failure}</p> : null}{message ? <p role="status">{message}</p> : null}
      {result.data ? <>
        {view !== "user" ? <InvitationsPanel organizations={organizations.data || []} organizationId={view === "organization" ? id : ""} /> : null}
        {view === "list" ? <>
          <section><h2>教室・講師一覧</h2><ul>{(result.data as Organization[]).map(item => <li key={item.id}>
            <Link href={"/operations/organizations/" + item.id}>{item.display_name}</Link>　生徒{item.students}名／今月{item.executions_this_month}件／累計{item.executions_total}件
          </li>)}</ul></section>
          <section><h2>教室・講師の登録</h2><form onSubmit={e => { e.preventDefault(); void action("/api/operations/organizations", { display_name: name, slug }); }}>
            <label>教室・講師名<input required maxLength={200} value={name} onChange={e => setName(e.target.value)} /></label>
            <label>管理用識別名（英数字）<input aria-describedby="organization-key-help" required maxLength={63} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={slug} onChange={e => setSlug(e.target.value)} /></label>
            <p id="organization-key-help">教室を区別する重複しない名前です。半角英小文字・数字・ハイフンで入力します（例：mari-mutsuro）。登録だけで公開URLは作成されません。</p><button disabled={busy}>登録する</button></form></section>
          <section><h2>ユーザー一覧</h2>{users.error ? <p role="alert">{users.error}</p> : <ul>{users.data?.map(item => <li key={item.id}>
            <Link href={"/operations/users/" + item.id}>{item.display_name || item.email}</Link>　{accountLabel(item.account_state)}</li>)}</ul>}</section>
          <PurchaseRetentionPanel organizations={organizations.data || []} />
          <section><h2>最近の管理操作</h2>{audit.error ? <p role="alert">{audit.error}</p> : <ul>{audit.data?.map(item => <li key={item.id}>
            {when(item.occurred_at)}　{auditLabels[item.action] || "管理操作（詳細は運営記録で確認）"}　対象ID：{item.target_id}</li>)}</ul>}</section>
        </> : null}
        {org ? <>
          <h2>{org.display_name}</h2><p>今月の鑑定実行{org.executions_this_month}件／累計{org.executions_total}件</p>
          <section><h2>教室・講師の設定</h2><p>管理用識別名（英数字）：{org.slug}</p><p>所属先を区別するための名前です。教室・講師名を変更しても、この識別名と現在の公開URLは変わりません。</p><form key={org.display_name + (org.logo_reference ?? "")} onSubmit={e => {
            e.preventDefault(); const values = new FormData(e.currentTarget); void action(path, { display_name: values.get("display_name"), logo_reference: values.get("logo_reference") || null }, "PATCH"); }}>
            <label>教室・講師名<input name="display_name" required defaultValue={org.display_name} maxLength={200} /></label>
            <label>ロゴの参照先<input name="logo_reference" defaultValue={org.logo_reference ?? ""} maxLength={2048} /></label><button disabled={busy}>設定を保存</button></form></section>
          <section><h2>所属利用者</h2><p>生徒数：{org.members.filter(item => item.role === "student").length}名</p><ul>{org.members.map(item => <li key={item.user_id}>
            <Link href={"/operations/users/" + item.user_id}>{item.display_name || item.email}</Link>　{item.role === "teacher" ? "先生" : "生徒"}／{accountLabel(item.account_state)}</li>)}</ul></section>
          <section><h2>入金確認後の生徒アカウント発行</h2><p>初回パスワードは本人がメール経由で設定します。</p>
            <form onSubmit={e => { e.preventDefault(); void action("/api/operations/users", { organization_id: id, email, display_name: name, initial_payment_confirmed: paid, monthly_fee: fee ? Number(fee) : null }); }}>
              <label>氏名<input required value={name} onChange={e => setName(e.target.value)} maxLength={200} /></label>
              <label>メールアドレス<input type="email" required value={email} onChange={e => setEmail(e.target.value)} maxLength={254} /></label>
              <label>契約月額（円）<input type="number" min="0" step="1" value={fee} onChange={e => setFee(e.target.value)} /></label>
              <label className="check"><input type="checkbox" required checked={paid} onChange={e => setPaid(e.target.checked)} />入金確認済み</label>
              <button disabled={busy || !paid}>アカウントを発行</button></form></section>
          <section><h2>先生との提携・監修契約</h2><p>この契約の終了は、生徒の利用契約を停止しません。</p>
            {org.teacher_contracts.map(item => <p key={item.id}>契約：{accountLabel(item.state)}　<button disabled={busy || item.state === "terminated"} onClick={() => {
              if (window.confirm("先生との提携契約を終了として記録しますか？生徒の利用契約は維持されます。")) void action(path + "/teacher-contract", { contract_id: item.id, state: "terminated" }); }}>提携終了を記録</button></p>)}
            {!org.teacher_contracts.length ? <button disabled={busy} onClick={() => void action(path + "/teacher-contract", { state: "active" })}>提携契約を登録</button> : null}</section>
        </> : null}
        {target ? <><h2>{target.display_name || target.email}</h2><dl><dt>アカウントの状態</dt><dd>{accountLabel(target.account_state)}</dd>
          <dt>メールアドレス</dt><dd>{target.email}</dd><dt>最終ログイン</dt><dd>{when(target.last_login_at)}</dd><dt>最終鑑定実行</dt><dd>{when(target.last_execution_at)}</dd>
          <dt>今月の鑑定実行</dt><dd>{target.executions_this_month}件</dd><dt>累計鑑定実行</dt><dd>{target.executions_total}件</dd><dt>現在の保存履歴件数</dt><dd>{target.saved_histories_current}件</dd></dl>
          <UserRetentionPanel ownerId={target.id} />
          <section><h2>氏名設定</h2><form onSubmit={e => { e.preventDefault(); void action(base, { display_name: name }, "PATCH"); }}>
            <label>氏名<input required value={name} onChange={e => setName(e.target.value)} maxLength={200} /></label><button disabled={busy}>氏名を保存</button></form></section>
          <section><h2>利用停止・再開</h2><p>以下はアカウント全体の管理操作です。教室・講師ごとの休止は所属先の「この契約を休止」を使ってください。</p><div className="managementActions"><button disabled={busy || target.account_state !== "active" || target.id === user.id} onClick={() => {
            if (window.confirm("利用を停止しますか？データは保持され、現在のログインは無効になります。")) void action(base + "/suspend", {}); }}>利用を停止</button>
            <button disabled={busy || target.account_state === "active" || target.id === user.id} onClick={() => {
              if (window.confirm("未納分の全額精算を確認して利用を再開しますか？")) void action(base + "/resume", {}); }}>利用を再開</button></div>
            {target.setup_pending ? <><p>初回パスワード設定待ち</p><button disabled={busy || target.account_state !== "active"} onClick={() => void action(base + "/setup-mail", {})}>初回設定メールを再送</button></> : null}</section>
          <section><h2>教室・講師への所属</h2><ul>{target.memberships.map(item => <li key={item.organization_id}>{item.display_name}／{item.role === "teacher" ? "先生" : "生徒"}
            {item.role === "student" ? <ServiceContractPanel organizationId={item.organization_id} ownerId={target.id} /> : null}
            {item.minimum_term_until ? <>／再開後の最低契約期間：{when(item.minimum_term_until)}</> : null}</li>)}</ul>
            <form onSubmit={e => { e.preventDefault(); void action(base + "/membership", { organization_id: organization, role, initial_payment_confirmed: paid, monthly_fee: fee ? Number(fee) : null }); }}>
              <label>所属先<select required value={organization} onChange={e => setOrganization(e.target.value)}>{organizationOptions}</select></label>
              <label>所属区分<select value={role} onChange={e => setRole(e.target.value)}><option value="student">生徒</option><option value="teacher">先生</option></select></label>
              <label>契約月額（円）<input type="number" min="0" step="1" value={fee} onChange={e => setFee(e.target.value)} /></label>
              <label className="check"><input type="checkbox" checked={paid} onChange={e => setPaid(e.target.checked)} />初期入金確認済み</label><button disabled={busy}>所属を設定</button></form></section>
          <section><h2>手動未納・精算記録</h2><ul>{target.dues.map(item => <li key={item.id}>期日{item.due_date}／{item.amount}円／{item.settled_at ? "精算済み" : "未納"}
            {!item.settled_at ? <>　<button disabled={busy} onClick={() => { if (window.confirm("この未納分の全額入金を確認しましたか？")) void action(base + "/dues/" + item.id + "/settle", {}); }}>全額精算を記録</button></> : null}</li>)}</ul>
            <form onSubmit={e => { e.preventDefault(); void action(base + "/dues", { organization_id: organization, due_date: dueDate, amount: Number(amount) }); }}>
              <label>契約所属先<select required value={organization} onChange={e => setOrganization(e.target.value)}>{organizationOptions}</select></label>
              <label>確認した支払期日<input type="date" required value={dueDate} onChange={e => setDueDate(e.target.value)} /></label>
              <label>確認した未納額（円）<input type="number" min="1" step="1" required value={amount} onChange={e => setAmount(e.target.value)} /></label>
              <button disabled={busy || target.account_state !== "active"}>未納を記録</button></form><p>請求・自動休止・自動督促は有効化していません。</p></section>
        </> : null}
      </> : null}
    </>}
  </main>;
}
