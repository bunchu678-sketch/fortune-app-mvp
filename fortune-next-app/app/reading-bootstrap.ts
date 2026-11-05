import "server-only";
import { cache } from "react";
import { headers } from "next/headers";
import type { ReadingBootstrap } from "./reading-mode";
export const readingBootstrap = cache(async (): Promise<ReadingBootstrap | null> => {
  if (process.env.FORTUNE_UI_SURFACE !== "teacher") return null;
  const incoming = await headers();
  const origin = process.env.FORTUNE_API_ORIGIN || "http://127.0.0.1:8765";
  const result = await fetch(origin.replace(/\/+$/, "") + "/api/reading/bootstrap", {
    headers: { Cookie: incoming.get("cookie") || "" }, cache: "no-store", redirect: "error",
  });
  if (!result.ok) throw new Error("表示設定を取得できません。");
  const value = await result.json();
  if (!value.ok || !value.data?.enabled) throw new Error("アプリの接続設定を確認してください。");
  return value.data as ReadingBootstrap;
});
