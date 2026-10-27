"""Portable, passphrase-encrypted recovery of one 256-bit backup key.

Uses Python's scrypt and the existing Node AES-GCM probe. No secret CLI
arguments, environment variables, plaintext key files, networking or task
registration. Production media/ACL checks belong to the deployment controller.
"""
from pathlib import Path
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import secrets
import subprocess

FORMAT = 'fortune-backup-recovery-v1'
KDF = {'name': 'scrypt', 'n': 131072, 'r': 8, 'p': 1, 'dklen': 32}


class RecoveryFailure(Exception):
    """Fixed codes only; never propagate subprocess or password details."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _decode(value, size):
    if not isinstance(value, str) or len(value) > 4096:
        raise RecoveryFailure('recovery_format_invalid')
    try:
        data = base64.b64decode(value, validate=True)
    except Exception:
        raise RecoveryFailure('recovery_format_invalid') from None
    if len(data) != size:
        raise RecoveryFailure('recovery_format_invalid')
    return data


def _derive(passphrase, salt):
    if not isinstance(passphrase, str) or not 16 <= len(passphrase) <= 1024:
        raise RecoveryFailure('recovery_passphrase_length')
    return hashlib.scrypt(passphrase.encode('utf-8'), salt=salt, n=KDF['n'],
                          r=KDF['r'], p=KDF['p'], dklen=32, maxmem=256 * 1024**2)


def _crypt(node, probe, operation, key, data, aad):
    request = {'syntheticOnly': True, 'operation': operation,
               'key': base64.b64encode(key).decode(),
               'data': base64.b64encode(data).decode(),
               'aad': base64.b64encode(aad).decode()}
    try:
        process = subprocess.run([str(node), str(probe)], input=canonical(request),
            capture_output=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if process.returncode:
            raise ValueError()
        return base64.b64decode(process.stdout, validate=True)
    except Exception:
        raise RecoveryFailure('recovery_authentication_failed') from None


def seal(key, passphrase, *, namespace, node, probe):
    if not isinstance(key, bytes) or len(key) != 32 or not re.fullmatch('[0-9a-f]{32}', namespace):
        raise RecoveryFailure('recovery_key_invalid')
    salt = secrets.token_bytes(32)
    header = {'format': FORMAT, 'namespace': namespace, 'kdf': dict(KDF),
              'salt': base64.b64encode(salt).decode(), 'cipher': 'AES-256-GCM',
              'created_at': datetime.now(timezone.utc).isoformat()}
    encrypted = _crypt(node, probe, 'seal', _derive(passphrase, salt), key, canonical(header))
    return canonical({'header': header, 'ciphertext': base64.b64encode(encrypted).decode()})


def open_key(body, passphrase, *, namespace, node, probe):
    try:
        if not isinstance(body, bytes) or len(body) > 8192:
            raise ValueError()
        def unique(pairs):
            result = {}
            for name, value in pairs:
                if name in result:
                    raise ValueError()
                result[name] = value
            return result
        envelope = json.loads(body, object_pairs_hook=unique)
        if set(envelope) != {'header', 'ciphertext'}:
            raise ValueError()
        header = envelope['header']
        if (set(header) != {'format', 'namespace', 'kdf', 'salt', 'cipher', 'created_at'}
            or header['format'] != FORMAT or header['namespace'] != namespace
            or not re.fullmatch('[0-9a-f]{32}', namespace)
            or header['kdf'] != KDF or header['cipher'] != 'AES-256-GCM'):
            raise ValueError()
        stamp = datetime.fromisoformat(header['created_at'])
        if stamp.utcoffset() is None:
            raise ValueError()
        salt = _decode(header['salt'], 32)
        ciphertext = _decode(envelope['ciphertext'], 60)
    except Exception:
        raise RecoveryFailure('recovery_format_invalid') from None
    key = _crypt(node, probe, 'open', _derive(passphrase, salt), ciphertext, canonical(header))
    if len(key) != 32:
        raise RecoveryFailure('recovery_key_invalid')
    return key


def prompt_passphrase(title, message):
    """Masked local input. Never log, persist or return it via the CLI."""
    import tkinter as tk
    from tkinter import simpledialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    try:
        value = simpledialog.askstring(title, message, show='*', parent=root)
    finally:
        root.destroy()
    if value is None:
        raise RecoveryFailure('recovery_input_cancelled')
    if not 16 <= len(value) <= 1024:
        raise RecoveryFailure('recovery_passphrase_length')
    return value


def main():
    parser = argparse.ArgumentParser(description='Verify an encrypted recovery key; never print the key.')
    parser.add_argument('--file', required=True)
    parser.add_argument('--namespace', required=True)
    parser.add_argument('--node', required=True)
    parser.add_argument('--probe', required=True)
    args = parser.parse_args()
    try:
        secret = prompt_passphrase('回復鍵の検証', '保存時のパスフレーズを入力してください。鍵本文は表示しません。')
        key = open_key(Path(args.file).read_bytes(), secret, namespace=args.namespace,
                       node=args.node, probe=args.probe)
        del secret, key
        print('{"authenticated":true,"key_disclosed":false}')
    except RecoveryFailure as error:
        print(json.dumps({'authenticated': False, 'code': str(error)}))
        raise SystemExit(2)
    except Exception:
        print('{"authenticated":false,"code":"recovery_verification_failed"}')
        raise SystemExit(2)


if __name__ == '__main__':
    main()
