"""Opt-in real-SSH/volume probe using NEW synthetic-only owned directories.

Private audited profile required. No discovery, production DB input, service
operation, credential registration, scheduler registration or real mail.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contextlib import closing
from datetime import datetime,timedelta,timezone
import argparse
import base64
import json
import os
import re
import secrets
import shlex
import sqlite3
from adapters.backup_runtime import (GuardedWorkspace,ConfiguredVPS,ConfiguredHome,volume_identity,dpapi,safe_path)
from adapters.backup_ssh import PinnedSSH,ProcessRPC,PullTransport
from research.home_backup_storage import canonical,digest,LabFailure,ProcessLock

FILES=('research/backup_restore_lab.py','research/backup_foundation_lab.py','research/backup_crypto_probe.cjs',
       'research/home_backup_storage.py','research/home_backup_jobs.py','research/backup_connection_probe.py',
       'adapters/backup_runtime.py','adapters/backup_ssh.py')


def grant(config,actions):
    return {'kind':'fortune-backup-execution-grant-v1','mode':'synthetic','config_sha256':digest(canonical(config)),
            'actions':actions,'expires_at':(datetime.now(timezone.utc)+timedelta(hours=8)).isoformat()}


def cleanup_workspace(lab):
    """No recursive delete. Validate the complete narrow inventory before unlink."""
    if lab.config['mode']!='synthetic':raise LabFailure('synthetic_cleanup_only')
    lab.validate_markers();lab.disk()
    files=[];directories=[]
    for parent in (lab.root,lab.data):
        for path in parent.iterdir():
            lab.check(path)
            if path.is_dir():
                if parent!=lab.root or path.name not in ('vps-state','pc-state'):raise LabFailure('cleanup_unknown_directory')
                directories.append(path)
                for child in path.iterdir():
                    lab.check(child)
                    if not child.is_file() or child.name not in ('synthetic-jobs.sqlite3','synthetic-jobs.sqlite3-journal',
                            'synthetic-jobs.sqlite3-wal','synthetic-jobs.sqlite3-shm','job.lock'):
                        raise LabFailure('cleanup_unknown_file')
                    files.append(child)
            else:
                allowed=path.name=='backup-owner.json'
                allowed|=(parent==lab.root and path.name in ('fixture.synthetic.sqlite3','fixture.synthetic.sqlite3-journal','fixture.synthetic.sqlite3-wal','fixture.synthetic.sqlite3-shm','test.key.dpapi'))
                allowed|=bool(parent==lab.data and re.fullmatch('[0-9a-f]{32}\\.(enc|part)',path.name))
                allowed|=bool(parent==lab.root and re.fullmatch('snapshot-[0-9a-f]{32}\\.sqlite3',path.name))
                if not path.is_file() or not allowed:raise LabFailure('cleanup_unknown_file')
                files.append(path)
    if any(path.stat().st_nlink!=1 for path in files):raise LabFailure('cleanup_link_refused')
    # All paths remain within the two exact freshly-created, marked roots.
    for path in files:lab.check(path).unlink()
    for path in directories:lab.check(path).rmdir()
    lab.data.rmdir();lab.root.rmdir()
    return len(files)


CONTROL=r'''from pathlib import Path
import sys,json,sqlite3
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parent))
from research.backup_connection_probe import cleanup_workspace
from adapters.backup_runtime import GuardedWorkspace,ConfiguredVPS
from research.home_backup_storage import canonical,LabFailure
top=Path(__file__).resolve().parent.parent
owner=json.loads((top/'connection-test-owner.json').read_bytes())
request=json.loads(sys.stdin.buffer.read(4097))
config=json.loads((top/'vps-config.json').read_bytes())
if owner['test_id']!=request.get('test_id') or config['mode']!='synthetic' or owner['test_id']!=config['namespace']:raise SystemExit(2)
lab=GuardedWorkspace(config,top/'vps-grant.json','generate')
if request['op']=='generate':
 now=datetime.fromisoformat(request['at'])
 with sqlite3.connect(config['source_path']) as db:db.execute('INSERT INTO synthetic_rows(value) VALUES (?)',('synthetic-generation-marker',))
 job=ConfiguredVPS(lab);job.sweep(now);row=job.generate(now)
 result={'row':row}
elif request['op']=='cleanup':
 cleanup_workspace(lab)
 known={*owner['code_files'],'code/connection_control.py','connection-test-owner.json','vps-config.json','vps-grant.json','test.key.bin'}
 actual=set()
 for path in top.rglob('*'):
  if path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()) or top not in path.resolve().parents:raise SystemExit(2)
  if path.is_file():actual.add(path.relative_to(top).as_posix())
 if actual!=known:raise SystemExit(2)
 for name in sorted(actual):
  p=top/name
  if p.stat().st_nlink!=1:raise SystemExit(2)
  p.unlink()
 for path in sorted((p for p in top.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):path.rmdir()
 top.rmdir();result={'cleaned':True}
else:raise SystemExit(2)
sys.stdout.buffer.write(canonical(result))
'''


BOOTSTRAP=r'''import sys,json,base64,os,pathlib,sqlite3,hashlib
request=json.loads(sys.stdin.buffer.read(2000000))
ns=request['test_id']
if len(ns)!=32 or any(c not in '0123456789abcdef' for c in ns):raise SystemExit(2)
top=pathlib.Path.home()/('fortune-backup-synthetic-'+ns)
cfg=request['config']
if cfg['mode']!='synthetic' or cfg['role']!='vps' or cfg['namespace']!=ns or cfg['root']!=str(top/'state') or cfg['data_root']!=str(top/'stage') or cfg['source_path']!=str(top/'state'/'fixture.synthetic.sqlite3') or cfg['key_path']!=str(top/'test.key.bin'):raise SystemExit(2)
if top.exists() or top.is_symlink():raise SystemExit(2)
top.mkdir(mode=0o700)
files=request['files']
expected={'research/backup_restore_lab.py','research/backup_foundation_lab.py','research/backup_crypto_probe.cjs','research/home_backup_storage.py','research/home_backup_jobs.py','research/backup_connection_probe.py','adapters/backup_runtime.py','adapters/backup_ssh.py'}
if set(files)!=expected:raise SystemExit(2)
def write(path,data):
 path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(descriptor,'wb') as out:out.write(data)
for name,value in files.items():write(top/'code'/name,base64.b64decode(value,validate=True))
write(top/'code'/'connection_control.py',request['control'].encode())
write(top/'connection-test-owner.json',json.dumps({'test_id':ns,'purpose':'synthetic-only','code_files':['code/'+p for p in sorted(files)]}).encode())
write(top/'vps-config.json',json.dumps(cfg).encode())
write(top/'vps-grant.json',json.dumps(request['grant']).encode())
write(top/'test.key.bin',base64.b64decode(request['synthetic_key'],validate=True))
sys.path.insert(0,str(top/'code'))
from adapters.backup_runtime import GuardedWorkspace
GuardedWorkspace.initialize(cfg,top/'vps-grant.json')
with sqlite3.connect(cfg['source_path']) as db:
 db.execute('CREATE TABLE synthetic_rows(id INTEGER PRIMARY KEY,value BLOB)')
 db.execute('INSERT INTO synthetic_rows(value) VALUES (?)',(os.urandom(1024*1024),))
os.chmod(cfg['source_path'],0o600)
print(json.dumps({'created':True,'synthetic_only':True}))
'''


def run(profile):
    if profile.get('kind')!='fortune-synthetic-connection-profile-v1' or profile.get('allow_real_synthetic') is not True:
        raise LabFailure('audited_synthetic_profile_required')
    home_config=profile['home'];vps_config=profile['vps'];ns=home_config['namespace']
    local=safe_path(profile['local_test_root']);data=safe_path(home_config['data_root'])
    if (home_config['mode']!='synthetic' or vps_config['mode']!='synthetic' or ns!=vps_config['namespace']
        or local.name!='fortune-backup-synthetic-'+ns or data.name!='fortune-backup-synthetic-'+ns
        or home_config['root']!=str(local/'state') or home_config['key_path']!=str(local/'state'/'test.key.dpapi')):
        raise LabFailure('synthetic_profile_scope_refused')
    if local.exists() or data.exists():raise LabFailure('existing_test_directory_refused')
    if volume_identity(data.parent)!=home_config['volume_identity']:raise LabFailure('hdd_identity_mismatch')
    local.mkdir(mode=0o700)
    (local/'connection-test-owner.json').write_bytes(canonical({'test_id':ns,'purpose':'synthetic-only'}))
    config_path=local/'home-config.json';approval=local/'home-grant.json'
    config_path.write_bytes(canonical(home_config));approval.write_bytes(canonical(grant(home_config,['initialize','receive'])))
    # Pinned host is checked before initializing the new HDD directory.
    class ProfileView:
        config=home_config
        class Permission:
            def check(self):return None
        grant=Permission()
    checked_ssh=PinnedSSH(ProfileView())
    remote=home_config['ssh']['remote_entry']
    top=Path(vps_config['root']).parent.as_posix()
    expected_suffix='/fortune-backup-synthetic-'+ns
    if not top.endswith(expected_suffix) or remote[1]!=top+'/code/adapters/backup_ssh.py':raise LabFailure('remote_test_scope_refused')
    control_command=[*checked_ssh.command[:-1],shlex.join([remote[0],'-B',top+'/code/connection_control.py'])]
    control_rpc=ProcessRPC(control_command)
    bootstrap=ProcessRPC([*checked_ssh.command[:-1],shlex.join([remote[0],'-B','-c',BOOTSTRAP])])
    key=secrets.token_bytes(32)
    files={name:base64.b64encode((Path(__file__).resolve().parents[1]/name).read_bytes()).decode() for name in FILES}
    request={'test_id':ns,'config':vps_config,'grant':grant(vps_config,['initialize','generate','transfer']),
             'files':files,'control':CONTROL,'synthetic_key':base64.b64encode(key).decode()}
    # Bootstrap needs more than a protocol request: still bounded, encrypted SSH stdin.
    import subprocess
    initialized=False;home=None;report={'synthetic_only':True}
    try:
        process=subprocess.run(bootstrap.command,input=canonical(request),capture_output=True,timeout=60)
        if process.returncode or json.loads(process.stdout)!={'created':True,'synthetic_only':True}:
            raise LabFailure('remote_synthetic_bootstrap_failed')
        initialized=True
        GuardedWorkspace.initialize(home_config,approval)
        Path(home_config['key_path']).write_bytes(dpapi(key,ns,protect=True))
        home=GuardedWorkspace(home_config,approval,'receive')
        pinned=PinnedSSH(home);transport=PullTransport(home,pinned)
        row=control_rpc.json({'test_id':ns,'op':'generate','at':'2026-10-27T07:00:00+09:00'})['row']
        class CutSSH(PinnedSSH):
            def blocks(inner,request,maximum):
                blocks=super(CutSSH,inner).blocks(request,maximum)
                try:
                    for block in blocks:
                        yield block
                        if request['op']=='get':raise LabFailure('synthetic_connection_cut')
                finally:blocks.close()
        interrupted=ConfiguredHome(home,PullTransport(home,CutSSH(home)))
        try:interrupted.run_slot(datetime.fromisoformat('2026-10-27T07:10:00+09:00'))
        except LabFailure:pass
        part=home.artifact('mock-hdd',row['id'],'.part')
        if not part.is_file() or not 0<part.stat().st_size<row['size']:raise LabFailure('partial_receive_not_exercised')
        report['partial_bytes_before_resume']=part.stat().st_size
        job=ConfiguredHome(home,transport)
        result=job.run_slot(datetime.fromisoformat('2026-10-27T07:11:00+09:00'))
        if result['status']!='completed' or result['received']!=1:raise LabFailure('resume_not_verified')
        report['ssh_resume_verified']=True
        body=job.verify_file(row)
        with closing(home.decode_backup(body,json.loads(row['metadata']))) as db:
            report['restored_synthetic_rows']=db.execute('SELECT count(*) FROM synthetic_rows').fetchone()[0]
        path=home.artifact('mock-hdd',row['id']);path.write_bytes(body[:-1]+bytes([body[-1]^1]))
        try:job.verify_file(row)
        except LabFailure:report['tamper_rejected']=True
        finally:path.write_bytes(body)
        wrapped=Path(home_config['key_path']).read_bytes()
        Path(home_config['key_path']).write_bytes(dpapi(secrets.token_bytes(32),ns,protect=True))
        try:home.decode_backup(body,json.loads(row['metadata']))
        except LabFailure:report['wrong_key_rejected']=True
        finally:Path(home_config['key_path']).write_bytes(wrapped)
        rows=[row]
        for value in ('12:00','17:00','23:00'):
            at=datetime.fromisoformat('2026-10-27T'+value+':00+09:00')
            row=control_rpc.json({'test_id':ns,'op':'generate','at':at.isoformat()})['row'];rows.append(row)
            if job.run_slot(at+timedelta(minutes=10))['status']!='completed':raise LabFailure('four_slot_receive_failed')
        report['four_generations_verified']=len({r['id'] for r in rows})==4
        report['four_distinct_sqlite_images']=len({json.loads(r['metadata'])['raw_sha256'] for r in rows})==4
        duplicate=control_rpc.json({'test_id':ns,'op':'generate','at':'2026-10-27T23:20:00+09:00'})['row']
        report['duplicate_reused']=duplicate['id']==rows[-1]['id']
        at=datetime.fromisoformat('2026-11-27T07:00:00+09:00')
        control_rpc.json({'test_id':ns,'op':'generate','at':at.isoformat()})
        job.run_slot(at+timedelta(minutes=10))
        report['timestamp_retention_verified']=len(list(home.data.glob('*.enc')))==1
        report['complete']=all(report.get(key) is True for key in ('ssh_resume_verified','tamper_rejected','wrong_key_rejected',
                            'four_generations_verified','four_distinct_sqlite_images','duplicate_reused','timestamp_retention_verified'))
        if not report['complete']:raise LabFailure('integration_check_incomplete')
        return report
    except Exception as error:
        report['complete']=False
        report['failure_code']=str(error) if isinstance(error,LabFailure) and re.fullmatch('[a-z_]+',str(error)) else 'integration_adapter_failed'
        return report
    finally:
        if initialized:
            try:report['remote_cleaned']=control_rpc.json({'test_id':ns,'op':'cleanup'})=={'cleaned':True}
            except Exception:report['remote_cleaned']=False
        if home is None and (Path(home_config['root'])/'backup-owner.json').exists():
            try:home=GuardedWorkspace(home_config,approval,'receive')
            except Exception:pass
        if home:
            try:cleanup_workspace(home);report['hdd_and_control_cleaned']=True
            except Exception:report['hdd_and_control_cleaned']=False
        if report.get('hdd_and_control_cleaned'):
            expected={'connection-test-owner.json','home-config.json','home-grant.json'}
            if {p.name for p in local.iterdir()}==expected:
                for name in expected:(local/name).unlink()
                local.rmdir()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--profile',required=True);args=parser.parse_args()
    try:
        result=run(json.loads(safe_path(args.profile).read_bytes()))
        print(json.dumps(result));raise SystemExit(0 if result.get('complete') and result.get('remote_cleaned') and result.get('hdd_and_control_cleaned') else 2)
    except Exception:
        print('{"complete":false,"code":"synthetic_connection_probe_failed"}');raise SystemExit(2)
