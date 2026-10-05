"""Local administrator CLI. Passwords only enter through a hidden terminal prompt."""
import argparse
from getpass import getpass, GetPassWarning
from pathlib import Path
import sqlite3
import sys
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from auth_service import AuthError, AuthRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "disable", "enable", "set-password"))
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    try:
        password = None
        if args.action in ("create", "set-password"):
            if not sys.stdin.isatty():
                raise AuthError("パスワードは対話端末から入力してください。", 422)
            with warnings.catch_warnings():
                warnings.simplefilter("error", GetPassWarning)
                password = getpass("Password (12-1024 characters): ")
                if password != getpass("Confirm password: "):
                    raise AuthError("パスワードが一致しません。", 422)
        repository = AuthRepository()
        user = repository.create_user(args.email, password) if args.action == "create" else repository.change_user(args.email, args.action, password)
        print(f"{args.action}: completed (user id: {user['id']})")
        return 0
    except AuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except GetPassWarning:
        print("入力を隠せる対話端末から実行してください。", file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error):
        print("認証の保存先を利用できません。DB設定と権限を確認してください。", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("管理操作を中止しました。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
