"use client";

import { createContext, ReactNode, useContext, useState } from "react";

export type ProductSaved = {
  result: Record<string, any>;
  form: Record<string, any>;
  boundaryInfo: Record<string, any>[];
  manualChoices: Record<string, "before" | "after">;
};
type ProductState = { saved: ProductSaved | null; setSaved: (value: ProductSaved) => void };
const Context = createContext<ProductState | null>(null);

export function ProductStateProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<ProductSaved | null>(null);
  return <Context.Provider value={{ saved, setSaved }}>{children}</Context.Provider>;
}

export function useProductState() {
  const state = useContext(Context);
  if (!state) throw new Error("商品版の画面状態を取得できません。");
  return state;
}
