"""Explicit-grant Windows pull entry. No default paths, host, account or keys."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
from datetime import datetime,timezone
import json
from adapters.backup_runtime import GuardedWorkspace,ConfiguredHome,safe_path
from adapters.backup_ssh import PinnedSSH,PullTransport


def run(config,approval,*,catch_up=True):
    workspace=GuardedWorkspace(config,approval,'receive')
    transport=PullTransport(workspace,PinnedSSH(workspace))
    return ConfiguredHome(workspace,transport).run_slot(datetime.now(timezone.utc),catch_up=catch_up)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--approval',required=True)
    parser.add_argument('--catch-up',action='store_true')
    args=parser.parse_args()
    try:
        result=run(json.loads(safe_path(args.config).read_bytes()),args.approval,catch_up=args.catch_up)
        print(json.dumps(result))
        raise SystemExit(0 if result['status'] in ('completed','already_completed','not_due') else 3)
    except Exception:
        print('{"status":"failed","code":"backup_client_failed"}');raise SystemExit(2)
