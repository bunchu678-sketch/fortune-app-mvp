import "server-only";
import { cache } from "react";
import { headers } from "next/headers";
import type { ReadingBootstrap } from "./reading-mode";
import { apiOrigin, teacherUiEnabled } from "../api-origin.mjs";
export const readingBootstrap = cache(async (): Promise<ReadingBootstrap | null> => {
  if (!teacherUiEnabled()) return null;
  const origin = apiOrigin();
  const incoming = await headers();
  const result = await fetch(origin.replace(/\/+$/, "") + "/api/reading/bootstrap", {
    headers: { Cookie: incoming.get("cookie") || "" }, cache: "no-store", redirect: "error",
  });
  if (!result.ok) throw new Error("表示設定を取得できません。");
  const value = await result.json();
  if (!value.ok || !value.data?.enabled) throw new Error("アプリの接続設定を確認してください。");
  return value.data as ReadingBootstrap;
});
