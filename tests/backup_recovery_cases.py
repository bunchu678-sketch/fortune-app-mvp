"""Disposable keys only. Portable recovery authentication and strict parsing."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import os
import shutil
import unittest
from adapters.backup_recovery import seal, open_key, RecoveryFailure


class RecoveryCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which('node')
        if not cls.node:
            raise unittest.SkipTest('Explicit Node runtime on process PATH required')
        cls.probe = Path(__file__).resolve().parents[1] / 'research' / 'backup_crypto_probe.cjs'
        cls.namespace = 'a' * 32
        cls.key = os.urandom(32)
        cls.password = 'Synthetic test only; Japanese 日本語 2026'
        cls.body = seal(cls.key, cls.password, namespace=cls.namespace, node=cls.node, probe=cls.probe)

    def opened(self, body, password=None, namespace=None):
        return open_key(body, password or self.password, namespace=namespace or self.namespace,
                        node=self.node, probe=self.probe)

    def test_roundtrip_and_randomized_encryption(self):
        self.assertEqual(self.opened(self.body), self.key)
        other = seal(self.key, self.password, namespace=self.namespace, node=self.node, probe=self.probe)
        self.assertNotEqual(other, self.body)
        self.assertEqual(self.opened(other), self.key)
        self.assertNotIn(self.key, self.body)
        self.assertNotIn(self.password.encode(), self.body)

    def test_wrong_password_and_tampered_ciphertext_refused(self):
        with self.assertRaises(RecoveryFailure):
            self.opened(self.body, 'Wrong password with sufficient length')
        value = json.loads(self.body)
        value['ciphertext'] = ('A' if value['ciphertext'][0] != 'A' else 'B') + value['ciphertext'][1:]
        with self.assertRaises(RecoveryFailure):
            self.opened(json.dumps(value).encode())

    def test_authenticated_header_and_namespace_refused(self):
        value = json.loads(self.body)
        value['header']['created_at'] = '2025-01-01T00:00:00+00:00'
        with self.assertRaises(RecoveryFailure):
            self.opened(json.dumps(value).encode())
        with self.assertRaises(RecoveryFailure):
            self.opened(self.body, namespace='b' * 32)

    def test_format_resource_limit_and_duplicates_refused(self):
        invalid = [b'x' * 8193, self.body[:-1], b'{"header":{},"header":{},"ciphertext":""}']
        value = json.loads(self.body)
        value['header']['kdf']['n'] = 2**30
        invalid.append(json.dumps(value).encode())
        for body in invalid:
            with self.assertRaises(RecoveryFailure):
                self.opened(body)

    def test_short_password_refused(self):
        with self.assertRaises(RecoveryFailure):
            seal(self.key, 'short', namespace=self.namespace, node=self.node, probe=self.probe)


if __name__ == '__main__':
    unittest.main()
