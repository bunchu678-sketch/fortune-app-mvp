"""Local control-record inspection. No SSH, decryption, mail or app DB access."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contextlib import closing
import argparse
import json
import re
import sqlite3
from adapters.backup_runtime import GuardedWorkspace,safe_path
from research.home_backup_storage import LabFailure


def status(config,approval):
    workspace=GuardedWorkspace(config,approval,'receive')
    if config['role']!='home':raise LabFailure('home_status_required')
    path=workspace.path('pc-state','synthetic-jobs.sqlite3')
    if not path.is_file():raise LabFailure('control_state_missing')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        count,created=db.execute("SELECT count(*),max(created_at) FROM backups WHERE state='verified'").fetchone()
        run=db.execute('SELECT slot,state,attempts FROM runs ORDER BY slot DESC LIMIT 1').fetchone()
        alerts=[dict(row) for row in db.execute('SELECT code,last_seen,occurrences FROM outbox ORDER BY code')
                if re.fullmatch('[a-z_]{1,64}',row['code'])]
    disk='available'
    try:workspace.disk()
    except LabFailure as error:
        disk=str(error) if re.fullmatch('[a-z_]{1,64}',str(error)) else 'hdd_check_failed'
    return {'status':'attention' if alerts or disk!='available' else 'recorded',
            'recorded_verified_backups':count,'latest_backup_created_at':created,
            'latest_run':dict(run) if run else None,'hdd':disk,'alerts':alerts,
            'integrity_rechecked':False,'periodic_registration_checked':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--approval',required=True)
    args=parser.parse_args()
    try:
        result=status(json.loads(safe_path(args.config).read_bytes()),args.approval)
        print(json.dumps(result));raise SystemExit(0 if result['status']=='recorded' else 3)
    except Exception:
        print('{"status":"failed","code":"backup_status_unavailable"}');raise SystemExit(2)
