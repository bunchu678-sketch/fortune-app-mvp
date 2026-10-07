/** Reset links carry secrets only in the fragment, never in a request URL. */
export function readResetToken(href: string): string {
  try {
    const token = new URLSearchParams(new URL(href).hash.slice(1)).get("token") ?? "";
    return /^[A-Za-z0-9_-]{40,200}$/.test(token) ? token : "";
  } catch { return ""; }
}
