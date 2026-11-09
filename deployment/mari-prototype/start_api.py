"""Dedicated classroom entry point: validate surface and existing DB, never headcount."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import argparse
import os
import sqlite3
from contextlib import closing
from mari_runtime import runtime_configuration


def validate_configuration():
    if runtime_configuration() != 'teacher':
        raise ValueError('teacher_surface_required')
    try:
        path = Path(os.environ.get('FORTUNE_HISTORY_DB_PATH', ''))
        if not path.is_absolute() or not path.is_file():
            raise ValueError()
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=3)) as db:
            db.execute('PRAGMA query_only=ON')
            row = db.execute('SELECT id FROM organizations WHERE slug=?',
                (os.environ.get('FORTUNE_READING_ORGANIZATION_SLUG', 'mari-mutsuro'),)).fetchone()
            if row is None:raise ValueError()
            db.execute('SELECT organization_id,user_id,role FROM memberships LIMIT 0')
    except Exception:
        raise ValueError('classroom_database_configuration_invalid') from None


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
