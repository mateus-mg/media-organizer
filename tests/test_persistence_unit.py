#!/usr/bin/env python3
"""Unit tests for persistence layer."""

import tempfile
import unittest
from pathlib import Path
from tinydb import Query

from app.infrastructure.database import OrganizationDatabase


class TestOrganizationDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp_dir.name)
        self.db_path = self.base / "organization.json"
        self.db = OrganizationDatabase(self.db_path, backup_enabled=False)

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()

    def test_add_media_updates_stats_for_music_and_lyrics(self):
        ok_music = self.db.adicionar_midia(
            file_hash="h1",
            original_path="/src/song.mp3",
            organized_path="/lib/song.mp3",
            metadata={"media_type": "music"},
        )
        ok_lyrics = self.db.adicionar_midia(
            file_hash="h2",
            original_path="/src/song.lrc",
            organized_path="/lib/song.lrc",
            metadata={"media_type": "lyrics"},
        )

        stats = self.db.get_stats()
        self.assertTrue(ok_music)
        self.assertTrue(ok_lyrics)
        self.assertEqual(stats["total_files_organized"], 2)
        self.assertEqual(stats["music_tracks"], 1)
        self.assertEqual(stats["lyrics_files"], 1)

    def test_lookup_by_original_path(self):
        self.db.adicionar_midia(
            file_hash="h3",
            original_path="/src/book.epub",
            organized_path="/lib/book.epub",
            metadata={"media_type": "book"},
        )

        record = self.db.get_record_by_original_path("/src/book.epub")
        self.assertIsNotNone(record)
        self.assertEqual(record["organized_path"], "/lib/book.epub")
        self.assertTrue(self.db.is_file_organized("/src/book.epub"))

    def test_add_media_prevents_duplicate_organized_path(self):
        ok_first = self.db.adicionar_midia(
            file_hash="h4",
            original_path="/src/a.flac",
            organized_path="/lib/shared.flac",
            metadata={"media_type": "music", "genre": "Pop"},
        )
        ok_second = self.db.adicionar_midia(
            file_hash="h5",
            original_path="/src/b.flac",
            organized_path="/lib/shared.flac",
            metadata={"media_type": "music", "genre": "Rock"},
        )

        Media = self.db.media_table
        records = Media.search(Query().organized_path == "/lib/shared.flac")

        self.assertTrue(ok_first)
        self.assertTrue(ok_second)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["metadata"].get("genre"), "Rock")

        stats = self.db.get_stats()
        self.assertEqual(stats["total_files_organized"], 1)

    def test_add_failure_increments_counter(self):
        before = self.db.get_stats()["failed_operations"]
        self.db.add_failure("/src/a.mp3", "test", "error")
        after = self.db.get_stats()["failed_operations"]

        self.assertEqual(after, before + 1)
        failures = self.db.get_failures(limit=5)
        self.assertGreaterEqual(len(failures), 1)

    def test_create_backup_includes_invalid_genres_catalog(self):
        self.db.close()
        self.db = OrganizationDatabase(self.db_path, backup_enabled=True)

        invalid_path = self.base / "invalid_music_genres.json"
        invalid_path.write_text(
            '{"version":1,"updated_at":"x","exact":["foo"],"regex":[],"auto_added":{}}',
            encoding="utf-8",
        )

        backup_path = self.db.create_backup()
        self.assertIsNotNone(backup_path)

        invalid_backups = list(
            (self.base / "backups").glob("invalid_music_genres_*.json"))
        self.assertTrue(invalid_backups)

    def test_create_backup_includes_suspect_and_link_registry(self):
        self.db.close()
        self.db = OrganizationDatabase(self.db_path, backup_enabled=True)

        suspect_path = self.base / "suspect_music_genres.json"
        suspect_path.write_text(
            '{"version":1,"updated_at":"x","threshold_for_auto_add":3,"items":{}}',
            encoding="utf-8",
        )

        link_registry_path = self.base / "link_registry.json"
        link_registry_path.write_text(
            '{"files": {"1": []}}',
            encoding="utf-8",
        )

        backup_path = self.db.create_backup()
        self.assertIsNotNone(backup_path)

        suspect_backups = list(
            (self.base / "backups").glob("suspect_music_genres_*.json"))
        link_backups = list(
            (self.base / "backups").glob("link_registry_*.json"))

        self.assertTrue(suspect_backups)
        self.assertTrue(link_backups)


if __name__ == "__main__":
    unittest.main()
