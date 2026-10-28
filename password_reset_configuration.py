"""Explicit Linux production mail configuration. Never guesses hosts or senders."""
from pathlib import Path
import json
import os
import stat
from auth_service import AuthSettings,AuthRepository,database_path,AuthError
from password_reset_service import PasswordResetService,trusted_origin
from mail_delivery import SMTPConfig,SMTPMailTransport


def private_file(value):
    path=Path(value)
    if os.name!='posix' or not path.is_absolute() or path.resolve()!=path:
        raise AuthError('メール設定の保護領域を確認してください。',503)
    for part in (path,*path.parents):
        if part.is_symlink():raise AuthError('メール設定の保護領域を確認してください。',503)
        if part!=path and part.stat().st_mode&0o022:
            raise AuthError('メール設定の親領域を確認してください。',503)
    metadata=path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=os.getuid() or metadata.st_mode&0o077 or metadata.st_nlink!=1:
        raise AuthError('メール設定の権限を確認してください。',503)
    return path


def configured_service(path,auth=None,*,expected_origin=None):
    try:
        config=json.loads(private_file(path).read_bytes())
        settings=AuthSettings.load()
        # A distinct invitation target is allowed only through explicit trusted
        # deployment configuration, never a request Host/Origin or user input.
        origin=trusted_origin(settings.public_origin if expected_origin is None else expected_origin)
        if config['public_origin']!=origin or config['security'] not in ('ssl','starttls'):
            raise ValueError()
        password=private_file(config['password_file']).read_text().rstrip('\r\n')
        mail=SMTPMailTransport(SMTPConfig(host=config['host'],port=config['port'],username=config['username'],
            password=password,sender=config['sender'],security=config['security']))
        return PasswordResetService(auth or AuthRepository(database_path()),mail,origin,settings)
    except Exception:raise AuthError('メール設定を確認してください。',503) from None
