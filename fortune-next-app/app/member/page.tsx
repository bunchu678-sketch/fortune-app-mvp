"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LoginRequired, useAuth } from "../auth";
import { memberDestination } from "../member-navigation";
import { productRequest } from "../product-client";
import "../management.css";

export default function MemberHome() {
  const { user, loading, isCurrentUser } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!user || loading) return;
    let active = true;
    void memberDestination(null, path => productRequest(path)).then(destination => {
      if (active && isCurrentUser(user.id)) router.replace(destination);
    });
    return () => { active = false; };
  }, [user?.id, loading, router, isCurrentUser]);
  return <main className="appShell managementPage"><h1>マイページ</h1>
    {user ? <p role="status">利用権限を確認して初期画面へ移動しています…</p> : <LoginRequired next="/member" />}
  </main>;
}
