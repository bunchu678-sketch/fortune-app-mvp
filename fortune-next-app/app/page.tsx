import MainFortune from "./main-fortune";
import { readingBootstrap } from "./reading-bootstrap";
import { redirect } from "next/navigation";

export default async function Home() {
  const bootstrap = await readingBootstrap();
  if (bootstrap) {
    if (bootstrap.access_error) return <main className="appShell"><p role="alert">{bootstrap.access_error}</p></main>;
    if (!bootstrap.user) redirect("/login");
    return <MainFortune mode="input" organizationId={bootstrap.organization_id || undefined} organizationName={bootstrap.branding?.display_name} />;
  }
  return <MainFortune mode="input" />;
}
