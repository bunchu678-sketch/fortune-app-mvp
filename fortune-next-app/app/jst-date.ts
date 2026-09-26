const JST_OFFSET_MS = 9 * 60 * 60 * 1000;

export function formatJstDate(instant: Date): string {
  const jst = new Date(instant.getTime() + JST_OFFSET_MS);
  const year = jst.getUTCFullYear();
  const month = String(jst.getUTCMonth() + 1).padStart(2, "0");
  const day = String(jst.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
