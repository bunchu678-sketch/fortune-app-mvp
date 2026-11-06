// Teacher-only presentation data, transcribed verbatim from the user's table.
// Source: Diviner Romari 四柱推命鑑定士：中級編, pp. 38–41.
// User confirmed the same keywords apply to stem and hidden-stem stars.
export const MARI_PERSONALITY_KEYWORDS = Object.freeze({
  比肩: "自我心・頑固・独立・努力家",
  劫財: "協調・社交性・対等・政治力",
  食神: "趣味・自然体・味覚・平和",
  傷官: "神経質・孤独・感受性・芸術",
  偏財: "愛情・現実主義・回転財・奉仕",
  正財: "温厚・堅実・蓄財・常識・不動産",
  偏官: "行動力・責任感・正直・動乱",
  正官: "自尊心・几帳面・自制心・地位名誉",
  偏印: "革新・創造・爆発・自由",
  印綬: "知恵・学問・論理性・母性愛",
});

export function mariPersonalityKeywords(star: string): string | undefined {
  return Object.hasOwn(MARI_PERSONALITY_KEYWORDS, star)
    ? MARI_PERSONALITY_KEYWORDS[star as keyof typeof MARI_PERSONALITY_KEYWORDS]
    : undefined;
}
