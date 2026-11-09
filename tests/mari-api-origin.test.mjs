import test from 'node:test';
import assert from 'node:assert/strict';
import { apiOrigin, TEACHER_SURFACE } from '../fortune-next-app/api-origin.mjs';
import { mkdtempSync, copyFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

test('ordinary doctor/admin API defaults remain intact',()=>{
  assert.equal(apiOrigin({}),'http://127.0.0.1:8765');
  assert.equal(apiOrigin({FORTUNE_API_ORIGIN:'http://127.0.0.1:8772'}),'http://127.0.0.1:8772');
});
test('marked dedicated config refuses direct Next loading with omitted or wrong origin',()=>{
  const dir=mkdtempSync(join(tmpdir(),'mari-config-'));
  try{
    for(const name of ['api-origin.mjs','next.config.mjs'])copyFileSync(new URL('../fortune-next-app/'+name,import.meta.url),join(dir,name));
    writeFileSync(join(dir,'.mari-reading-release'),'teacher\n');
    const clean=Object.fromEntries(Object.entries(process.env).filter(([k])=>!k.startsWith('FORTUNE_')));
    for(const extra of [{},{FORTUNE_UI_SURFACE:'teacher'},{FORTUNE_UI_SURFACE:'teacher',FORTUNE_API_ORIGIN:'http://127.0.0.1:8765'}]){
      const p=spawnSync(process.execPath,['--input-type=module','-e',`await import(${JSON.stringify(pathToFileURL(join(dir,'next.config.mjs')).href)})`],{env:{...clean,...extra},encoding:'utf8',windowsHide:true});
      assert.notEqual(p.status,0);assert.match(p.stderr,/Teacher API connection/);
    }
  }finally{rmSync(dir,{recursive:true,force:true});}
});
test('teacher requires explicit dedicated API; never forwards to another surface',()=>{
  const env={FORTUNE_UI_SURFACE:'teacher',FORTUNE_REQUIRED_DEPLOYMENT_SURFACE:TEACHER_SURFACE};
  for(const origin of [undefined,'','http://127.0.0.1:8765','http://127.0.0.1:8771',
    'http://127.0.0.1:8772','https://other.example.test','http://user:pass@127.0.0.1:8773','http://127.0.0.1:8773/api']){
    assert.throws(()=>apiOrigin({...env,FORTUNE_API_ORIGIN:origin}));
  }
  assert.equal(apiOrigin({...env,FORTUNE_API_ORIGIN:'http://127.0.0.1:8773/'}),'http://127.0.0.1:8773');
  assert.throws(()=>apiOrigin({FORTUNE_API_ORIGIN:'http://127.0.0.1:8773'},true));
});
