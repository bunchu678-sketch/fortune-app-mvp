"use client";
import Link from "next/link";
import { Personal, useProductData } from "./product-client";
import type { Membership } from "./member-navigation";

function OrganizationStart({ member }: { member: Membership }) {
  const { data, loading, error } = useProductData<{ role: string }>("/api/b2b/organizations/" + encodeURIComponent(member.organization_id) + "/me");
  return <li><strong>{member.display_name}（先生版）</strong>
    {loading ? <p role="status">利用権限を確認中…</p> : data && ["teacher", "student"].includes(data.role) ?
      <p><Link className="memberStartButton" href={"/b2b/" + member.organization_id} aria-label={member.display_name + "で鑑定を始める"}>鑑定を始める</Link></p> :
      <p role="alert">{error || "この所属先の利用権限を確認できません。"}</p>}
  </li>;
}

export default function MemberStart({ account }: { account: Personal }) {
  return <section className="memberStart" aria-label="鑑定の入口"><h2>鑑定を始める</h2>
    {account.memberships.length > 1 ? <p>利用する所属先を選んでください。</p> : null}
    {account.memberships.length ? <ul>{account.memberships.map(member => <OrganizationStart key={member.organization_id} member={member} />)}</ul> : null}
    <p><strong>通常鑑定（博士の占い）</strong></p>
    <Link className="memberStartButton" href="/" aria-label="通常鑑定（博士の占い）で鑑定を始める">鑑定を始める</Link>
    <nav><Link href="/history">自分の鑑定履歴</Link></nav>
  </section>;
}
