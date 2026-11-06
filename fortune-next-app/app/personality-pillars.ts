// Read the original per-pillar stars, never the age-stage presentation rows.
export function personalityPillars(stars: Record<string, unknown>) {
  return ([['hour', '時柱'], ['day', '日柱'], ['month', '月柱'], ['year', '年柱']] as const).map(([key, label]) => ({
    key,
    label,
    // The day stem is the reference; the existing meishiki table uses a dash.
    tsuhensei: key === 'day' ? '－' : String(stars[`${key}_tsuhensei`] || '不明'),
    zokkanTsuhensei: String(stars[`${key}_zokkan_tsuhensei`] || '不明'),
  }));
}
