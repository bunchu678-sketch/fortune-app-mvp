"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { LoginRequired, useAuth } from "../../auth";
import { accountLabel, Totals, useProductData } from "../../product-client";
import "../../management.css";
type TeacherData = Totals & { display_name: string; students: Array<{ display_name: string; account_state: string }> };
export default function TeacherPage() {
  const org = String(useParams<{ organizationId: string }>().organizationId);
  const { user } = useAuth(); const { data, loading, error } = useProductData<TeacherData>("/api/b2b/organizations/" + encodeURIComponent(org) + "/teacher");
  return <main className="appShell managementPage"><h1>先生用管理画面</h1>
    {!user ? <LoginRequired next={"/teacher/" + org} /> : <>
      {loading ? <p role="status">確認中…</p> : null}{error ? <p role="alert">{error}</p> : null}
      {data ? <><h2>{data.display_name}</h2><section><h2>Organization全体の利用状況</h2>
        <dl><dt>今月の鑑定実行件数</dt><dd>{data.executions_this_month}件</dd><dt>累計鑑定実行件数</dt><dd>{data.executions_total}件</dd></dl>
        <p>先生ご本人の鑑定実行も含みます。今月は日本時間で集計します。</p></section>
        <section><h2>生徒一覧</h2>{!data.students.length ? <p>生徒は登録されていません。</p> : <ul>{data.students.map((item, index) =>
          <li key={index}>{item.display_name}　{accountLabel(item.account_state)}</li>)}</ul>}</section>
        <nav><Link href="/history">自分の鑑定履歴</Link><Link href="/mypage">自分の鑑定回数・アカウント</Link><Link href={"/b2b/" + org}>鑑定する</Link></nav>
      </> : null}
    </>}<nav><Link href="/mypage">マイページへ</Link></nav><p>Powered by 博士の占いらぼ</p>
  </main>;
}
