export type GroupConfig = { classification: Record<string, string>; weights: Record<string, number> };
export const groupNames = ["地球", "月", "太陽"] as const;
export function aggregateGroups(rows: Array<{ pillar_key: string; juuni_unsei: string }>, config: GroupConfig) {
  const scores: Record<string, number> = { 地球: 0, 月: 0, 太陽: 0 };
  const pillars = new Set<string>();
  for (const row of rows) {
    if (pillars.has(row.pillar_key)) continue;
    pillars.add(row.pillar_key);
    const group = config.classification[row.juuni_unsei];
    const weight = config.weights[row.pillar_key];
    if (groupNames.includes(group as typeof groupNames[number]) && Number.isFinite(weight) && weight > 0) scores[group] += weight;
  }
  const total = groupNames.reduce((sum, name) => sum + scores[name], 0);
  return { scores, total, missing: Math.max(0, 100 - total) };
}
