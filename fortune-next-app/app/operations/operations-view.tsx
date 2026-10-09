"use client";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { LoginRequired, useAuth } from "../auth";
import { accountLabel, Organization, productRequest, useProductData, Totals, Personal } from "../product-client";
import { savedTime } from "../history-client";
import "../management.css";
import ServiceContractPanel from "../service-contract";
import MemberStart from "../member-start";
import PurchaseRetentionPanel, { UserRetentionPanel } from "./retention-controls";

type Member = { user_id: string; display_name: string | null; email: string; role: string; account_state: string };
type OrgDetail = Organization & { logo_reference: string | null; members: Member[]; teacher_contracts: Array<{ id: string; state: string }> };
type User = Totals & { id: string; email: string; display_name: string | null; account_state: string; setup_pending: boolean;
  last_login_at: string | null; last_execution_at: string | null; saved_histories_current: number;
  memberships: Array<{ organization_id: string; role: string; display_name: string; monthly_fee: number | null; contract_state: string | null; minimum_term_until: string | null }>;
  dues: Array<{ id: string; organization_id: string; due_date: string; amount: number; settled_at: string | null }> };
type Audit = { id: string; action: string; actor_user_id: string; target_id: string; occurred_at: string };
const when = (value: string | null) => value ? savedTime(value) : "記録なし";

export default function OperationsView({ view = "list", id = "" }: { view?: "list" | "organization" | "user"; id?: string }) {
  const { user } = useAuth();
  const personal = useProductData<Personal>("/api/account/summary");
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
    <nav><Link href="/operations">Organization一覧・User一覧</Link><Link href="/mypage">自分のマイページ</Link></nav>
    {!user ? <LoginRequired next="/operations" /> : <>
      {result.loading ? <p role="status">確認中…</p> : null}{result.error ? <p role="alert">{result.error}</p> : null}
      {failure ? <p role="alert">{failure}</p> : null}{message ? <p role="status">{message}</p> : null}
      {result.data ? <>
        {view === "list" ? <>
          {personal.data ? <><MemberStart account={personal.data} /><p>自分の利用状況：今月{personal.data.executions_this_month}件／累計{personal.data.executions_total}件／保存履歴{personal.data.saved_histories_current}件</p></> : personal.error ? <p role="alert">{personal.error}</p> : <p role="status">自分の利用状況を確認中…</p>}
          <section><h2>Organization一覧</h2><ul>{(result.data as Organization[]).map(item => <li key={item.id}>
            <Link href={"/operations/organizations/" + item.id}>{item.display_name}</Link>　生徒{item.students}名／今月{item.executions_this_month}件／累計{item.executions_total}件
          </li>)}</ul></section>
          <section><h2>Organization作成</h2><form onSubmit={e => { e.preventDefault(); void action("/api/operations/organizations", { display_name: name, slug }); }}>
            <label>名称<input required maxLength={200} value={name} onChange={e => setName(e.target.value)} /></label>
            <label>識別名<input required maxLength={63} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={slug} onChange={e => setSlug(e.target.value)} /></label>
            <button disabled={busy}>作成する</button></form></section>
          <section><h2>User一覧</h2>{users.error ? <p role="alert">{users.error}</p> : <ul>{users.data?.map(item => <li key={item.id}>
            <Link href={"/operations/users/" + item.id}>{item.display_name || item.email}</Link>　{accountLabel(item.account_state)}</li>)}</ul>}</section>
          <PurchaseRetentionPanel organizations={organizations.data || []} />
          <section><h2>最近の管理操作</h2>{audit.error ? <p role="alert">{audit.error}</p> : <ul>{audit.data?.map(item => <li key={item.id}>
            {when(item.occurred_at)}　{item.action}　対象ID：{item.target_id}</li>)}</ul>}</section>
        </> : null}
        {org ? <>
          <h2>{org.display_name}</h2><p>今月の鑑定実行{org.executions_this_month}件／累計{org.executions_total}件</p>
          <section><h2>Organization設定</h2><p>識別名：{org.slug}</p><form key={org.display_name + (org.logo_reference ?? "")} onSubmit={e => {
            e.preventDefault(); const values = new FormData(e.currentTarget); void action(path, { display_name: values.get("display_name"), logo_reference: values.get("logo_reference") || null }, "PATCH"); }}>
            <label>表示名<input name="display_name" required defaultValue={org.display_name} maxLength={200} /></label>
            <label>logo参照<input name="logo_reference" defaultValue={org.logo_reference ?? ""} maxLength={2048} /></label><button disabled={busy}>設定を保存</button></form></section>
          <section><h2>所属利用者</h2><p>生徒数：{org.members.filter(item => item.role === "student").length}名</p><ul>{org.members.map(item => <li key={item.user_id}>
            <Link href={"/operations/users/" + item.user_id}>{item.display_name || item.email}</Link>　{item.role === "teacher" ? "先生" : "生徒"}／{accountLabel(item.account_state)}</li>)}</ul></section>
          <section><h2>入金確認後の生徒アカウント発行</h2><p>初回passwordは本人がメール経由で設定します。</p>
            <form onSubmit={e => { e.preventDefault(); void action("/api/operations/users", { organization_id: id, email, display_name: name, initial_payment_confirmed: paid, monthly_fee: fee ? Number(fee) : null }); }}>
              <label>氏名<input required value={name} onChange={e => setName(e.target.value)} maxLength={200} /></label>
              <label>メールアドレス<input type="email" required value={email} onChange={e => setEmail(e.target.value)} maxLength={254} /></label>
              <label>契約月額（円）<input type="number" min="0" step="1" value={fee} onChange={e => setFee(e.target.value)} /></label>
              <label className="check"><input type="checkbox" required checked={paid} onChange={e => setPaid(e.target.checked)} />入金確認済み</label>
              <button disabled={busy || !paid}>アカウントを発行</button></form></section>
          <section><h2>先生との提携・監修契約</h2><p>この契約の終了は、生徒の利用契約を停止しません。</p>
            {org.teacher_contracts.map(item => <p key={item.id}>契約：{item.state}　<button disabled={busy || item.state === "terminated"} onClick={() => {
              if (window.confirm("先生との提携契約を終了として記録しますか？生徒の利用契約は維持されます。")) void action(path + "/teacher-contract", { contract_id: item.id, state: "terminated" }); }}>提携終了を記録</button></p>)}
            {!org.teacher_contracts.length ? <button disabled={busy} onClick={() => void action(path + "/teacher-contract", { state: "active" })}>提携契約を登録</button> : null}</section>
        </> : null}
        {target ? <><h2>{target.display_name || target.email}</h2><dl><dt>account状態</dt><dd>{accountLabel(target.account_state)}</dd>
          <dt>メールアドレス</dt><dd>{target.email}</dd><dt>最終login</dt><dd>{when(target.last_login_at)}</dd><dt>最終鑑定実行</dt><dd>{when(target.last_execution_at)}</dd>
          <dt>今月の鑑定実行</dt><dd>{target.executions_this_month}件</dd><dt>累計鑑定実行</dt><dd>{target.executions_total}件</dd><dt>現在の保存履歴件数</dt><dd>{target.saved_histories_current}件</dd></dl>
          <UserRetentionPanel ownerId={target.id} />
          <section><h2>氏名設定</h2><form onSubmit={e => { e.preventDefault(); void action(base, { display_name: name }, "PATCH"); }}>
            <label>氏名<input required value={name} onChange={e => setName(e.target.value)} maxLength={200} /></label><button disabled={busy}>氏名を保存</button></form></section>
          <section><h2>利用停止・再開</h2><p>以下はアカウント全体の管理操作です。Organizationごとの休止は所属先の「この契約を休止」を使ってください。</p><div className="managementActions"><button disabled={busy || target.account_state !== "active" || target.id === user.id} onClick={() => {
            if (window.confirm("利用を停止しますか？dataは保持され、現在のsessionは失効します。")) void action(base + "/suspend", {}); }}>利用を停止</button>
            <button disabled={busy || target.account_state === "active" || target.id === user.id} onClick={() => {
              if (window.confirm("未納分の全額精算を確認して利用を再開しますか？")) void action(base + "/resume", {}); }}>利用を再開</button></div>
            {target.setup_pending ? <><p>初回password設定待ち</p><button disabled={busy || target.account_state !== "active"} onClick={() => void action(base + "/setup-mail", {})}>初回設定メールを再送</button></> : null}</section>
          <section><h2>Organization所属</h2><ul>{target.memberships.map(item => <li key={item.organization_id}>{item.display_name}／{item.role === "teacher" ? "先生" : "生徒"}
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
