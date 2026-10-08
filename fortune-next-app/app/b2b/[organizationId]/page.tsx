"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { LoginRequired, useAuth } from "../../auth";
import MainFortune from "../../main-fortune";
import { useProductData } from "../../product-client";

type OrganizationSelf = { role: string; branding: { display_name: string } };
export default function OrganizationFortune() {
  const org = String(useParams<{ organizationId: string }>().organizationId);
  const { user } = useAuth(); const { data, error, loading } = useProductData<OrganizationSelf>("/api/b2b/organizations/" + encodeURIComponent(org) + "/me");
  if (!user) return <main className="appShell"><h1>先生版 鑑定画面</h1><LoginRequired next={"/b2b/" + org} /></main>;
  if (loading) return <main className="appShell"><p role="status">所属・利用権限を確認中…</p></main>;
  if (error || !data) return <main className="appShell"><p role="alert">{error || "利用権限を確認できません。"}</p><Link href="/mypage">マイページへ</Link></main>;
  return <MainFortune mode="input" organizationId={org} organizationName={data.branding.display_name} />;
}
