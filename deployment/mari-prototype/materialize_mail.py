"""Optional SMTP credential snapshots for the existing strict private_file guard.

Runs as the API UID. Only /run RuntimeDirectory receives plaintext; systemd
removes it on stop. Never logs values, opens original secret paths or sends mail.
"""
import json
import os
import stat
from pathlib import Path

RUNTIME=Path('/run/fortune-mari-reading-mail')


def materialize():
    if os.name!='posix' or os.geteuid()==0:raise ValueError()
    source=Path(os.environ['CREDENTIALS_DIRECTORY'])
    if (source.resolve()!=source or source.parent!=Path('/run/credentials')
            or RUNTIME.resolve()!=RUNTIME or RUNTIME.is_symlink()):raise ValueError()
    directory=RUNTIME.stat()
    if directory.st_uid!=os.getuid() or stat.S_IMODE(directory.st_mode)!=0o700:raise ValueError()
    values={}
    for name,limit in [('smtp-config',65536),('smtp-password',16384)]:
        path=source/name;metadata=path.lstat()
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid not in (0,os.getuid())
                or metadata.st_nlink!=1 or metadata.st_mode&0o227 or metadata.st_size>limit):raise ValueError()
        values[name]=path.read_bytes()
    config=json.loads(values['smtp-config'])
    config['password_file']=str(RUNTIME/'smtp-password')
    values['smtp-config']=json.dumps(config,ensure_ascii=False).encode()
    for name,body in values.items():
        target=RUNTIME/name
        if target.exists() or target.is_symlink():
            previous=target.lstat()
            if (not stat.S_ISREG(previous.st_mode) or previous.st_uid!=os.getuid()
                    or previous.st_nlink!=1 or stat.S_IMODE(previous.st_mode)!=0o600):raise ValueError()
        # An owned RuntimeDirectory is private to this service UID. A fresh
        # exclusive temporary inode avoids following a link during replacement.
        import tempfile
        fd,temporary=tempfile.mkstemp(prefix='.smtp-',dir=RUNTIME)
        try:
            with os.fdopen(fd,'wb') as f:
                os.fchmod(f.fileno(),0o600);f.write(body)
            os.replace(temporary,target)
        finally:
            if os.path.exists(temporary):os.unlink(temporary)


if __name__=='__main__':
    try:materialize()
    except Exception:raise SystemExit('SMTP runtime configuration could not be prepared.') from None
