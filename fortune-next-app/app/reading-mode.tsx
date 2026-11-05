"use client";
import { createContext, useContext } from "react";
import type { AuthUser } from "./auth";
import type { GroupConfig } from "./thinking-groups";
export type DisplayTheme = { key: string; display_name: string; definition: Record<string, string> };
export type Branding = { display_name: string; presentation_mode?: string; themes: DisplayTheme[]; selected_theme_key: string; thinking_groups: GroupConfig };
export type ReadingBootstrap = { enabled: boolean; user: AuthUser | null; organization_id: string | null; branding: Branding | null; default_theme: DisplayTheme; access_error?: string };
const Context = createContext<ReadingBootstrap | null>(null);
export const useReadingMode = () => useContext(Context);
export function ReadingModeProvider({ bootstrap, children }: { bootstrap: ReadingBootstrap | null; children: React.ReactNode }) {
  return <Context.Provider value={bootstrap}>{children}</Context.Provider>;
}
