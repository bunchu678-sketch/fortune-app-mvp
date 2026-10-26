"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, useAuth } from "./auth";

export class ProductRequestError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
export async function productRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(API_BASE + path, { ...options, credentials: "same-origin", cache: "no-store",
    headers: { "Content-Type": "application/json", ...options.headers } });
  const value = await response.json();
  if (!response.ok || !value.ok) throw new ProductRequestError(value.error || value.errors?.join(" / ") || "処理に失敗しました。", response.status);
  return value.data as T;
}
export function useProductData<T>(path: string) {
  const { user } = useAuth(); const sequence = useRef(0);
  const [data, setData] = useState<T | null>(null), [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    const id = ++sequence.current; setLoading(true); setError("");
    try { const value = await productRequest<T>(path); if (id === sequence.current) setData(value); }
    catch (caught) { if (id === sequence.current) { setData(null); setError(caught instanceof Error ? caught.message : "取得できません。"); } }
    finally { if (id === sequence.current) setLoading(false); }
  }, [path]);
  useEffect(() => { if (user) void reload(); else { ++sequence.current; setData(null); setLoading(false); }
    return () => { ++sequence.current; };
  }, [user?.id, reload]);
  return { data, error, loading, reload };
}
export type Totals = { executions_this_month: number; executions_total: number; month_timezone: string };
export type Personal = Totals & { saved_histories_current: number; saved_histories_total: number; deleted_histories: number;
  email: string; is_operator: boolean; memberships: Array<{ organization_id: string; display_name: string; role: string }> };
export type Organization = Totals & { id: string; display_name: string; slug: string; students: number };
export const accountLabel = (state: string) => ({ active: "利用中", suspended: "停止中", deletion_pending: "削除待機", terminated: "利用終了", deleted: "削除済み" }[state] ?? state);
