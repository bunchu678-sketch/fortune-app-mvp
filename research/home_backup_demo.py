"""Disposable home-backup demonstration. No DB/HDD/SSH path inputs."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
from datetime import datetime, time, timedelta, timezone
import json
from operations_repository import OperationsRepository
from research.home_backup_storage import OwnedHomeLab, LabFailure
from research.home_backup_jobs import SyntheticVPS, SyntheticHomeJob


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node',required=True,help='Existing Node executable; no installation')
    args=parser.parse_args()
    now=datetime(2026,10,26,18,tzinfo=timezone.utc)  # Fixture only.
    with OwnedHomeLab(args.node) as lab:
        OperationsRepository(lab.source_lab.source)
        server=SyntheticVPS(lab,schedule=time(3),staging_days=3,staging_limit_bytes=256*1024*1024)
        home=SyntheticHomeJob(lab,server,schedule=time(3))
        server.generate(now)
        first=home.run_daily(now+timedelta(minutes=1))
        # Simulate a two-day PC outage while the VPS continues independently.
        for day in (1,2):
            moment=now+timedelta(days=day)
            server.sweep(moment); server.generate(moment)
        resumed=SyntheticHomeJob(lab,server,schedule=time(3)).run_daily(now+timedelta(days=2,minutes=1))
        count=len(home.state.rows("SELECT id FROM backups WHERE state='verified'"))
        print(json.dumps({'synthetic_only':True,'first':first,'resumed':resumed,
                          'verified_files':count,'production_connections':False,'temporary_lab_cleaned_on_exit':True}))


if __name__=='__main__':
    try: main()
    except LabFailure:
        print('{"synthetic_only":true,"status":"failed"}')
        raise SystemExit(1)
