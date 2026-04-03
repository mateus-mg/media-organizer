#!/usr/bin/env python3
"""Simulated test battery for books and comics organization."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.main import MediaOrganizerApp
from app.services.organizers import BookOrganizer


class _FakeDatabase:
    def __init__(self):
        self.organized = set()
        self.add_calls = []

    def is_file_organized(self, file_path):
        return file_path in self.organized

    def adicionar_midia(self, file_hash, original_path, organized_path, metadata):
        self.add_calls.append(
            {
                "file_hash": file_hash,
                "original_path": original_path,
                "organized_path": organized_path,
                "metadata": metadata,
            }
        )
        return True


class _FakeConfig:
    def __init__(self, base: Path):
        self.download_path_books = base / "downloads" / "books"
        self.download_path_comics = base / "downloads" / "comics"
        self.library_path_music = base / "library" / "music"
        self.library_path_books = base / "library" / "books"
        self.library_path_comics = base / "library" / "comics"
        self.link_registry_path = base / "data" / "link_registry.json"
        self.calibre_enabled = False
        self.enrich_book_metadata = True
        self.enrich_book_metadata_online = False
        self.enrich_book_metadata_google_books = True
        self.book_cover_min_match_score = 80
        self.google_books_api_key = ""
        self.book_metadata_trust_mode = "missing_only"
        self.book_cover_update_enabled = False


class _FakeConflictHandler:
    def __init__(self, forced_dest: Path | None = None):
        self.forced_dest = forced_dest

    def resolve(self, source_path: Path, dest_path: Path, dry_run: bool = False):
        if self.forced_dest is not None:
            return self.forced_dest, "renamed"
        return dest_path, "no_conflict"


class TestBookComicOrganizerUnit(unittest.IsolatedAsyncioTestCase):
    async def test_book_metadata_and_destination_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            db = _FakeDatabase()
            organizer = BookOrganizer(
                config=cfg,
                database=db,
                conflict_handler=_FakeConflictHandler(),
                logger=__import__("logging").getLogger("test"),
                dry_run=True,
                book_type="book",
            )

            src = base / "downloads" / "Author One - Clean Code (2008).epub"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text("book", encoding="utf-8")

            result = await organizer.organizar(src)

            self.assertTrue(result.success)
            self.assertIn("Author One", str(result.organized_path))
            self.assertIn("Clean Code (2008)", str(result.organized_path))
            self.assertEqual(result.metadata.get("media_type"), "book")

    async def test_comic_metadata_and_destination_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            db = _FakeDatabase()
            organizer = BookOrganizer(
                config=cfg,
                database=db,
                conflict_handler=_FakeConflictHandler(),
                logger=__import__("logging").getLogger("test"),
                dry_run=True,
                book_type="comic",
            )

            src = base / "downloads" / "Batman #001.cbz"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text("comic", encoding="utf-8")

            result = await organizer.organizar(src)

            self.assertTrue(result.success)
            self.assertIn("Batman", str(result.organized_path))
            self.assertTrue(
                str(result.organized_path).endswith("Batman #001.cbz"))
            self.assertEqual(result.metadata.get("media_type"), "comic")
            self.assertEqual(result.metadata.get("issue_number"), "001")

    async def test_non_dry_run_creates_hardlink_and_db_entry_for_book(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            db = _FakeDatabase()
            organizer = BookOrganizer(
                config=cfg,
                database=db,
                conflict_handler=_FakeConflictHandler(),
                logger=__import__("logging").getLogger("test"),
                dry_run=False,
                book_type="book",
            )

            src = base / "downloads" / \
                "Author Two - Domain Driven Design (2003).pdf"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text("ddd", encoding="utf-8")

            result = await organizer.organizar(src)

            self.assertTrue(result.success)
            self.assertTrue(result.organized_path.exists())
            self.assertEqual(src.stat().st_ino,
                             result.organized_path.stat().st_ino)
            self.assertEqual(len(db.add_calls), 1)
            self.assertEqual(
                db.add_calls[0]["metadata"].get("media_type"), "book")

    async def test_conflict_handler_forced_path_is_respected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            db = _FakeDatabase()
            expected = cfg.library_path_books / "Forced" / "forced.epub"
            organizer = BookOrganizer(
                config=cfg,
                database=db,
                conflict_handler=_FakeConflictHandler(forced_dest=expected),
                logger=__import__("logging").getLogger("test"),
                dry_run=True,
                book_type="book",
            )

            src = base / "downloads" / "Any Author - Any Book (2020).epub"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text("book", encoding="utf-8")

            result = await organizer.organizar(src)

            self.assertTrue(result.success)
            self.assertEqual(result.organized_path, expected)


class TestBookComicEndToEndSimulated(unittest.IsolatedAsyncioTestCase):
    async def test_app_routes_book_and_comic_and_updates_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            env = {
                "DATABASE_PATH": str(base / "data" / "organization.json"),
                "LINK_REGISTRY_PATH": str(base / "data" / "link_registry.json"),
                "LIBRARY_PATH_MUSIC": str(base / "library" / "music"),
                "LIBRARY_PATH_BOOKS": str(base / "library" / "books"),
                "LIBRARY_PATH_COMICS": str(base / "library" / "comics"),
                "DOWNLOAD_PATH_MUSIC": str(base / "downloads" / "music"),
                "DOWNLOAD_PATH_BOOKS": str(base / "downloads" / "books"),
                "DOWNLOAD_PATH_COMICS": str(base / "downloads" / "comics"),
                "CONFLICT_STRATEGY": "rename",
                "DATABASE_BACKUP_ENABLED": "false",
                "ENRICH_MUSIC_METADATA_ONLINE": "false",
            }

            download_root = base / "downloads" / "mixed"
            download_root.mkdir(parents=True, exist_ok=True)
            book_src = download_root / \
                "Author Three - Practical Vim (2012).epub"
            comic_src = download_root / "Saga #012.cbz"
            book_src.write_text("book", encoding="utf-8")
            comic_src.write_text("comic", encoding="utf-8")

            with patch.dict(os.environ, env, clear=False):
                app = MediaOrganizerApp(dry_run=False)
                try:
                    processed = await app.organize_directory(download_root, validate_completion=False)
                    stats = app.database.get_stats()
                    book_record = app.database.get_record_by_original_path(
                        str(book_src))
                    comic_record = app.database.get_record_by_original_path(
                        str(comic_src))
                finally:
                    app.cleanup()

            self.assertEqual(processed, 2)
            self.assertEqual(stats.get("books"), 1)
            self.assertEqual(stats.get("comics"), 1)

            self.assertIsNotNone(book_record)
            self.assertIsNotNone(comic_record)

            book_dest = Path(book_record["organized_path"])
            comic_dest = Path(comic_record["organized_path"])

            self.assertTrue(book_dest.exists())
            self.assertTrue(comic_dest.exists())
            self.assertEqual(book_src.stat().st_ino, book_dest.stat().st_ino)
            self.assertEqual(comic_src.stat().st_ino, comic_dest.stat().st_ino)


if __name__ == "__main__":
    unittest.main()
