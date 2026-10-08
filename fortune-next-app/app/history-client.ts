import { API_BASE } from "./auth";
import { formatJstDate } from "./jst-date";

export type HistoryLink = {
  mode: "new_person" | "new_group" | "existing_group";
  person_id?: string; group_id?: string; source_reading_id?: string;
};
export type PastMemo = { id: string; reading_date: string; memo: string };
export type HistoryRecord = {
  organization_id?: string;
  id: string; person_id: string; group_id: string; reading_date: string;
  saved_at: string; updated_at: string; memo: string;
  input_snapshot: { form: Record<string, any>; manualChoices: Record<string, "before" | "after">;
    boundarySelections?: Record<string, any> };
  result_snapshot: Record<string, any>; past_memos?: PastMemo[];
};
export type PersonCandidate = {
  id: string; surname: string; givenName: string; birthDate: string; birthPlace: string;
  histories: Array<{ id: string; group_id: string; reading_date: string; saved_at: string }>;
};
export type RerunDraft = {
  organizationId?: string;
  form: Record<string, any>; manualChoices: Record<string, "before" | "after">;
  boundarySelections: Record<string, any>; link: HistoryLink; pastMemos: PastMemo[];
};
export class HistoryRequestError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
export async function historyRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(API_BASE + "/api/history" + path, {
    ...options, credentials: "same-origin", headers: { "Content-Type": "application/json", ...options?.headers }, cache: "no-store",
  });
  const body = await response.json();
  if (!response.ok || !body.ok) throw new HistoryRequestError(body.error || "履歴の処理に失敗しました。", response.status);
  return body.data as T;
}
export const displayName = (form: Record<string, any>) =>
  [form.surname ?? "", form.givenName ?? ""].join("").trim() || "無記名";
export const displayKana = (form: Record<string, any>) =>
  [form.surnameKana ?? "", form.givenNameKana ?? ""].join("");
export const savedTime = (value: string) => new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
}).format(new Date(value));
export const rerunToday = () => formatJstDate(new Date());
