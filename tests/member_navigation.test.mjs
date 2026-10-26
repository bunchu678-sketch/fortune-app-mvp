import assert from 'node:assert/strict';
import test from 'node:test';
import { memberDestination } from '../fortune-next-app/app/member-navigation.ts';
const org = '11111111-1111-4111-8111-111111111111';
const other = '22222222-2222-4222-8222-222222222222';
const teacher = { organization_id: org, role: 'teacher' };
const student = { organization_id: org, role: 'student' };
const deny = () => { throw Error('denied'); };
const read = (summary, denied = []) => async path => {
  if (denied.includes(path)) return deny();
  return path === '/api/account/summary' ? summary : {};
};
for (const [name, summary, expected] of [
  ['B2C', {memberships: []}, '/mypage'],
  ['student', {memberships: [student]}, '/mypage'],
  ['teacher', {memberships: [teacher]}, '/teacher/' + org],
  ['operator takes precedence', {is_operator: true, memberships: [teacher]}, '/operations'],
  ['multiple teachers', {memberships: [teacher, {...teacher, organization_id: other}]}, '/mypage'],
  ['teacher and student in different orgs', {memberships: [teacher, {...student, organization_id: other}]}, '/mypage'],
  ['insufficient metadata', {}, '/mypage'],
  ['unknown role', {memberships: [{...teacher, role: 'admin'}]}, '/mypage'],
  ['untrusted organization id', {memberships: [{...teacher, organization_id: '//outside.test'}]}, '/mypage'],
]) test(name, async () => assert.equal(await memberDestination(null, read(summary)), expected));
test('metadata network error falls back safely', async () => assert.equal(await memberDestination(null, deny), '/mypage'));
test('teacher suspended access falls back safely', async () => assert.equal(await memberDestination(null, read({memberships: [teacher]}, ['/api/b2b/organizations/' + org + '/teacher'])), '/mypage'));
for (const next of ['/', '/mypage', '/history', '/history/deleted'])
  test('authenticated self/public next ' + next, async () => assert.equal(await memberDestination(next, deny), next));
for (const [next, endpoint] of [
  ['/history/' + org, '/api/history/' + org],
  ['/b2b/' + org, '/api/b2b/organizations/' + org + '/me'],
  ['/teacher/' + org, '/api/b2b/organizations/' + org + '/teacher'],
  ['/operations', '/api/operations/organizations'],
  ['/operations/organizations/' + org, '/api/operations/organizations/' + org],
  ['/operations/users/' + org, '/api/operations/users/' + org],
]) {
  test('authorized next ' + next, async () => { const calls = []; assert.equal(await memberDestination(next, async path => {calls.push(path); return {};}), next); assert.deepEqual(calls, [endpoint]); });
  test('denied next ' + next, async () => assert.equal(await memberDestination(next, read({memberships: []}, [endpoint])), '/mypage'));
}
for (const next of ['https://outside.test', '//outside.test', '/\\outside.test', '/%2f%2foutside.test', '/operations/../login', '/teacher/' + org + '?evil=yes', '/mypage#bad', '/login', '/result', '/teacher/not-an-id', ' /mypage'])
  test('reject non-allowlisted next ' + next, async () => { const calls = []; assert.equal(await memberDestination(next, async path => {calls.push(path); return {memberships: []};}), '/mypage'); assert.deepEqual(calls, ['/api/account/summary']); });
