"use client";
import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "./auth";
import { useFortuneState } from "./fortune-state";
import { productRequest, type Personal } from "./product-client";
import type { GroupConfig } from "./thinking-groups";
import "./teacher-theme.css";
import { useReadingMode } from "./reading-mode";
import { themeStyle, themeTokens } from "./theme-tokens";

type Theme = { key: string; display_name: string; definition: Record<string, string> };
type Branding = { presentation_mode?: string; themes: Theme[]; selected_theme_key: string; thinking_groups: GroupConfig };
type State = { organizationId: string; branding: Branding };
const Context = createContext<State | null>(null);
export const useTeacherTheme = () => useContext(Context);

export function TeacherThemeProvider({ children }: { children: React.ReactNode }) {
  const { user, isCurrentUser } = useAuth();
  const bootstrap = useReadingMode();
  const readingOnly = !!bootstrap?.enabled;
  const { saved } = useFortuneState();
  const pathname = usePathname();
  const [state, setState] = useState<State | null>(() => bootstrap?.branding && bootstrap.organization_id && user?.id === bootstrap.user?.id ? { organizationId: bootstrap.organization_id, branding: bootstrap.branding } : null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const sequence = useRef(0);
  const routeOrg = pathname.match(/^\/(?:b2b|teacher)\/([a-f0-9-]{36})(?:\/|$)/)?.[1];
  const resultOrg = pathname === "/result" ? saved?.organizationId : undefined;
  const requestedOrg = routeOrg || resultOrg;
  // The B2C input and B2C results always retain their existing presentation.
  const b2c = pathname === "/" || (pathname === "/result" && !resultOrg) || pathname.startsWith("/operations") || pathname.startsWith("/product");
  useEffect(() => {
    if (readingOnly) {
      if (!user || user.id !== bootstrap?.user?.id) { ++sequence.current; setState(null); }
      return;
    }
    const requestId = ++sequence.current;
    setState(null); setError(""); setBusy(false);
    if (!user || user.development || b2c) return;
    const owner = user.id;
    void (async () => {
      try {
        let org = requestedOrg;
        const historyId = pathname.match(/^\/history\/([a-f0-9-]{36})$/)?.[1];
        if (!org && historyId) {
          const reading = await productRequest<{ organization_id?: string }>(`/api/history/${historyId}`);
          if (!reading.organization_id) return;
          org = reading.organization_id;
        }
        if (!org) {
          const account = await productRequest<Personal>("/api/account/summary");
          if (account.is_operator || account.memberships.length !== 1) return;
          org = account.memberships[0].organization_id;
        }
        const data = await productRequest<{ organization_id: string; branding: Branding }>(`/api/b2b/organizations/${org}/me`);
        if (requestId === sequence.current && isCurrentUser(owner) && data.organization_id === org && data.branding.presentation_mode === "mari-keywords") {
          setState({ organizationId: org, branding: data.branding });
        }
      } catch { /* Existing page controls retain their own authorization/error handling. */ }
    })();
    return () => { ++sequence.current; };
  }, [user?.id, requestedOrg, b2c, pathname, readingOnly, bootstrap?.user?.id]);

  useLayoutEffect(() => {
    const fallback = bootstrap?.default_theme;
    const selected = state ? (state.branding.themes.find(item => item.key === state.branding.selected_theme_key) || state.branding.themes[0]) : fallback;
    if (!selected) return;
    const html = document.documentElement;
    html.dataset.teacherTheme = selected.key;
    for (const [token, value] of Object.entries(themeStyle(selected))) html.style.setProperty(token, value);
    return () => { delete html.dataset.teacherTheme; themeTokens.forEach(token => html.style.removeProperty(`--${token}`)); };
  }, [state, bootstrap?.default_theme]);

  async function select(key: string) {
    if (!state || !user || busy) return;
    const requestId = sequence.current, owner = user.id;
    setBusy(true); setError("");
    try {
      const branding = await productRequest<Branding>(readingOnly ? "/api/reading/theme" : `/api/b2b/organizations/${state.organizationId}/theme`, { method: "POST", body: JSON.stringify({ theme_key: key }) });
      if (requestId === sequence.current && isCurrentUser(owner)) setState({ ...state, branding });
    } catch (caught) {
      if (requestId === sequence.current && isCurrentUser(owner)) setError(caught instanceof Error ? caught.message : "テーマを保存できません。");
    } finally { if (requestId === sequence.current) setBusy(false); }
  }
  return <Context.Provider value={state}>
    {state ? <div className="teacherThemeControl"><label>表示テーマ
      <select aria-label="表示テーマ" value={state.branding.themes.some(item => item.key === state.branding.selected_theme_key) ? state.branding.selected_theme_key : "default"} disabled={busy} onChange={event => void select(event.target.value)}>
        {state.branding.themes.map(item => <option key={item.key} value={item.key}>{item.display_name}</option>)}
      </select></label>{busy ? <span role="status">保存中…</span> : null}{error ? <p role="alert">{error}</p> : null}</div> : null}
    {children}
  </Context.Provider>;
}
