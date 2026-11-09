"""Dedicated prototype entry point: refuse missing pair config before startup."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import argparse
import json
import os
import sqlite3
from contextlib import closing
from mari_prototype_access import PROFILE, require_prototype_reader


def validate_configuration():
    if (os.environ.get('FORTUNE_DEPLOYMENT_SURFACE') != 'teacher'
            or os.environ.get('FORTUNE_READING_ACCESS_PROFILE') != PROFILE):
        raise ValueError('prototype_profile_required')
    try:
        ids = json.loads(os.environ.get('FORTUNE_READING_ALLOWED_USER_IDS', ''))
        require_prototype_reader(ids[0])
        path = Path(os.environ.get('FORTUNE_HISTORY_DB_PATH', ''))
        if not path.is_absolute() or not path.is_file():
            raise ValueError()
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=3)) as db:
            db.execute('PRAGMA query_only=ON')
            roles = []
            for owner in ids:
                row = db.execute("""SELECT m.role FROM memberships m JOIN users u ON u.id=m.user_id
                    JOIN organizations o ON o.id=m.organization_id
                    LEFT JOIN user_account_lifecycle l ON l.user_id=u.id
                    WHERE m.user_id=? AND o.slug=? AND u.status='active'
                    AND COALESCE(l.state,'active')='active'
                    AND NOT EXISTS(SELECT 1 FROM user_initial_setup s WHERE s.user_id=u.id AND s.completed_at IS NULL)""",
                    (owner, os.environ.get('FORTUNE_READING_ORGANIZATION_SLUG', 'mari-mutsuro'))).fetchone()
                if row is None: raise ValueError()
                roles.append(row[0])
            if sorted(roles) != ['student', 'teacher']: raise ValueError()
    except Exception:
        raise ValueError('prototype_pair_configuration_invalid') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8773)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535: raise SystemExit('invalid_loopback_port')
    try: validate_configuration()
    except ValueError as error: raise SystemExit(str(error)) from None
    command = [sys.executable, '-B', '-m', 'uvicorn', 'server:app', '--app-dir',
        str(ROOT/'fortune-next-app/backend'), '--host', '127.0.0.1', '--port', str(args.port), '--no-access-log']
    if os.environ.get('FORTUNE_PROXY_HEADERS') == '1':
        command += ['--proxy-headers', '--forwarded-allow-ips', '127.0.0.1,::1']
    else:
        command += ['--no-proxy-headers']
    if os.name == 'nt':
        # Keep the owned parent alive so local test cleanup owns the child tree.
        import subprocess
        raise SystemExit(subprocess.call(command))
    os.execv(sys.executable, command)


if __name__ == '__main__': main()
