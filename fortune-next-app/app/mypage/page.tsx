"use client";
import Link from "next/link";
import { LoginRequired, useAuth } from "../auth";
import { useProductData, Personal } from "../product-client";
import "../management.css";
import ServiceContractPanel from "../service-contract";
import MemberStart from "../member-start";

export default function MyPage() {
  const { user } = useAuth(); const { data, error, loading } = useProductData<Personal>("/api/account/summary");
  return <main className="appShell managementPage"><h1>マイページ</h1>
    {!user ? <LoginRequired next="/mypage" /> : <>
      {loading ? <p role="status">利用状況を確認中…</p> : null}{error ? <p role="alert">{error}</p> : null}
      {data ? <>
        <MemberStart account={data} />
        <section><h2>自分の利用状況</h2><dl><dt>今月の鑑定実行回数</dt><dd>{data.executions_this_month}件</dd>
          <dt>累計鑑定実行回数</dt><dd>{data.executions_total}件</dd><dt>現在の鑑定履歴保存件数</dt><dd>{data.saved_histories_current}件</dd></dl>
          <p>今月は日本時間で集計します。履歴の再表示・メモ編集は鑑定実行回数に含みません。</p>
          <nav><Link href="/history/deleted">削除した履歴を復旧</Link></nav>
        </section>
        {data.memberships.length ? <section><h2>所属先</h2><ul>{data.memberships.map(item => <li key={item.organization_id}>
          {item.display_name}
          {item.role === "teacher" ? <>　<Link href={"/teacher/" + item.organization_id}>先生用管理画面</Link></> : null}
          {item.role === "student" ? <ServiceContractPanel organizationId={item.organization_id} /> : null}
        </li>)}</ul></section> : null}
        <section><h2>アカウント設定</h2><p>メールアドレス：{data.email}</p><Link href="/forgot-password">パスワードを再設定</Link></section>
        {data.is_operator ? <section><Link href="/operations">しぜんとらぼ 運営管理</Link></section> : null}
      </> : null}
    </>}<nav><Link href="/">博士の占いへ</Link></nav>
  </main>;
}
