"""Explicitly granted file/SQLite adapters for the existing backup jobs.

No defaults select a real database, volume, key or host. This module never
generates production keys, registers jobs, restores files or resumes users.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contextlib import closing
from datetime import datetime, timedelta, timezone
import base64
import ctypes
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from uuid import uuid4
from research.home_backup_storage import (OwnedHomeLab, BackupSchedule, LabFailure,
    canonical,digest,MAX_RAW,MAX_WIRE,JobState,ProcessLock)
from research.backup_foundation_lab import SyntheticNodeAEAD
from research.backup_restore_lab import Snapshot,inspect
from research.home_backup_jobs import VPSBackupJob,HomeBackupJob


def safe_path(value):
    path=Path(value)
    if not path.is_absolute() or path.resolve()!=path: raise LabFailure('unsafe_config_path')
    for part in (path,*path.parents):
        if part.is_symlink() or (hasattr(part,'is_junction') and part.is_junction()):
            raise LabFailure('reparse_path_refused')
    return path


class ExecutionGrant:
    def __init__(self,config,approval,action):
        self.config=dict(config); self.approval=safe_path(approval) if approval else None
        self.action=action; self.check()

    def check(self):
        if self.config.get('enabled') is not True or self.config.get('mode') not in ('synthetic','production') or not self.approval:
            raise LabFailure('execution_not_authorized')
        try:
            value=json.loads(safe_path(self.approval).read_bytes())
            deadline=datetime.fromisoformat(value['expires_at'])
            valid=(value['kind']=='fortune-backup-execution-grant-v1' and value['mode']==self.config['mode']
                   and value['config_sha256']==digest(canonical(self.config)) and self.action in value['actions']
                   and deadline.utcoffset() is not None and datetime.now(timezone.utc)<deadline)
        except Exception: valid=False
        if not valid: raise LabFailure('execution_not_authorized')


def volume_identity(directory):
    """OS identity, never a drive letter or an on-disk marker alone."""
    path=safe_path(directory)
    if os.name!='nt':return 'device:'+str(path.stat().st_dev)
    mount=ctypes.create_unicode_buffer(32768)
    name=ctypes.create_unicode_buffer(32768)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetVolumePathNameW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_ulong]
    kernel.GetVolumeNameForVolumeMountPointW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_ulong]
    if not kernel.GetVolumePathNameW(str(path),mount,len(mount)) or not kernel.GetVolumeNameForVolumeMountPointW(mount.value,name,len(name)):
        raise LabFailure('volume_identity_unavailable')
    return name.value.lower()


def dpapi(data,namespace,*,protect=False):
    if os.name!='nt':raise LabFailure('dpapi_windows_required')
    class Blob(ctypes.Structure):
        _fields_=[('size',ctypes.c_ulong),('data',ctypes.POINTER(ctypes.c_ubyte))]
    def blob(value):
        buffer=ctypes.create_string_buffer(value)
        return Blob(len(value),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte))),buffer
    value,keep=blob(data); entropy,keep_entropy=blob(namespace.encode()); output=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    call=crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    call.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(Blob)]
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if not call(ctypes.byref(value),None,ctypes.byref(entropy),None,None,1,ctypes.byref(output)):
        raise LabFailure('key_protection_failed')
    try:return ctypes.string_at(output.data,output.size)
    finally:kernel.LocalFree(output.data)


def private_acl(path):
    """Read-only ACL check. Never changes an existing directory or credential."""
    path=safe_path(path)
    if os.name!='nt':
        value=path.stat()
        return value.st_uid==os.getuid() and value.st_mode&0o077==0
    script="""$ErrorActionPreference='Stop'
$p=__PATH__
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$allowed=@($sid,'S-1-5-18','S-1-5-32-544')
$acl=Get-Acl -LiteralPath $p
$owner=([Security.Principal.NTAccount]$acl.Owner).Translate([Security.Principal.SecurityIdentifier]).Value
$ok=$allowed -contains $owner
foreach($rule in $acl.Access){if($rule.AccessControlType -eq 'Allow' -and $allowed -notcontains $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value){$ok=$false}}
if($ok){'true'}else{'false'}
""".replace('__PATH__',"'"+str(path).replace("'","''")+"'")
    encoded=base64.b64encode(script.encode('utf-16-le')).decode()
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,timeout=15)
    return result.returncode==0 and result.stdout.decode(errors='replace').strip()=='true'


class GuardedWorkspace:
    inventory_marker_names={'backup-owner.json'}
    # These exact implementations are reused, including authenticated envelopes
    # and memory-only SQLite verification; the synthetic constructor is not used.
    artifact=OwnedHomeLab.artifact
    write=OwnedHomeLab.write
    envelope=OwnedHomeLab.envelope
    open_envelope=OwnedHomeLab.open_envelope
    decode_backup=OwnedHomeLab.decode_backup
    clean_plain_snapshots=OwnedHomeLab.clean_plain_snapshots

    @classmethod
    def initialize(cls,config,approval):
        ExecutionGrant(config,approval,'initialize')
        root=safe_path(config['root']); data=safe_path(config['data_root'])
        if (config.get('role') not in ('vps','home') or not re.fullmatch('[0-9a-f]{32}',config.get('namespace',''))
            or root==data or root in data.parents or data in root.parents):
            raise LabFailure('workspace_config_invalid')
        if root.exists() or data.exists():raise LabFailure('existing_workspace_refused')
        if config['role']=='home' and volume_identity(data.parent)!=config['volume_identity']:
            raise LabFailure('hdd_identity_mismatch')
        root.mkdir(mode=0o700)
        data.mkdir(mode=0o700)
        marker={'format':1,'namespace':config['namespace'],'role':config['role'],'mode':config['mode']}
        for target in (root/'backup-owner.json',data/'backup-owner.json'):
            descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as stream:stream.write(canonical(marker));stream.flush();os.fsync(stream.fileno())
        return marker

    def __init__(self,config,approval,action):
        self.grant=ExecutionGrant(config,approval,action); self.config=self.grant.config
        if config.get('role') not in ('vps','home') or not re.fullmatch('[0-9a-f]{32}',config.get('namespace','')):
            raise LabFailure('workspace_config_invalid')
        self.root=safe_path(config['root']); self.data=safe_path(config['data_root'])
        if self.root==self.data or self.root in self.data.parents or self.data in self.root.parents:
            raise LabFailure('workspace_roots_must_be_separate')
        self.generation=config['namespace']; self.node=str(safe_path(config['node_executable'])) if action!='transfer' else None
        self.link_available=True
        self.key_path=safe_path(config['key_path']) if action!='transfer' else None
        if self.key_path and (self.key_path==self.data or self.data in self.key_path.parents):raise LabFailure('key_backup_separation_required')
        self.expected={'format':1,'namespace':self.generation,'role':config['role'],'mode':config['mode']}
        self.validate_markers(include_data=config['role']!='home')
        acl_paths=[self.root]+([self.data] if config['role']=='vps' else [])+([self.key_path] if self.key_path and self.key_path.exists() else [])
        if config['mode']=='production' and not all(private_acl(path) for path in acl_paths):
            raise LabFailure('private_acl_required')
        self._data_acl_checked=False
        for name in (() if action=='transfer' else ('vps-state',) if config['role']=='vps' else ('pc-state',)):
            self.path(name).mkdir(mode=0o700,exist_ok=True)
        self.schedule=BackupSchedule.parse(config['generation_times_jst'],config['pull_delay_minutes'])
        if config['role']=='vps' and action=='generate':self.source_lab=ConfiguredSQLiteSource(self)

    def validate_markers(self,*,include_data=True):
        self.grant.check()
        for root in ((self.root,self.data) if include_data else (self.root,)):
            try:value=json.loads(safe_path(root/'backup-owner.json').read_bytes())
            except FileNotFoundError:
                raise LabFailure('hdd_unavailable' if root==self.data and self.config['role']=='home' else 'workspace_marker_missing') from None
            except Exception:raise LabFailure('workspace_marker_missing') from None
            if value!=self.expected:raise LabFailure('workspace_marker_mismatch')

    def check(self,path):
        self.grant.check(); path=safe_path(path)
        if not any(path==root or root in path.parents for root in (self.root,self.data)):
            raise LabFailure('outside_backup_workspace')
        return path

    def path(self,*parts):
        if parts and parts[0] in ('vps-stage','mock-hdd'):return self.check(self.data.joinpath(*parts[1:]))
        return self.check(self.root.joinpath(*parts))

    def disk(self,required=0):
        self.validate_markers(include_data=False)
        if self.config['role']=='home':
            try:identity=volume_identity(self.data.parent)
            except Exception:raise LabFailure('hdd_unavailable') from None
            if identity!=self.config['volume_identity']:raise LabFailure('hdd_identity_mismatch')
        self.validate_markers()
        if self.config['mode']=='production' and self.config['role']=='home' and not self._data_acl_checked:
            if not private_acl(self.data):raise LabFailure('private_acl_required')
            self._data_acl_checked=True
        if shutil.disk_usage(self.data).free<required+self.config.get('reserve_free_bytes',0):
            raise LabFailure('backup_capacity_insufficient')
        return self.data

    def usage(self):
        self.disk()
        retained=sum(self.check(p).stat().st_size for p in self.data.glob('*.enc'))
        return {'ciphertext_bytes':retained,'partial_bytes':sum(self.check(p).stat().st_size for p in self.data.glob('*.part')),
                'stage_bytes':retained if self.config['role']=='vps' else None,
                'mock_host_free_bytes':None,'volume_free_bytes':shutil.disk_usage(self.data).free,'injected_free_bytes':None}

    def cipher(self,role):
        self.grant.check()
        if self.grant.action=='transfer':raise LabFailure('key_operation_refused')
        expected='vps-key' if self.config['role']=='vps' else 'pc-key'
        if role!=expected:raise LabFailure('key_role_refused')
        try:
            path=safe_path(self.key_path)
            if path.stat().st_nlink!=1:raise ValueError()
            body=path.read_bytes()
            if self.config.get('key_protection')=='dpapi':body=dpapi(body,self.generation)
            elif os.name=='nt' and self.config['mode']=='production':raise ValueError()
            elif self.config['mode']=='production' and not private_acl(path):raise ValueError()
            if len(body)!=32:raise ValueError()
        except Exception:raise LabFailure('backup_key_unavailable') from None
        cipher=SyntheticNodeAEAD(self.node);cipher._key=body
        return cipher


class ConfiguredSQLiteSource:
    def __init__(self,workspace):self.workspace=workspace

    def snapshot(self,timeout_seconds=5):
        lab=self.workspace;lab.grant.check();lab.disk()
        if lab.grant.action!='generate':raise LabFailure('source_operation_refused')
        source=safe_path(lab.config['source_path'])
        if lab.config['mode']=='synthetic' and lab.root not in source.parents:
            raise LabFailure('synthetic_source_outside_test')
        if not source.is_file() or source.stat().st_nlink!=1 or not 0<source.stat().st_size<=MAX_RAW:
            raise LabFailure('source_size_or_identity_refused')
        # All checks above precede SQLite connect. There is no path discovery.
        if shutil.disk_usage(lab.root).free<source.stat().st_size+lab.config.get('reserve_free_bytes',0):
            raise LabFailure('snapshot_capacity_insufficient')
        target=lab.path('snapshot-'+uuid4().hex+'.sqlite3')
        descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(descriptor)
        deadline=time.monotonic()+min(max(timeout_seconds,1),60)
        def progress(*args):
            if time.monotonic()>=deadline:raise LabFailure('snapshot_timeout')
        try:
            with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=2)) as src,closing(sqlite3.connect(target)) as dst:
                src.backup(dst,pages=256,progress=progress,sleep=.02);dst.commit()
                if dst.execute('PRAGMA journal_mode=DELETE').fetchone()[0]!='delete':raise LabFailure('snapshot_not_standalone')
                schema,migrations,origin=inspect(dst)
            return Snapshot(target,lab.generation,digest(target.read_bytes()),schema,migrations,origin)
        except Exception:
            lab.check(target).unlink(missing_ok=True);raise


class ConfiguredVPS(VPSBackupJob):
    def __init__(self,workspace,**kwargs):
        if not isinstance(workspace,GuardedWorkspace) or workspace.config['role']!='vps' or workspace.grant.action!='generate':
            raise LabFailure('configured_vps_required')
        super().__init__(workspace,schedule=workspace.schedule,staging_days=workspace.config['staging_days'],
                         staging_limit_bytes=workspace.config['staging_limit_bytes'],**kwargs)


class ConfiguredHome(HomeBackupJob):
    def __init__(self,workspace,transport,**kwargs):
        if not isinstance(workspace,GuardedWorkspace) or workspace.config['role']!='home' or workspace.grant.action!='receive':
            raise LabFailure('configured_receiver_required')
        if transport.namespace!=workspace.generation:raise LabFailure('transport_namespace_mismatch')
        super().__init__(workspace,transport,schedule=workspace.schedule,**kwargs)
