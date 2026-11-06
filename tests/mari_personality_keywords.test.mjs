import assert from 'node:assert/strict';
import test from 'node:test';
import { MARI_PERSONALITY_KEYWORDS, mariPersonalityKeywords } from '../fortune-next-app/app/mari-personality-keywords.ts';
import { personalityPillars } from '../fortune-next-app/app/personality-pillars.ts';

// Independent acceptance transcript supplied by the user, including punctuation.
const approved = {
  比肩:'自我心・頑固・独立・努力家', 劫財:'協調・社交性・対等・政治力',
  食神:'趣味・自然体・味覚・平和', 傷官:'神経質・孤独・感受性・芸術',
  偏財:'愛情・現実主義・回転財・奉仕', 正財:'温厚・堅実・蓄財・常識・不動産',
  偏官:'行動力・責任感・正直・動乱', 正官:'自尊心・几帳面・自制心・地位名誉',
  偏印:'革新・創造・爆発・自由', 印綬:'知恵・学問・論理性・母性愛',
};
test('ten official entries exactly match the approved wording, order and separators', () => {
  assert.deepEqual(MARI_PERSONALITY_KEYWORDS, approved);
  assert.equal(Object.keys(MARI_PERSONALITY_KEYWORDS).length, 10);
  assert(Object.isFrozen(MARI_PERSONALITY_KEYWORDS));
  for (const [star, text] of Object.entries(approved)) assert.equal(mariPersonalityKeywords(star), text);
});
test('missing, dash, unknown and non-entry properties never receive keywords', () => {
  for (const star of ['', '－', '不明', '未入力', '未登録', 'toString', 'constructor', '__proto__', '比肩 ']) {
    assert.equal(mariPersonalityKeywords(star), undefined);
  }
});
test('the same official star in both slots resolves to the same approved keywords', () => {
  const hour = personalityPillars({hour_tsuhensei:'正財', hour_zokkan_tsuhensei:'正財'})[0];
  assert.equal(mariPersonalityKeywords(hour.tsuhensei), approved.正財);
  assert.equal(mariPersonalityKeywords(hour.zokkanTsuhensei), approved.正財);
});
