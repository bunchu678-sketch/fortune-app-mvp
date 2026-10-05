"""Exact production settings on temporary SQLite; no VPS or public network access."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import auth_cases as ac
from auth_service import AuthRepository, token_hash
from history_repository import SQLiteHistoryRepository
from history_service import HistoryService
from report_export_cases import FORM
from fortune_service import calculate_fortune
from tier_b import api_app
from proxy_settings import proxy_settings
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
ORIGIN='https://app.hakase-uranai.jp'

class ProductionCases(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.result=calculate_fortune(FORM)
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='fortune-predeploy-');self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/'isolated.sqlite3'
  self.env=patch.dict(os.environ,{'FORTUNE_ENV':'production','FORTUNE_PUBLIC_ORIGIN':ORIGIN,
   'FORTUNE_HISTORY_DB_PATH':str(self.path),'FORTUNE_HISTORY_DEV_USER_ID':'must-not-grant-access',
   'FORTUNE_PDF_CONVERTER':'disabled','FORTUNE_PROXY_HEADERS':'1','FORTUNE_TRUSTED_PROXY_IPS':'127.0.0.1',
   'FORTUNE_SESSION_TTL_HOURS':'24','FORTUNE_LOGIN_WINDOW_SECONDS':'900',
   'FORTUNE_LOGIN_ACCOUNT_LIMIT':'10','FORTUNE_LOGIN_IP_LIMIT':'30'})
  self.env.start();self.addCleanup(self.env.stop)
  self.password=secrets.token_urlsafe(24);self.repo=AuthRepository()
  self.a=self.repo.create_user('production.a@example.test',self.password)
  self.b=self.repo.create_user('production.b@example.test',self.password)
  self.history=SQLiteHistoryRepository(self.path)
  self.reading=HistoryService(self.history).create(self.a['id'],{'input_snapshot':{'form':FORM},'result_snapshot':deepcopy(self.result),'memo':'synthetic'})
  app=ProxyHeadersMiddleware(api_app(),trusted_hosts=proxy_settings()['forwarded_allow_ips'])
  self.app_patch=patch.object(ac,'api_app',return_value=app);self.app_patch.start();self.addCleanup(self.app_patch.stop)
 def call(self,method,path,payload=None,**kw):
  kw.setdefault('origin',ORIGIN);kw.setdefault('headers',{'X-Forwarded-For':'198.51.100.21'})
  return asyncio.run(ac.api_request(method,path,payload,**kw))
 def login(self,who='a',password=None):
  user=self.a if who=='a' else self.b
  status,headers,_=self.call('POST','/api/auth/login',{'email':user['email'],'password':password or self.password})
  self.assertEqual(status,200)
  return headers[b'set-cookie'].decode().split(';',1)[0].split('=',1)[1]
 def test_cookie_and_me(self):
  status,headers,_=self.call('POST','/api/auth/login',{'email':self.a['email'],'password':self.password})
  self.assertEqual(status,200);cookie=headers[b'set-cookie'].decode()
  self.assertTrue(all(value in cookie for value in ['Secure','HttpOnly','SameSite=lax','Path=/']))
  token=cookie.split(';',1)[0].split('=',1)[1]
  self.assertEqual(json.loads(self.call('GET','/api/auth/me',cookie=token)[2])['data']['user']['id'],self.a['id'])
 def test_csrf_spoof_and_dev_fallback(self):
  self.assertEqual(self.call('GET','/api/history?user_id='+self.a['id'])[0],401)
  for origin in (None,'https://evil.example.test'):
   self.assertEqual(self.call('POST','/api/auth/login',{'email':self.a['email'],'password':self.password},origin=origin,headers={'X-Forwarded-For':'192.0.2.9','X-Forwarded-Host':'evil.example.test','X-Forwarded-Proto':'https'})[0],403)
  a=self.login();b=self.login('b')
  self.assertEqual(self.call('GET','/api/history/'+self.reading['id']+'?user_id='+self.a['id'],cookie=b,headers={'X-User-Id':self.a['id']})[0],404)
  self.assertEqual(self.call('PATCH','/api/history/'+self.reading['id']+'/memo',{'memo':'spoof','updated_at':self.reading['updated_at'],'user_id':self.b['id']},cookie=a,origin='https://evil.example.test')[0],403)
 def test_disable_password_change_and_expiry(self):
  token=self.login();self.repo.change_user(self.a['email'],'disable')
  self.assertEqual(self.call('GET','/api/auth/me',cookie=token)[0],401)
  self.repo.change_user(self.a['email'],'enable');self.assertEqual(self.call('GET','/api/auth/me',cookie=token)[0],401)
  token=self.login();new_password=secrets.token_urlsafe(24);self.repo.change_user(self.a['email'],'set-password',new_password)
  self.assertEqual(self.call('GET','/api/auth/me',cookie=token)[0],401)
  self.assertEqual(self.call('POST','/api/auth/login',{'email':self.a['email'],'password':self.password})[0],401)
  token=self.login(password=new_password)
  with self.repo.connection() as db: db.execute('UPDATE auth_sessions SET expires_at=0 WHERE token_hash=?',(token_hash(token),))
  self.assertEqual(self.call('GET','/api/auth/me',cookie=token)[0],401)
 def test_account_rate_limit(self):
  for _ in range(10):self.assertEqual(self.call('POST','/api/auth/login',{'email':self.a['email'],'password':'synthetic-wrong'})[0],401)
  status,headers,_=self.call('POST','/api/auth/login',{'email':self.a['email'],'password':'synthetic-wrong'})
  self.assertEqual(status,429);self.assertEqual(headers[b'retry-after'],b'900');self.login('b')
 def test_ip_rate_limit_and_forwarded_ip_hash(self):
  for n in range(30):self.assertEqual(self.call('POST','/api/auth/login',{'email':f'missing{n}@example.test','password':'synthetic-wrong'})[0],401)
  self.assertEqual(self.call('POST','/api/auth/login',{'email':'another@example.test','password':'synthetic-wrong'})[0],429)
  with self.repo.connection() as db:keys=db.execute('SELECT DISTINCT ip_key FROM auth_login_attempts').fetchall()
  self.assertEqual(len(keys),1);self.assertTrue(keys[0][0]==token_hash('198.51.100.21'))
 def test_excel_pdf_and_session_bound_tokens(self):
  a=self.login();b=self.login('b')
  status,_,body=self.call('POST','/api/fortune',FORM,cookie=a);self.assertEqual(status,200)
  token=json.loads(body)['excel_export_token']
  for payload in ({'reading_id':self.reading['id']},{'export_token':token}):
   self.assertEqual(self.call('POST','/api/export/excel',payload,cookie=a)[2][:2],b'PK')
   self.assertEqual(self.call('POST','/api/export/pdf',payload,cookie=b)[0],404)
   status,_,body=self.call('POST','/api/export/pdf',payload,cookie=a)
   self.assertEqual(status,503);self.assertEqual(json.loads(body)['code'],'converter_unavailable')
  a2=self.login()
  self.assertEqual(self.call('POST','/api/export/excel',{'export_token':token},cookie=a2)[0],404)
  self.assertFalse(json.loads(self.call('GET','/api/export-capabilities')[2])['data']['pdf_available'])
 def test_hash_storage_and_logout(self):
  token=self.login()
  with self.repo.connection() as db:
   user=db.execute('SELECT password_hash FROM users WHERE id=?',(self.a['id'],)).fetchone()[0]
   session=db.execute('SELECT token_hash FROM auth_sessions WHERE user_id=?',(self.a['id'],)).fetchone()[0]
  self.assertTrue(user.startswith('$argon2id$'));self.assertTrue(self.password not in user,'Password must not be plaintext')
  self.assertTrue(session==token_hash(token),'Session must be hash-only')
  self.assertEqual(self.call('POST','/api/auth/logout',{},cookie=token)[0],200)
  self.assertEqual(self.call('GET','/api/auth/me',cookie=token)[0],401)

if __name__=='__main__':unittest.main(verbosity=2)
