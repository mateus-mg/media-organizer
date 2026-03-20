#!/usr/bin/env python3
"""Unit tests for MediaOrganizerApp wiring and orchestration."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core import MediaType
from src.main import MediaOrganizerApp


class TestMediaOrganizerApp(unittest.IsolatedAsyncioTestCase):
    async def test_app_initialization_and_organize_directory(self):
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
                "CONFLICT_STRATEGY": "skip",
                "DATABASE_BACKUP_ENABLED": "false",
                "ENRICH_MUSIC_METADATA_ONLINE": "false",
            }

            download_root = base / "downloads" / "music"
            download_root.mkdir(parents=True, exist_ok=True)
            (download_root / "track.mp3").write_text("audio", encoding="utf-8")
            (download_root /
             "track.lrc").write_text("[00:01] line", encoding="utf-8")
            (download_root / "book.epub").write_text("book", encoding="utf-8")
            (download_root / "comic.cbz").write_text("comic", encoding="utf-8")

            with patch.dict(os.environ, env, clear=False):
                app = MediaOrganizerApp(dry_run=True)
                try:
                    self.assertIn(MediaType.LYRICS, app.organizadores)
                    processed = await app.organize_directory(download_root, validate_completion=False)
                finally:
                    app.cleanup()

            self.assertEqual(processed, 4)


if __name__ == "__main__":
    unittest.main()
