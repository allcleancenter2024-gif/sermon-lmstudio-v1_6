import unittest
from unittest.mock import Mock

from app.doctrine_storage_audit import audit_minio_references


class _Object:
    def __init__(self, name): self.object_name = name


class StorageAuditTests(unittest.TestCase):
    def test_audit_reports_orphans_and_missing_objects_without_mutation(self):
        client = Mock()
        client.list_objects.return_value = [
            _Object("production/doctrine-archive/KMC/1/original.html"),
            _Object("production/unreferenced/original.pdf"),
        ]
        store = Mock()
        store.list_keys.side_effect = lambda prefix: sorted(obj.object_name for obj in client.list_objects(None, prefix=prefix, recursive=True))
        result = audit_minio_references(store, ["doctrine-archive/KMC/1/original.html"])

        self.assertEqual(result["orphan_objects"], ["production/unreferenced/original.pdf"])
        self.assertEqual(result["missing_objects"], ["production/doctrine-archive/KMC/1/metadata.json"])
        store.delete_object.assert_not_called()


if __name__ == "__main__": unittest.main()
