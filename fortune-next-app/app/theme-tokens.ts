import type { DisplayTheme } from "./reading-mode";
export const themeTokens = ["bg", "bg-soft", "panel", "panel-strong", "line", "ink", "muted", "soft", "accent", "accent-2", "accent-3", "blue", "button", "button-text", "danger", "shadow"];
export function selectedTheme(branding: { themes: DisplayTheme[]; selected_theme_key: string } | null, fallback: DisplayTheme) {
  return branding?.themes.find(theme => theme.key === branding.selected_theme_key) || branding?.themes[0] || fallback;
}
export function themeStyle(theme: DisplayTheme): Record<string, string> {
  return Object.fromEntries(themeTokens.flatMap(token => {
    const value = theme.definition[token === "bg" ? "background" : token === "ink" ? "foreground" : ""] || theme.definition[token];
    return typeof value === "string" && /^(#[0-9a-f]{3,8}|white|black|transparent)$/i.test(value) ? [[`--${token}`, value]] : [];
  }));
}
