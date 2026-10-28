"""Explicit prepare/send/grant for the first Operator; JSON stdin, no passwords."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse,json
from operations_repository import OperationsRepository
from auth_service import normalized_email,AuthError
from password_reset_configuration import configured_service


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--action',choices=['prepare','send','grant'],required=True)
    parser.add_argument('--mail-config',type=Path)
    parser.add_argument('--confirm',action='store_true',required=True)
    args=parser.parse_args()
    if not args.database.is_file():parser.error('Explicit existing reviewed database required')
    data=json.loads(sys.stdin.read(4097))
    operations=OperationsRepository(args.database)
    with operations.auth.connection() as db:
        old=db.execute('SELECT user_id FROM operating_administrator WHERE singleton=1').fetchone()
        user=db.execute('SELECT id FROM users WHERE normalized_email=?',(normalized_email(data['email']),)).fetchone()
    if old:
        if user and old[0]==user['id']:return {'status':'already_configured'}
        raise AuthError('運営管理者は既に存在します。重複設定しません。',409)
    if args.action=='prepare':
        if user:raise AuthError('既存Userの選定は明示したgrant操作で行ってください。',409)
        created=operations.auth.create_setup_user(data['email'])
        return {'status':'setup_pending','user_id':created['id']}
    if not user or data.get('user_id')!=user['id']:raise AuthError('本人確認済みUserを明示してください。',422)
    if args.action=='send':
        if args.mail_config is None:parser.error('Explicit reviewed mail configuration required')
        with operations.auth.connection() as db:
            if not db.execute('SELECT 1 FROM user_initial_setup WHERE user_id=? AND completed_at IS NULL',(user['id'],)).fetchone():
                raise AuthError('初回設定待ちUserを指定してください。',409)
        service=configured_service(args.mail_config,operations.auth)
        normalized=service.admit_request(data['email'],'explicit-operator-bootstrap')
        if not service.deliver(normalized,initial=True):raise AuthError('初回設定メールを受け付けられませんでした。',503)
        return {'status':'provider_accepted','mailbox_delivery_confirmed':False}
    operations.bootstrap(user['id'])
    return {'status':'operator_configured'}


if __name__=='__main__':
    try:print(json.dumps(main()))
    except Exception:
        print('{"status":"failed","code":"operator_initial_setup_failed"}')
        raise SystemExit(2)
