"""Disposable home-backup demonstration. No DB/HDD/SSH path inputs."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
from datetime import datetime, time, timedelta, timezone
import json
from operations_repository import OperationsRepository
from research.home_backup_storage import OwnedHomeLab, LabFailure, BackupSchedule, JST
from research.home_backup_jobs import SyntheticVPS, SyntheticHomeJob


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node',required=True,help='Existing Node executable; no installation')
    parser.add_argument('--generation-times-jst',required=True)
    parser.add_argument('--pull-delay-minutes',required=True,type=int)
    args=parser.parse_args()
    schedule=BackupSchedule.parse(args.generation_times_jst,args.pull_delay_minutes)
    if len(schedule.times)!=4: raise LabFailure('four_slots_required')
    day=datetime(2026,10,27,tzinfo=JST).date()  # Synthetic calendar only.
    with OwnedHomeLab(args.node) as lab:
        OperationsRepository(lab.source_lab.source)
        server=SyntheticVPS(lab,schedule=schedule,staging_days=3,staging_limit_bytes=256*1024*1024)
        home=SyntheticHomeJob(lab,server,schedule=schedule)
        first=[]
        for value in schedule.times:
            moment=datetime.combine(day,value,JST)
            server.sweep(moment); server.generate(moment)
            first.append(home.run_slot(moment+schedule.pull_delay))
        # Eight more points while the PC is stopped for two days.
        for delta in (1,2):
            for value in schedule.times:
                moment=datetime.combine(day+timedelta(days=delta),value,JST)
                server.sweep(moment); server.generate(moment)
        resumed=SyntheticHomeJob(lab,server,schedule=schedule).run_slot(moment+schedule.pull_delay,catch_up=True)
        count=len(home.state.rows("SELECT id FROM backups WHERE state='verified'"))
        print(json.dumps({'synthetic_only':True,'first':first,'resumed':resumed,
                          'verified_files':count,'production_connections':False,'temporary_lab_cleaned_on_exit':True}))


if __name__=='__main__':
    try: main()
    except LabFailure:
        print('{"synthetic_only":true,"status":"failed"}')
        raise SystemExit(1)
