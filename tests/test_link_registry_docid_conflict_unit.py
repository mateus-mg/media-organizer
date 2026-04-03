#!/usr/bin/env python3
"""Regression tests for TinyDB doc_id conflicts in LinkRegistry."""

import tempfile
import unittest
from pathlib import Path

from app.infrastructure.link_registry import LinkRegistry


class TestLinkRegistryDocIdConflict(unittest.TestCase):
    def test_register_link_with_two_instances_retries_on_docid_conflict(self):
        """Two open registries writing alternately should not fail with doc_id conflicts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "data" / "link_registry.json"
            src_dir = root / "src"
            dst_dir = root / "dst"
            src_dir.mkdir(parents=True, exist_ok=True)
            dst_dir.mkdir(parents=True, exist_ok=True)

            # Open two independent instances against the same TinyDB file,
            # matching music/lyrics organizer behavior.
            r1 = LinkRegistry(db_path)
            r2 = LinkRegistry(db_path)

            try:
                source_1 = src_dir / "track1.flac"
                source_1.write_bytes(b"a")
                dest_1 = dst_dir / "track1.flac"
                dest_1.hardlink_to(source_1)

                source_2 = src_dir / "track2.flac"
                source_2.write_bytes(b"b")
                dest_2 = dst_dir / "track2.flac"
                dest_2.hardlink_to(source_2)

                ok1 = r1.register_link(
                    source_1, dest_1, {"media_type": "music"})
                ok2 = r2.register_link(
                    source_2, dest_2, {"media_type": "lyrics"})

                self.assertTrue(ok1)
                self.assertTrue(ok2)

                # Confirm both inodes were persisted.
                self.assertEqual(r1.files_table.all().__len__(), 2)
            finally:
                r1.close()
                r2.close()


if __name__ == "__main__":
    unittest.main()
