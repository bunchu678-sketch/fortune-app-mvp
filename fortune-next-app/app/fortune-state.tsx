"use client";

import { createContext, ReactNode, useContext, useState } from "react";

export type FortuneSaved = {
  result: Record<string, any>;
  form: Record<string, any>;
  manualChoices: Record<string, "before" | "after">;
};

type FortuneState = {
  saved: FortuneSaved | null;
  setSaved: (value: FortuneSaved) => void;
};

const Context = createContext<FortuneState | null>(null);

export function FortuneStateProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<FortuneSaved | null>(null);
  return <Context.Provider value={{ saved, setSaved }}>{children}</Context.Provider>;
}

export function useFortuneState() {
  const state = useContext(Context);
  if (!state) throw new Error("鑑定画面の状態を取得できません。");
  return state;
}
