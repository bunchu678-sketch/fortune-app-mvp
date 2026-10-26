"use client";

import { createContext, ReactNode, useContext, useState } from "react";
import type { HistoryLink, HistoryRecord, PastMemo, RerunDraft } from "./history-client";

export type FortuneSaved = {
  organizationId?: string;
  result: Record<string, any>;
  form: Record<string, any>;
  manualChoices: Record<string, "before" | "after">;
  boundarySelections?: Record<string, any>;
  link?: HistoryLink;
  memo?: string;
  pastMemos?: PastMemo[];
  history?: HistoryRecord;
};
type FortuneState = {
  saved: FortuneSaved | null;
  setSaved: (value: FortuneSaved | null) => void;
  draft: RerunDraft | null;
  setDraft: (value: RerunDraft | null) => void;
};
const Context = createContext<FortuneState | null>(null);
export function FortuneStateProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<FortuneSaved | null>(null);
  const [draft, setDraft] = useState<RerunDraft | null>(null);
  return <Context.Provider value={{ saved, setSaved, draft, setDraft }}>{children}</Context.Provider>;
}
export function useFortuneState() {
  const state = useContext(Context);
  if (!state) throw new Error("鑑定画面の状態を取得できません。");
  return state;
}
