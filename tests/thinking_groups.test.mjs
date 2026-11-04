import assert from 'node:assert/strict';
import test from 'node:test';
import { aggregateGroups } from '../fortune-next-app/app/thinking-groups.ts';
const config = { classification: Object.fromEntries(Object.entries({地球:['胎','長生','帝旺','病'],月:['養','衰','冠帯','墓'],太陽:['絶','建禄','沐浴','死']}).flatMap(([g,stars])=>stars.map(s=>[s,g]))), weights:{year:15,month:30,day:50,hour:5} };
const rows = (year,month,day,hour) => Object.entries({year,month,day,hour}).map(([pillar_key,juuni_unsei])=>({pillar_key,juuni_unsei}));
test('weighted example 45/50/5',()=>assert.deepEqual(aggregateGroups(rows('胎','長生','養','絶'),config),{scores:{地球:45,月:50,太陽:5},total:100,missing:0}));
for(const [star,group] of Object.entries(config.classification)) test(star+' full allocation',()=>{
  const value=aggregateGroups(rows(star,star,star,star),config);
  assert.equal(value.scores[group],100);assert.equal(value.total,100);assert.equal(value.missing,0);
});
test('unknown hour remains unallocated, no renormalization',()=>assert.deepEqual(aggregateGroups(rows('胎','長生','養',''),config),{scores:{地球:45,月:50,太陽:0},total:95,missing:5}));
test('unknown star and duplicate pillar do not inflate values',()=>{
 const value=aggregateGroups([...rows('胎','未登録','養','絶'),{pillar_key:'day',juuni_unsei:'養'}],config);
 assert.deepEqual(value,{scores:{地球:15,月:50,太陽:5},total:70,missing:30});
});
