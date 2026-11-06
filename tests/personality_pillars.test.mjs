import assert from 'node:assert/strict';
import test from 'node:test';
import { personalityPillars } from '../fortune-next-app/app/personality-pillars.ts';

test('distinct stem and hidden-stem stars stay with their own pillars in table order', () => {
  const stars = {hour_tsuhensei:'比肩', hour_zokkan_tsuhensei:'劫財',
    day_zokkan_tsuhensei:'食神', month_tsuhensei:'傷官', month_zokkan_tsuhensei:'偏財',
    year_tsuhensei:'正財', year_zokkan_tsuhensei:'偏官'};
  assert.deepEqual(personalityPillars(stars), [
    {key:'hour',label:'時柱',tsuhensei:'比肩',zokkanTsuhensei:'劫財'},
    {key:'day',label:'日柱',tsuhensei:'－',zokkanTsuhensei:'食神'},
    {key:'month',label:'月柱',tsuhensei:'傷官',zokkanTsuhensei:'偏財'},
    {key:'year',label:'年柱',tsuhensei:'正財',zokkanTsuhensei:'偏官'},
  ]);
});
test('unknown hour stays unknown; never borrow a different pillar or infer a star', () => {
  const cards = personalityPillars({hour_tsuhensei:'',hour_zokkan_tsuhensei:'',day_zokkan_tsuhensei:'印綬'});
  assert.equal(cards[0].tsuhensei,'不明');
  assert.equal(cards[0].zokkanTsuhensei,'不明');
  assert.equal(cards[1].zokkanTsuhensei,'印綬');
  assert.equal(cards[1].tsuhensei,'－');
});
