"""Real adapter paths in exclusively allocated fixtures; no production input."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contextlib import closing
from datetime import datetime,timedelta,timezone
from io import BytesIO
import base64
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch,Mock
from uuid import uuid4
from adapters.backup_runtime import (GuardedWorkspace,ExecutionGrant,ConfiguredVPS,ConfiguredHome,dpapi,volume_identity,private_acl)
from adapters.backup_ssh import ProcessRPC,PullTransport,TransferService,PinnedSSH
from adapters.backup_notifications import BackupNotifications
from research.home_backup_storage import LabFailure,canonical,digest,ProcessLock,OwnedHomeLab
from research.home_backup_jobs import SyntheticVPS
from research.home_backup_task_draft import configured_draft
from mail_delivery import MemoryMailTransport,SMTPConfig,SMTPMailTransport

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,10,26,22,tzinfo=timezone.utc)  # 07:00 JST fixture.


class AdapterCases(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='fortune-adapter-owned-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();namespace=uuid4().hex
        self.configs={};self.approvals={};self.config_paths={}
        key=secrets.token_bytes(32)
        for role in ('vps','home'):
            config={'version':1,'enabled':True,'mode':'synthetic','namespace':namespace,'role':role,
                    'root':str(self.base/(role+'-state-root')),'data_root':str(self.base/(role+'-data-root')),
                    'key_path':str(self.base/(role+'-key.bin')),'key_protection':'raw',
                    'node_executable':shutil.which('node'),'generation_times_jst':'07:00,12:00,17:00,23:00',
                    'pull_delay_minutes':10,'staging_days':3,'staging_limit_bytes':512*1024**2,'reserve_free_bytes':0}
            if role=='vps':config['source_path']=str(Path(config['root'])/'fixture.synthetic.sqlite3')
            else:config['volume_identity']=volume_identity(self.base)
            self.configs[role]=config;self.config_paths[role]=self.base/(role+'-config.json')
            self.approvals[role]=self.base/(role+'-grant.json')
            self.save(role)
            GuardedWorkspace.initialize(config,self.approvals[role])
            Path(config['key_path']).write_bytes(key)
        self.vps=GuardedWorkspace(self.configs['vps'],self.approvals['vps'],'generate')
        self.home=GuardedWorkspace(self.configs['home'],self.approvals['home'],'receive')
        with closing(sqlite3.connect(self.configs['vps']['source_path'])) as db:
            db.execute('CREATE TABLE synthetic_rows (id INTEGER PRIMARY KEY, value BLOB)')
            db.execute('INSERT INTO synthetic_rows(value) VALUES (?)',(b'synthetic fixture',));db.commit()
        self.server=ConfiguredVPS(self.vps)
        self.command=[sys.executable,'-B',str(ROOT/'adapters'/'backup_ssh.py'),'--serve',
                      '--config',str(self.config_paths['vps']),'--approval',str(self.approvals['vps'])]
        self.rpc=ProcessRPC(self.command)
        self.transport=PullTransport(self.home,self.rpc)
        self.job=ConfiguredHome(self.home,self.transport)

    def save(self,role,*,actions=None,expires=None):
        config=self.configs[role];self.config_paths[role].write_bytes(canonical(config))
        self.approvals[role].write_bytes(canonical({'kind':'fortune-backup-execution-grant-v1','mode':config['mode'],
            'config_sha256':digest(canonical(config)),'actions':actions or ['initialize','generate','receive','transfer','notify'],
            'expires_at':(expires or datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}))

    def capture(self,now=NOW):
        row=self.server.generate(now);result=self.job.run_slot(now+timedelta(minutes=10))
        return row,result

    @unittest.skipUnless(os.name=='nt','Windows DACL check')
    def test_real_private_acl_accepts_owner_and_rejects_other_readers(self):
        target=self.base/'acl-owned';target.mkdir()
        command=['powershell.exe','-NoProfile','-NonInteractive','-Command',
                 '[Security.Principal.WindowsIdentity]::GetCurrent().User.Value']
        sid=subprocess.check_output(command,text=True).strip()
        subprocess.run(['icacls.exe',str(target),'/inheritance:r','/grant:r',
                        '*'+sid+':(OI)(CI)F','*S-1-5-18:(OI)(CI)F','*S-1-5-32-544:(OI)(CI)F'],
                       check=True,capture_output=True)
        self.assertTrue(private_acl(target))
        file=target/'key.fixture';file.write_bytes(b'synthetic ACL fixture')
        self.assertTrue(private_acl(file))
        subprocess.run(['icacls.exe',str(target),'/grant','*S-1-5-32-545:(OI)(CI)R'],check=True,capture_output=True)
        self.assertFalse(private_acl(target))
        self.assertFalse(private_acl(file))

    def transfer_workspace(self):
        return GuardedWorkspace(self.configs['vps'],self.approvals['vps'],'transfer')

    def test_four_slots_use_separate_process_protocol_and_authenticate(self):
        ids=[]
        for hours in (0,5,10,16):
            row,result=self.capture(NOW+timedelta(hours=hours));ids.append(row['id'])
            self.assertEqual(result['status'],'completed');self.assertEqual(result['received'],1)
            with closing(self.home.decode_backup(self.job.verify_file(row),json.loads(row['metadata']))) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM synthetic_rows').fetchone()[0],1)
        self.assertEqual(len(set(ids)),4)
        self.assertTrue(all(row['state']=='acked' for row in self.server.catalog()))

    def test_duplicate_and_cross_date_reuse_generation_id(self):
        first,_=self.capture()
        self.assertEqual(self.server.generate(NOW+timedelta(minutes=20))['id'],first['id'])
        self.assertEqual(self.job.run_slot(NOW+timedelta(minutes=20))['status'],'already_completed')
        second,_=self.capture(NOW+timedelta(days=1))
        self.assertNotEqual(first['id'],second['id'])

    def test_missing_disabled_expired_or_changed_grant_has_no_source_access(self):
        for change in ('missing','disabled','expired','changed'):
            config=dict(self.configs['vps']);approval=self.approvals['vps']
            if change=='missing':approval=None
            if change=='disabled':config['enabled']=False
            if change=='expired':self.save('vps',expires=datetime.now(timezone.utc)-timedelta(seconds=1))
            if change=='changed':config['source_path']=str(self.base/'not-approved.sqlite3')
            with patch('adapters.backup_runtime.sqlite3.connect',side_effect=AssertionError('DB must not open')):
                with self.assertRaises(LabFailure):GuardedWorkspace(config,approval,'generate')
            self.save('vps')

    def test_production_mode_cannot_reuse_synthetic_grant_or_marker(self):
        config=dict(self.configs['vps']);config['mode']='production'
        with self.assertRaises(LabFailure):GuardedWorkspace(config,self.approvals['vps'],'generate')
        self.configs['vps']=config;self.save('vps')
        with self.assertRaisesRegex(LabFailure,'marker_mismatch'):GuardedWorkspace(config,self.approvals['vps'],'generate')

    def test_synthetic_source_outside_owned_root_refused_before_sqlite(self):
        self.configs['vps']['source_path']=str(self.base/'outside.sqlite3');self.save('vps')
        workspace=GuardedWorkspace(self.configs['vps'],self.approvals['vps'],'generate')
        with patch('adapters.backup_runtime.sqlite3.connect',side_effect=AssertionError('DB must not open')):
            with self.assertRaisesRegex(LabFailure,'outside_test'):workspace.source_lab.snapshot()

    def test_root_escape_existing_directory_and_unknown_inventory_protected(self):
        with self.assertRaises(LabFailure):self.home.path('..','outside')
        with self.assertRaises(LabFailure):GuardedWorkspace.initialize(self.configs['home'],self.approvals['home'])
        self.home.path('mock-hdd','unmanaged.txt').write_text('keep')
        _,result=self.capture()
        self.assertIn('unknown_inventory',result['warnings'])
        self.assertTrue(self.home.path('mock-hdd','unmanaged.txt').exists())

    def test_wrong_volume_or_marker_refuses_write(self):
        self.configs['home']['volume_identity']='wrong-device';self.save('home')
        workspace=GuardedWorkspace(self.configs['home'],self.approvals['home'],'receive')
        with self.assertRaisesRegex(LabFailure,'identity_mismatch'):workspace.disk()
        (workspace.root/'backup-owner.json').write_text('{}')
        with self.assertRaisesRegex(LabFailure,'marker_mismatch'):workspace.disk()

    def test_transfer_role_has_no_key_or_source_handle(self):
        config={k:v for k,v in self.configs['vps'].items() if k not in ('key_path','source_path','node_executable')}
        self.configs['vps']=config;self.save('vps')
        workspace=GuardedWorkspace(config,self.approvals['vps'],'transfer')
        self.assertFalse(hasattr(workspace,'source_lab'));self.assertIsNone(workspace.key_path)
        with self.assertRaises(LabFailure):workspace.cipher('vps-key')

    def test_restricted_protocol_rejects_paths_offsets_and_mutation_methods(self):
        row=self.server.generate(NOW);service=TransferService(self.transfer_workspace())
        for values in ({'op':'delete'},{'op':'get','id':'../../source','sha256':row['sha256']},
                       {'op':'get','id':row['id'],'sha256':row['sha256'],'offset':-1},
                       {'op':'get','id':row['id'],'sha256':'0'*64,'offset':0}):
            with self.assertRaises(LabFailure):service.serve({'version':1,'namespace':self.vps.generation,**values},BytesIO())

    def test_wrong_key_and_ciphertext_tampering_never_become_success(self):
        row=self.server.generate(NOW)
        Path(self.home.config['key_path']).write_bytes(secrets.token_bytes(32))
        with self.assertRaises(LabFailure):self.job.run_slot(NOW+timedelta(minutes=10))
        self.assertFalse(self.job.state.rows("SELECT id FROM backups WHERE state='verified'"))
        self.vps.artifact('vps-stage',row['id']).write_bytes(b'corrupt')
        with self.assertRaises(LabFailure):self.job.run_slot(NOW+timedelta(minutes=11))

    def test_missing_key_stops_capture_and_cleans_plain_copy(self):
        Path(self.vps.config['key_path']).unlink()
        with self.assertRaises(LabFailure):self.server.generate(NOW)
        self.assertEqual(list(self.vps.root.glob('snapshot-*.sqlite3')),[])
        self.assertEqual(list(self.vps.data.glob('*.enc')),[])

    def test_staging_and_snapshot_space_failure_preserve_owned_source(self):
        with patch('adapters.backup_runtime.shutil.disk_usage',return_value=shutil._ntuple_diskusage(10,10,0)):
            with self.assertRaises(LabFailure):self.server.generate(NOW)
        self.assertTrue(Path(self.vps.config['source_path']).exists())
        self.server.limit=1
        with self.assertRaises(LabFailure):self.server.generate(NOW+timedelta(minutes=1))
        self.assertEqual(list(self.vps.root.glob('snapshot-*.sqlite3')),[])

    def test_interrupted_process_stream_resumes_from_verified_prefix(self):
        with closing(sqlite3.connect(self.vps.config['source_path'])) as db:
            db.execute('INSERT INTO synthetic_rows(value) VALUES (?)',(secrets.token_bytes(512*1024),));db.commit()
        row=self.server.generate(NOW)
        class InterruptRPC(ProcessRPC):
            drop=True;offsets=[]
            def blocks(inner,request,maximum):
                if request['op']=='get':inner.offsets.append(request['offset'])
                blocks=super(InterruptRPC,inner).blocks(request,maximum)
                try:
                    for block in blocks:
                        yield block
                        if inner.drop and request['op']=='get':raise LabFailure('synthetic_disconnect')
                finally:blocks.close()
        rpc=InterruptRPC(self.command);transport=PullTransport(self.home,rpc);job=ConfiguredHome(self.home,transport)
        with self.assertRaises(LabFailure):job.run_slot(NOW+timedelta(minutes=10))
        part=self.home.artifact('mock-hdd',row['id'],'.part')
        self.assertTrue(0<part.stat().st_size<row['size'])
        rpc.drop=False
        result=ConfiguredHome(self.home,transport).run_slot(NOW+timedelta(minutes=11))
        self.assertEqual(result['received'],1);self.assertGreater(rpc.offsets[-1],0)
        self.assertEqual(digest(self.job.verify_file(row)),row['sha256'])

    def test_corrupt_partial_prefix_is_restarted(self):
        row=self.server.generate(NOW);part=self.home.artifact('mock-hdd',row['id'],'.part');part.write_bytes(b'wrong partial')
        self.assertEqual(self.job.run_slot(NOW+timedelta(minutes=10))['status'],'completed')
        self.assertTrue(self.job.state.rows("SELECT * FROM events WHERE code='partial_restarted'"))

    def test_output_limit_and_timeout_refuse_unsafe_transport(self):
        rpc=ProcessRPC([sys.executable,'-B','-c','import sys;sys.stdin.read();sys.stdout.buffer.write(b"x"*10000)'])
        with self.assertRaises(LabFailure):list(rpc.blocks({'op':'probe'},8))
        stalled=ProcessRPC([sys.executable,'-B','-c','import sys,time;sys.stdin.read();time.sleep(5)'],timeout=.2)
        with self.assertRaises(LabFailure):list(stalled.blocks({'op':'probe'},8))

    def test_process_lock_prevents_concurrent_capture_and_transfer(self):
        with ProcessLock(self.vps,'vps-state'):
            with self.assertRaises(LabFailure):self.server.generate(NOW)
            with self.assertRaises(LabFailure):self.transport.catalog()

    def test_actual_receiver_exit_after_rename_resumes_receipt(self):
        row=self.server.generate(NOW)
        child='''import json,sys,os
from datetime import datetime
from adapters.backup_runtime import GuardedWorkspace,ConfiguredHome
from adapters.backup_ssh import PullTransport,ProcessRPC
cfg=json.loads(open(sys.argv[1]).read());lab=GuardedWorkspace(cfg,sys.argv[2],'receive')
def fault(stage,identifier):
 if stage=='received_renamed':os._exit(73)
ConfiguredHome(lab,PullTransport(lab,ProcessRPC(json.loads(sys.argv[3]))),point=fault).run_slot(datetime.fromisoformat(sys.argv[4]))
'''
        result=subprocess.run([sys.executable,'-B','-c',child,str(self.config_paths['home']),str(self.approvals['home']),
                               json.dumps(self.command),(NOW+timedelta(minutes=10)).isoformat()],cwd=ROOT,capture_output=True,timeout=45)
        self.assertEqual(result.returncode,73,result.stderr.decode(errors='replace'))
        self.assertEqual(self.job.run_slot(NOW+timedelta(minutes=11))['status'],'completed')
        self.assertEqual(len(list(self.home.data.glob('*.enc'))),1)

    def test_thirty_day_cleanup_is_based_on_created_time(self):
        first,_=self.capture()
        self.server.sweep(NOW+timedelta(days=31))
        second,result=self.capture(NOW+timedelta(days=31))
        self.assertFalse(self.home.artifact('mock-hdd',first['id']).exists())
        self.assertTrue(self.home.artifact('mock-hdd',second['id']).exists())

    def test_notification_uses_existing_memory_transport_without_claiming_delivery(self):
        self.job.state.event(NOW,'generation_stale',alert=True)
        mail=MemoryMailTransport();notifier=BackupNotifications(self.home,mail)
        result=notifier.dispatch(recipient='synthetic-alert@example.test')
        self.assertEqual(result,{'provider_accepted':1,'delivered_confirmed':False})
        self.assertEqual(notifier.dispatch(recipient='synthetic-alert@example.test')['provider_accepted'],0)
        self.assertEqual(len(mail.messages),1)

    def test_notification_no_grant_or_disabled_transport_does_not_claim_sent(self):
        self.job.state.event(NOW,'generation_stale',alert=True)
        notifier=BackupNotifications(self.home)
        with self.assertRaises(LabFailure):notifier.dispatch(recipient='synthetic-alert@example.test')
        self.assertEqual(notifier.state.rows('SELECT * FROM alert_delivery'),[])
        self.save('home',actions=['receive'])
        with self.assertRaises(LabFailure):BackupNotifications(self.home,MemoryMailTransport()).dispatch(recipient='synthetic-alert@example.test')

    @unittest.skipUnless(os.name=='nt','Windows DPAPI API')
    def test_dpapi_synthetic_key_roundtrip_and_wrong_entropy(self):
        key=secrets.token_bytes(32);wrapped=dpapi(key,self.home.generation,protect=True)
        self.assertNotEqual(key,wrapped);self.assertEqual(dpapi(wrapped,self.home.generation),key)
        with self.assertRaises(LabFailure):dpapi(wrapped,'wrong-namespace')

    def test_configured_xml_is_disabled_and_targets_guarded_client(self):
        import xml.etree.ElementTree as ET
        xml=configured_draft(sys.executable,self.home.node,'2026-10-28T00:00:00+09:00',schedule=self.home.schedule,
              config=self.config_paths['home'],approval=self.approvals['home'],user_id='DRAFT-USER')
        root=ET.fromstring(xml);ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        self.assertEqual(root.find('t:Settings/t:Enabled',ns).text,'false')
        self.assertIn('backup_client.py',root.find('t:Actions/t:Exec/t:Arguments',ns).text)
        self.assertEqual(len(root.findall('.//t:CalendarTrigger',ns)),4)
        self.assertEqual(root.find('.//t:LogonType',ns).text,'InteractiveToken')

    def test_synthetic_wrapper_cannot_accept_configured_workspace(self):
        with self.assertRaises(LabFailure):SyntheticVPS(self.vps,schedule=self.vps.schedule,staging_days=3,staging_limit_bytes=1)

    def pin_profile(self,*,wrong=False,traversal=False):
        identity=self.base/'ssh-identity-fixture';identity.write_bytes(b'not-a-real-private-key')
        public=b'synthetic-public-record';encoded=base64.b64encode(public).decode()
        known=self.base/'pinned-hosts-fixture';known.write_text('synthetic.example.test ssh-ed25519 '+encoded+'\n')
        fingerprint='SHA256:'+base64.b64encode(__import__('hashlib').sha256(public).digest()).decode().rstrip('=')
        self.configs['home']['ssh']={'host':'synthetic.example.test','user':'synthetic','port':22,'identity_file':str(identity),
             'known_hosts':str(known),'host_key_fingerprint':'wrong' if wrong else fingerprint,
             'ssh_executable':sys.executable,'remote_entry':['/usr/bin/python3','/home/synthetic/entry.py',
                  '/home/synthetic/../config.json' if traversal else '/home/synthetic/config.json','/home/synthetic/grant.json']}
        self.save('home')
        return GuardedWorkspace(self.configs['home'],self.approvals['home'],'receive')

    def test_host_pin_mismatch_or_remote_path_traversal_never_starts_ssh(self):
        for options in ({'wrong':True},{'traversal':True}):
            workspace=self.pin_profile(**options)
            with patch('adapters.backup_ssh.subprocess.Popen',side_effect=AssertionError('no network')):
                with self.assertRaises(LabFailure):PinnedSSH(workspace)
        workspace=self.pin_profile()
        known=Path(workspace.config['ssh']['known_hosts'])
        known.write_text(known.read_text().replace('ssh-ed25519','ssh-rsa'))
        with self.assertRaises(LabFailure):PinnedSSH(workspace)

    def test_pinned_client_disables_host_acceptance_forwarding_and_passwords(self):
        command=PinnedSSH(self.pin_profile()).command
        for option in ('StrictHostKeyChecking=yes','UpdateHostKeys=no','ClearAllForwardings=yes',
                       'PermitLocalCommand=no','PasswordAuthentication=no','KbdInteractiveAuthentication=no'):
            self.assertIn(option,command)
        self.assertIn('-a',command);self.assertIn('-F',command)

    def test_owned_cleanup_refuses_unknown_file_then_removes_exact_scope(self):
        from research.backup_connection_probe import cleanup_workspace
        unknown=self.home.data/'unmanaged.txt';unknown.write_bytes(b'do not delete')
        with self.assertRaisesRegex(LabFailure,'unknown_file'):cleanup_workspace(self.home)
        self.assertTrue(unknown.exists());self.assertTrue((self.home.data/'backup-owner.json').exists())
        unknown.unlink()
        self.assertGreater(cleanup_workspace(self.home),0)
        self.assertFalse(self.home.data.exists());self.assertFalse(self.home.root.exists())

    def test_source_hardlink_refused(self):
        os.link(self.vps.config['source_path'],self.base/'alias.sqlite3')
        with self.assertRaisesRegex(LabFailure,'identity_refused'):self.vps.source_lab.snapshot()

    def test_disconnected_data_directory_is_recorded_in_independent_control_outbox(self):
        self.server.generate(NOW)
        disconnected=self.base/'disconnected-owned-data'
        self.home.data.rename(disconnected)
        try:
            restarted=GuardedWorkspace(self.configs['home'],self.approvals['home'],'receive')
            job=ConfiguredHome(restarted,PullTransport(restarted,self.rpc))
            with self.assertRaises(LabFailure):job.run_slot(NOW+timedelta(minutes=10))
            self.assertTrue(job.state.rows("SELECT * FROM outbox WHERE code='hdd_unavailable'"))
        finally:disconnected.rename(self.home.data)

    def test_notification_reuses_smtp_adapter_with_mocked_network(self):
        self.job.state.event(NOW,'backup_capacity_insufficient',alert=True)
        connection=Mock();connection.send_message.return_value={}
        factory=Mock();factory.return_value.__enter__=Mock(return_value=connection);factory.return_value.__exit__=Mock(return_value=False)
        config=SMTPConfig('smtp.example.test',587,'synthetic-user','synthetic-password',sender='synthetic-sender@example.test')
        notifier=BackupNotifications(self.home,SMTPMailTransport(config,factory))
        self.assertEqual(notifier.dispatch(recipient='synthetic-alert@example.test')['provider_accepted'],1)
        message=connection.send_message.call_args.args[0]
        self.assertIn('backup_capacity_insufficient',message.get_content())
        self.assertEqual(message['To'],'synthetic-alert@example.test')

    def test_vps_notifications_use_vps_outbox(self):
        self.server.state.event(NOW,'delivery_overdue',alert=True)
        mail=MemoryMailTransport();notifier=BackupNotifications(self.vps,mail)
        self.assertEqual(notifier.dispatch(recipient='synthetic-alert@example.test')['provider_accepted'],1)
        self.assertIn('delivery_overdue',mail.messages[0].body)
        self.assertFalse(self.job.state.rows('SELECT * FROM outbox'))


if __name__=='__main__':unittest.main(verbosity=2)
