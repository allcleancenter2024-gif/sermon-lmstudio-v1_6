import hashlib
import tempfile
import unittest
from pathlib import Path

from app.doctrine_storage import LocalObjectStore


class ObjectStoreRecoveryTests(unittest.TestCase):
    def test_immutable_store_verifies_digest_and_reuses_same_object(self):
        with tempfile.TemporaryDirectory() as root:
            store = LocalObjectStore(Path(root))
            payload = b"official doctrine source"
            digest = hashlib.sha256(payload).hexdigest()
            first = store.put_bytes("doctrine-archive/KMC/1/2026/" + digest + "/original.pdf", payload, digest)
            second = store.put_bytes(first.key, payload, digest)
            self.assertEqual(first, second)
            self.assertTrue(store.verify(first.key, digest))

    def test_checksum_mismatch_never_overwrites_existing_object(self):
        with tempfile.TemporaryDirectory() as root:
            store = LocalObjectStore(Path(root))
            with self.assertRaises(ValueError):
                store.put_bytes("doctrine-archive/KMC/1/2026/x/original.pdf", b"bad", "0" * 64)

    def test_orphans_are_reported_without_deletion(self):
        with tempfile.TemporaryDirectory() as root:
            store = LocalObjectStore(Path(root))
            payload = b"orphan"
            digest = hashlib.sha256(payload).hexdigest()
            key = "doctrine-archive/KMC/1/2026/" + digest + "/original.pdf"
            store.put_bytes(key, payload, digest)
            self.assertEqual(store.find_orphans([]), [key])
            self.assertTrue(store.exists(key))


if __name__ == '__main__':
    unittest.main()
