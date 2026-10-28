"""Run actual nginx on new loopback high ports with synthetic TLS/upstreams only."""
from pathlib import Path
import http.client,json,os,re,socket,ssl,subprocess,sys,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
HOME=Path(sys.argv[1]).resolve();assert HOME.is_dir() and not HOME.is_symlink()
LAB=HOME/'nginx-security-lab';assert not LAB.exists();LAB.mkdir(mode=0o700)
DOMAINS={'b2c':'app.hakase-uranai.jp','teacher':'mari-mutsuro.hakase-uranai.jp','admin':'admin.hakase-uranai.jp'}
servers=[];threads=[];checks=[];process=None
class Upstream(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):self.do_GET()
    def do_GET(self):
        role=self.server.role;p=self.path;status=200;body=b'<!doctype html><html><body>synthetic page</body></html>'
        if p.startswith('/api/'):
            if role=='admin' and not p.startswith(('/api/operations/','/api/auth/','/api/account/')):status=404
            elif p=='/api/probe403':status=403
            elif p in ('/api/auth/me','/api/history','/api/operations/invitations'):status=401
            elif p=='/api/export/excel':body=b'PK-synthetic-xlsx'
            else:body=b'{"ok":true}'
        elif p=='/__absent':status=404
        self.send_response(status);self.send_header('Content-Type','text/html' if not p.startswith('/api/') else 'application/json')
        for k,v in [('X-Powered-By','fixture'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','upstream-policy')]:self.send_header(k,v)
        if p.startswith('/api/'):self.send_header('Cache-Control','no-store')
        if p=='/api/auth/me':self.send_header('Set-Cookie','synthetic_session=fixture; Path=/; Secure; HttpOnly; SameSite=Lax')
        if p=='/api/export/excel':self.send_header('Content-Disposition','attachment; filename="synthetic.xlsx"')
        self.end_headers();self.wfile.write(body)
def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def verify(label,condition):
    if not condition:raise AssertionError(label)
    checks.append(label)
try:
    for role in ('web','b2c','teacher','admin'):
        s=ThreadingHTTPServer(('127.0.0.1',0),Upstream);s.role=role;servers.append(s)
        t=threading.Thread(target=s.serve_forever,daemon=True);t.start();threads.append(t)
    upstreams=dict(zip(('web','b2c','teacher','admin'),[s.server_port for s in servers]))
    http_port,tls_port=port(),port();verify('private high ports',http_port>1024 and tls_port>1024 and http_port!=tls_port)
    cert,key=LAB/'cert.pem',LAB/'key.pem'
    san='subjectAltName='+','.join('DNS:'+v for v in DOMAINS.values())
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=synthetic-security-lab','-addext',san,'-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    key.chmod(0o600)
    snippets=ROOT/'deployment/security';configs=[]
    for role,name in (('b2c','fortune-app'),('teacher','fortune-mari'),('admin','fortune-admin')):
        text=(snippets/(name+'.conf.candidate')).read_text()
        text=text.replace('listen [::]:443 ssl ipv6only=on;',f'listen [::1]:{tls_port} ssl ipv6only=on;').replace('listen 443 ssl;',f'listen 127.0.0.1:{tls_port} ssl;')
        text=text.replace('listen [::]:80;',f'listen [::1]:{http_port};').replace('listen 80;',f'listen 127.0.0.1:{http_port};')
        text=text.replace(f'/etc/nginx/snippets/fortune-security-{role}.conf',str(snippets/f'fortune-security-{role}.conf'))
        text=re.sub(r'/etc/letsencrypt/live/[^/]+/fullchain.pem',str(cert),text)
        text=re.sub(r'/etc/letsencrypt/live/[^/]+/privkey.pem',str(key),text)
        # TLS cipher settings/DH are not changed in the proposal. Lab certificate is synthetic.
        text=re.sub(r'^\s*(?:include /etc/letsencrypt/options-ssl-nginx.conf|ssl_dhparam [^;]+);[^\n]*\n','',text,flags=re.M)
        for original,target in ((8765,'b2c'),(8771,'teacher'),(8772,'admin'),(3000,'web'),(3011,'web')):text=text.replace('http://127.0.0.1:'+str(original),'http://127.0.0.1:'+str(upstreams[target]))
        for slug in ('mari','admin'):
            acme=LAB/('acme-'+slug);(acme/'.well-known/acme-challenge').mkdir(parents=True,exist_ok=True)
            (acme/'.well-known/acme-challenge/synthetic').write_text('synthetic-challenge')
            text=text.replace('/var/www/fortune-'+slug+'-acme',str(acme))
        configs.append(text)
    # Explicit child-header fixture verifies the nginx 1.24 inheritance rule and remedy.
    inheritance=f'''server {{ listen 127.0.0.1:{http_port}; server_name inheritance.example.test;
        include {snippets}/fortune-security-teacher.conf;
        location / {{ include {snippets}/fortune-security-teacher.conf; add_header Cache-Control "no-store" always; return 403; }} }}'''
    configuration=f'''pid {LAB}/nginx.pid;
error_log {LAB}/error.log;
events {{ worker_connections 128; }}
http {{ access_log off; client_body_temp_path {LAB}/client; proxy_temp_path {LAB}/proxy;
{''.join(configs)}
{inheritance}
}}
'''
    config=LAB/'nginx.conf';config.write_text(configuration)
    r=subprocess.run(['nginx','-t','-p',str(LAB)+'/', '-c',str(config)],capture_output=True,text=True)
    (LAB/'syntax.log').write_text(r.stdout+r.stderr);verify('actual nginx syntax',r.returncode==0)
    process=subprocess.Popen(['nginx','-p',str(LAB)+'/', '-c',str(config),'-g','daemon off;'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for _ in range(50):
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1',tls_port))==0:break
        assert process.poll() is None;time.sleep(.1)
    context=ssl.create_default_context(cafile=str(cert))
    def request(role,path,method='GET',tls=True):
        host=DOMAINS.get(role,role)
        if tls:
            raw=socket.create_connection(('127.0.0.1',tls_port),timeout=4)
            conn=http.client.HTTPConnection(host);conn.sock=context.wrap_socket(raw,server_hostname=host)
        else:conn=http.client.HTTPConnection('127.0.0.1',http_port,timeout=4)
        conn.request(method,path,headers={'Host':host,'Origin':'https://'+host})
        response=conn.getresponse();body=response.read();headers=response.getheaders();status=response.status;conn.close()
        return status,{k.lower():[v for n,v in headers if n.lower()==k.lower()] for k,v in headers},body
    def headers(role,values,label):
        expected={'strict-transport-security':'max-age=300','x-frame-options':'DENY','content-security-policy':"frame-ancestors 'none'; base-uri 'self'; object-src 'none'",'x-content-type-options':'nosniff','referrer-policy':'strict-origin-when-cross-origin' if role=='b2c' else 'no-referrer'}
        verify(label+' exact single security headers',all(values.get(k)==[v] for k,v in expected.items()))
        verify(label+' no framework/version or CORS',not values.get('x-powered-by') and values.get('server')==['nginx'] and not values.get('access-control-allow-origin'))
    for role in DOMAINS:
        for path in ('/','/login','/reset-password','/forgot-password','/api/auth/me','/api/probe403','/__absent'):
            status,h,body=request(role,path);headers(role,h,role+path)
            if path=='/api/auth/me':verify(role+' 401/cookie/no-store',status==401 and h.get('cache-control')==['no-store'] and h.get('set-cookie')==['synthetic_session=fixture; Path=/; Secure; HttpOnly; SameSite=Lax'])
            if path=='/api/probe403':verify(role+' representative denial',status==(404 if role=='admin' else 403))
            if path=='/__absent':verify(role+' 404 response',status==404)
        status,h,body=request(role,'/api/export/excel','POST');headers(role,h,role+' download')
        verify(role+' download routing',status==(404 if role=='admin' else 200))
        if role!='admin':verify(role+' download unchanged',body==b'PK-synthetic-xlsx' and h['content-disposition']==['attachment; filename="synthetic.xlsx"'] and h['cache-control']==['no-store'])
    verify('teacher unscoped fortune exact path blocked',request('teacher','/api/fortune','POST')[0]==404)
    verify('teacher unscoped fortune slash blocked',request('teacher','/api/fortune/','POST')[0]==404)
    verify('b2c unscoped fortune retained',request('b2c','/api/fortune','POST')[0]==200)
    verify('teacher scoped fortune routing retained',request('teacher','/api/b2b/organizations/synthetic/fortune','POST')[0]==200)
    verify('teacher operations API blocked',request('teacher','/api/operations/invitations')[0]==404)
    verify('teacher operations admin redirect',request('teacher','/operations')[1].get('location')==['https://admin.hakase-uranai.jp/operations'])
    redirects=[urlsplit(request('teacher',path)[1]['location'][0]) for path in ('/','/product','/product/')]
    verify('teacher root and legacy input go to member entry',all(u.hostname==DOMAINS['teacher'] and u.path=='/mypage' and u.scheme=='https' for u in redirects))
    verify('admin non-management API blocked',request('admin','/api/history')[0]==404)
    for role in ('teacher','admin'):
        status,h,body=request(role,'/.well-known/acme-challenge/synthetic',tls=False);verify(role+' ACME reachable over HTTP',status==200 and body==b'synthetic-challenge')
    status,h,body=request('inheritance.example.test','/',tls=False);headers('teacher',h,'child add_header with repeated include')
    verify('child no-store preserved',status==403 and h['cache-control']==['no-store'])
    result={'checks':len(checks),'passed':True,'actual_nginx':True,'private_loopback_high_ports':True,'synthetic_tls_upstreams_only':True,'normal_fixture_CA_hostname_validation':True,'production_config_or_reload':False,'lab_directory':str(LAB)}
    (HOME/'nginx-security-result.json').write_text(json.dumps(result));print(json.dumps(result))
finally:
    if process is not None:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    for server in servers:server.shutdown();server.server_close()
