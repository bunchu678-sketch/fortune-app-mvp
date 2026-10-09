// All role/permission information comes from authenticated existing endpoints.
export type Membership = { organization_id: string; display_name: string; role: string };
type Summary = { is_operator: boolean; memberships: Membership[] };
type Read = (path: string) => Promise<unknown>;
const id = "[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}";

export async function memberDestination(next: string | null, read: Read): Promise<string> {
  if (next && ["/", "/mypage", "/history", "/history/deleted"].includes(next)) return next;
  let endpoint: string | null = null;
  const reading = next?.match(new RegExp("^/history/(" + id + ")$"));
  const member = next?.match(new RegExp("^/(b2b|teacher)/(" + id + ")$"));
  const operation = next?.match(new RegExp("^/operations/(organizations|users)/(" + id + ")$"));
  if (reading) endpoint = "/api/history/" + reading[1];
  if (member) endpoint = "/api/b2b/organizations/" + member[2] + (member[1] === "teacher" ? "/teacher" : "/me");
  if (next === "/operations") endpoint = "/api/operations/organizations";
  if (operation) endpoint = "/api/operations/" + operation[1] + "/" + operation[2];
  if (endpoint) {
    try { await read(endpoint); return next!; } catch { /* Fall back to an authorized member entrance. */ }
  }
  try {
    const summary = await read("/api/account/summary") as Summary;
    if (summary.is_operator === true) return "/operations";
    if (Array.isArray(summary.memberships) && summary.memberships.length === 1) {
      const membership = summary.memberships[0];
      if (membership.role === "teacher" && new RegExp("^" + id + "$").test(membership.organization_id)) {
        await read("/api/b2b/organizations/" + membership.organization_id + "/teacher");
        return "/teacher/" + membership.organization_id;
      }
    }
  } catch { /* Missing information or suspended access: keep the safe entrance. */ }
  return "/mypage";
}
