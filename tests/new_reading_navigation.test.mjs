import assert from 'node:assert/strict';
import test from 'node:test';
import { newReadingDestination } from '../fortune-next-app/app/member-navigation.ts';
const org='11111111-1111-4111-8111-111111111111';
const other='22222222-2222-4222-8222-222222222222';
const member={organization_id:org,role:'student'};
const summary=memberships=>({is_operator:false,memberships});
const read=(account,access=member)=>async path=>path==='/api/account/summary'?account:access;

for(const role of ['student','teacher'])test(role+' new reading goes to input, not teacher management',async()=>{
  const calls=[];const membership={...member,role};
  assert.equal(await newReadingDestination(async path=>{calls.push(path);return path==='/api/account/summary'?summary([membership]):membership;}),'/b2b/'+org);
  assert.deepEqual(calls,['/api/account/summary','/api/b2b/organizations/'+org+'/me']);
});
test('B2C retains normal input',async()=>assert.equal(await newReadingDestination(read(summary([]))),'/'));
test('multiple organizations use the existing chooser without choosing an org',async()=>{
  const calls=[];assert.equal(await newReadingDestination(async path=>{calls.push(path);return summary([member,{...member,organization_id:other}]);}),'/mypage');
  assert.deepEqual(calls,['/api/account/summary']);
});
test('operator has no personal reading destination even with membership',async()=>assert.equal(await newReadingDestination(read({is_operator:true,memberships:[member]})),null));
for(const reason of ['suspended','unpaid','foreign','network failure'])test(reason+' never falls back to B2C',async()=>{
  assert.equal(await newReadingDestination(async path=>{if(path==='/api/account/summary')return summary([member]);throw Error(reason);}),'/mypage');
});
for(const value of [null,{}, {memberships:[]},{is_operator:false}])test('incomplete summary '+JSON.stringify(value)+' hides the link',async()=>assert.equal(await newReadingDestination(read(value)),null));
test('summary failure hides link; existing header remains the safe entrance',async()=>assert.equal(await newReadingDestination(async()=>{throw Error('offline');}),null));
test('untrusted organization identifier cannot become a link',async()=>assert.equal(await newReadingDestination(read(summary([{...member,organization_id:'//outside.test'}]))),'/mypage'));
test('unknown membership role cannot open input',async()=>assert.equal(await newReadingDestination(read(summary([{...member,role:'admin'}]))),'/mypage'));
test('unexpected organization in permission response is rejected',async()=>assert.equal(await newReadingDestination(read(summary([member]),{...member,organization_id:other})),'/mypage'));
test('unexpected permission role is rejected',async()=>assert.equal(await newReadingDestination(read(summary([member]),{...member,role:'admin'})),'/mypage'));
