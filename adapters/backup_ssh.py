"""Pinned SSH pull and restricted catalog/prefix/get/ACK protocol.

No server/path/shell expression is accepted from a transfer request. The remote
entry and its private configuration are fixed in an execution-granted profile.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contextlib import contextmanager
from datetime import datetime,timezone
import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
from threading import Timer
from adapters.backup_runtime import ExecutionGrant,GuardedWorkspace,ConfiguredVPS,safe_path
from research.home_backup_storage import (JobState,ProcessLock,LabFailure,canonical,digest,
    MAX_WIRE,BackupSchedule)

MAX_CATALOG=4*1024*1024


class ProcessRPC:
    """Bounded process transport; also used for isolated local protocol tests."""
    def __init__(self,command,*,timeout=60):
        self.command=tuple(command);self.timeout=timeout

    def blocks(self,request,maximum):
        body=canonical(request)
        if len(body)>4096:raise LabFailure('request_size_refused')
        process=subprocess.Popen(self.command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        timer=Timer(self.timeout,lambda:process.kill() if process.poll() is None else None)
        timer.daemon=True;timer.start()
        try:
            process.stdin.write(body);process.stdin.close()
            total=0
            while block:=process.stdout.read(min(65536,maximum-total+1)):
                total+=len(block)
                if total>maximum:raise LabFailure('transport_output_limit')
                yield block
            if process.wait(timeout=5)!=0:raise LabFailure('ssh_operation_failed')
        except Exception:raise LabFailure('transport_failed') from None
        finally:
            timer.cancel()
            if not process.stdin.closed:process.stdin.close()
            if process.poll() is None:process.kill()
            process.wait(timeout=5);process.stdout.close()

    def json(self,request,maximum=MAX_CATALOG):
        try:return json.loads(b''.join(self.blocks(request,maximum)))
        except Exception:raise LabFailure('protocol_response_invalid') from None


class PinnedSSH(ProcessRPC):
    def __init__(self,workspace):
        workspace.grant.check()
        settings=workspace.config.get('ssh',{})
        host=settings.get('host','');user=settings.get('user','');port=settings.get('port',22)
        if (not re.fullmatch('[A-Za-z0-9][A-Za-z0-9.-]{0,252}',host) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_-]{0,63}',user)
                or type(port) is not int or not 1<=port<=65535):raise LabFailure('ssh_profile_invalid')
        known=safe_path(settings['known_hosts']);identity=safe_path(settings['identity_file'])
        if not identity.is_file():raise LabFailure('ssh_identity_missing')
        lines=[line.split() for line in known.read_text().splitlines() if line.strip() and not line.startswith('#')]
        address=host if port==22 else f'[{host}]:{port}'
        if len(lines)!=1 or len(lines[0])<3 or lines[0][0]!=address:raise LabFailure('pinned_host_record_required')
        algorithm,key=lines[0][1:3]
        try:fingerprint='SHA256:'+base64.b64encode(hashlib.sha256(base64.b64decode(key,validate=True)).digest()).decode().rstrip('=')
        except Exception:raise LabFailure('pinned_host_record_required') from None
        if fingerprint!=settings.get('host_key_fingerprint') or algorithm not in ('ssh-ed25519','ecdsa-sha2-nistp256'):
            raise LabFailure('host_key_pin_mismatch')
        remote=settings.get('remote_entry',[])
        if len(remote)!=4 or any(not isinstance(p,str) or not re.fullmatch('/[A-Za-z0-9._/-]+',p) or '..' in p.split('/') for p in remote):
            raise LabFailure('fixed_remote_entry_required')
        remote=[remote[0],'-B',remote[1],'--serve','--config',remote[2],'--approval',remote[3]]
        executable=str(safe_path(settings['ssh_executable']))
        null='NUL' if os.name=='nt' else '/dev/null'
        options=['-F',null,'-T','-a','-x','-p',str(port),'-i',str(identity)]
        for key,value in [('BatchMode','yes'),('IdentitiesOnly','yes'),('StrictHostKeyChecking','yes'),
                          ('UpdateHostKeys','no'),('UserKnownHostsFile',str(known)),('GlobalKnownHostsFile',null),
                          ('HostKeyAlgorithms',algorithm),('ConnectTimeout','12'),('ConnectionAttempts','1'),
                          ('ServerAliveInterval','10'),('ServerAliveCountMax','2'),('ClearAllForwardings','yes'),
                          ('PermitLocalCommand','no'),('PasswordAuthentication','no'),('KbdInteractiveAuthentication','no')]:
            options+=['-o',key+'='+value]
        super().__init__([executable,*options,user+'@'+host,shlex.join(remote)])


class PullTransport:
    def __init__(self,workspace,rpc):
        workspace.grant.check()
        self.namespace=workspace.generation;self.schedule=workspace.schedule;self.rpc=rpc;self.workspace=workspace

    def request(self,op,**values):
        self.workspace.grant.check()
        return {'version':1,'namespace':self.namespace,'op':op,**values}

    def catalog(self):
        value=self.rpc.json(self.request('catalog'))
        if not isinstance(value,list) or len(value)>4096:raise LabFailure('catalog_invalid')
        for row in value:
            if not isinstance(row,dict) or not re.fullmatch('[0-9a-f]{32}',row.get('id','')):
                raise LabFailure('catalog_invalid')
            if row.get('state') not in ('pending','ready','acked','delete_pending','deleted'):raise LabFailure('catalog_invalid')
            if row['state'] in ('ready','acked'):
                if type(row.get('size')) is not int or not 0<row['size']<=MAX_WIRE or not re.fullmatch('[0-9a-f]{64}',row.get('sha256','')):
                    raise LabFailure('catalog_invalid')
        return value

    def prefix_digest(self,row,length):
        value=self.rpc.json(self.request('prefix',id=row['id'],sha256=row['sha256'],length=length),4096)
        result=value.get('sha256','')
        if not re.fullmatch('[0-9a-f]{64}',result):raise LabFailure('prefix_response_invalid')
        return result

    def payload_chunks(self,row,offset):
        yield from self.rpc.blocks(self.request('get',id=row['id'],sha256=row['sha256'],offset=offset),row['size']-offset)

    def acknowledge(self,identifier,sha256,now):
        if self.rpc.json(self.request('ack',id=identifier,sha256=sha256),4096)!={'ok':True}:
            raise LabFailure('ack_response_invalid')


class TransferService:
    def __init__(self,workspace):
        if workspace.grant.action!='transfer' or workspace.config['role']!='vps':raise LabFailure('transfer_not_authorized')
        if not workspace.path('vps-state','synthetic-jobs.sqlite3').is_file():raise LabFailure('catalog_not_initialized')
        self.lab=workspace;self.state=JobState(workspace,'vps-state')

    def serve(self,request,output):
        self.lab.grant.check();self.lab.validate_markers()
        if request.get('version')!=1 or request.get('namespace')!=self.lab.generation:raise LabFailure('request_namespace_refused')
        operation=request.get('op')
        if operation not in ('catalog','prefix','get','ack'):raise LabFailure('request_operation_refused')
        with ProcessLock(self.lab,'vps-state'):
            if operation=='catalog':
                rows=self.state.rows('SELECT * FROM backups ORDER BY created_at,id')
                body=canonical(rows)
                if len(rows)>4096 or len(body)>MAX_CATALOG:raise LabFailure('catalog_budget_exceeded')
                output.write(body);return
            identifier=request.get('id','');sha=request.get('sha256','')
            if not re.fullmatch('[0-9a-f]{32}',identifier) or not re.fullmatch('[0-9a-f]{64}',sha):raise LabFailure('request_artifact_refused')
            rows=self.state.rows("SELECT * FROM backups WHERE id=? AND sha256=? AND state IN ('ready','acked')",(identifier,sha))
            if not rows:raise LabFailure('request_artifact_unknown')
            row=rows[0];path=self.lab.artifact('vps-stage',identifier)
            if operation=='ack':
                if not path.is_file() or path.stat().st_size!=row['size']:raise LabFailure('ack_artifact_missing')
                with self.state.db() as db:db.execute("UPDATE backups SET state='acked' WHERE id=?",(identifier,))
                self.state.event(datetime.now(timezone.utc),'offsite_receipt_recorded',identifier)
                output.write(canonical({'ok':True}));return
            offset=request.get('offset',0) if operation=='get' else request.get('length')
            if type(offset) is not int or not 0<=offset<=row['size']<=MAX_WIRE:raise LabFailure('resume_offset_refused')
            if path.stat().st_size!=row['size']:raise LabFailure('staged_file_corrupt')
            with path.open('rb') as stream:
                if operation=='prefix':output.write(canonical({'sha256':digest(stream.read(offset))}));return
                stream.seek(offset)
                while block:=stream.read(65536):output.write(block);output.flush()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--approval',required=True)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--serve',action='store_true');group.add_argument('--generate',action='store_true')
    args=parser.parse_args()
    config=json.loads(safe_path(args.config).read_bytes())
    workspace=GuardedWorkspace(config,args.approval,'transfer' if args.serve else 'generate')
    if args.serve:
        body=sys.stdin.buffer.read(4097)
        if len(body)>4096:raise LabFailure('request_size_refused')
        deadline=workspace.config.get('transfer_timeout_seconds',60)
        if type(deadline) is not int or not 1<=deadline<=120:raise LabFailure('transfer_deadline_refused')
        def expired(*args):raise LabFailure('transfer_request_timeout')
        if os.name!='nt':signal.signal(signal.SIGALRM,expired);signal.alarm(deadline)
        try:TransferService(workspace).serve(json.loads(body),sys.stdout.buffer)
        finally:
            if os.name!='nt':signal.alarm(0)
    else:
        now=datetime.now(timezone.utc)
        job=ConfiguredVPS(workspace);job.sweep(now);row=job.generate(now)
        print(json.dumps({'status':'ready' if row else 'not_due'}))


if __name__=='__main__':
    try:main()
    except Exception:
        sys.stderr.write('backup_request_failed\n');raise SystemExit(2)
