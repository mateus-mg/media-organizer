#!/usr/bin/env python3
"""Unit tests for link registry backup restore behavior."""

import tempfile
import unittest
from pathlib import Path

from app.infrastructure.link_registry import LinkRegistry


class TestLinkRegistryRestore(unittest.TestCase):
    def test_missing_link_registry_is_restored_from_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            backup_dir = data_dir / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_path = backup_dir / "link_registry_2026-03-23_10-00-00.json"
            backup_path.write_text('{"files": {"1": []}}', encoding="utf-8")

            target_path = data_dir / "link_registry.json"
            self.assertFalse(target_path.exists())

            registry = LinkRegistry(target_path)
            try:
                self.assertTrue(target_path.exists())
            finally:
                registry.close()


if __name__ == "__main__":
    unittest.main()
