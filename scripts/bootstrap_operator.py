"""Explicit singleton grant. No account creation, invitation or password output."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from operations_repository import OperationsRepository
from history_repository import HistoryError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",type=Path,required=True)
    parser.add_argument("--user-id",required=True)
    parser.add_argument("--confirm",action="store_true",required=True)
    args=parser.parse_args()
    if not args.database.is_file(): parser.error("Specify an existing reviewed local database")
    try:
        OperationsRepository(args.database).bootstrap(args.user_id)
    except HistoryError as exc:
        print(str(exc),file=sys.stderr); return 1
    print("Singleton operator configured.")
    return 0

if __name__=="__main__": raise SystemExit(main())
