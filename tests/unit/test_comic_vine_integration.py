#!/usr/bin/env python3
"""Unit tests for Comic Vine integration in BookOrganizer."""

import asyncio
import logging
import tempfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.organizers import BookOrganizer


class _FakeConfig:
    def __init__(self, base):
        self.download_path_music = base / "downloads" / "music"
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
        self.infer_genre_from_source_path = True
        self.enrich_music_metadata_online = False
        self.music_genre_complement_enabled = True
        self.music_genre_complement_max_existing_genres = 1
        self.music_genre_complement_max_total_genres = 4
        self.lastfm_api_key = ""
        self.comic_vine_enabled = True
        self.comic_vine_api_key = "test_api_key"
        self.comic_vine_translate_series_names = True
        self.comic_vine_api_delay_seconds = 1.0
        self.comic_vine_timeout_seconds = 15.0
        self.comic_vine_min_match_score = 75


class _FakeDatabase:
    def __init__(self):
        self._organized = set()

    def is_file_organized(self, path):
        return str(path) in self._organized

    def register_organized_file(self, path):
        self._organized.add(str(path))


class _FakeConflictHandler:
    def check(self, src, dst, metadata):
        return None


class TestEnrichComicMetadataIfNeeded(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.cfg = _FakeConfig(self.base)
        self.common_kwargs = {
            "config": self.cfg,
            "database": _FakeDatabase(),
            "conflict_handler": _FakeConflictHandler(),
            "logger": logging.getLogger("test"),
            "dry_run": True,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_organizer(self, **config_overrides):
        if config_overrides:
            for key, value in config_overrides.items():
                setattr(self.cfg, key, value)
        organizer = BookOrganizer(
            **self.common_kwargs,
            book_type="comic",
        )
        return organizer

    async def test_enrichment_is_called_when_comic_vine_enabled(self):
        organizer = self._create_organizer()
        organizer.logger = MagicMock()

        mock_client = MagicMock()
        mock_client.search_issue = AsyncMock(return_value=[])
        mock_client.map_to_comic_metadata = MagicMock(return_value={})

        with patch("app.metadata.comic_vine.ComicVineClient", return_value=mock_client):
            metadata = {
                "title": "Homem Aranha",
                "series": "Homem Aranha",
                "issue_number": "300",
                "year": 2020,
            }
            result = await organizer._enrich_comic_metadata_if_needed(
                Path("test.cbz"), metadata
            )

        mock_client.search_issue.assert_called_once()

    async def test_series_and_title_are_not_overwritten(self):
        organizer = self._create_organizer()
        organizer.logger = MagicMock()

        comic_vine_response = {
            "name": "Amazing Spider-Man #300",
            "issue_number": "300",
            "cover_date": "2020-05-01",
            "volume": {"name": "Spider-Man"},
            "image": {"super_url": "http://example.com/cover.jpg"},
            "id": 12345,
        }

        mock_client = MagicMock()
        mock_client.search_issue = AsyncMock(return_value=[comic_vine_response])
        mock_client.map_to_comic_metadata.return_value = {
            "title": "Spider-Man #300",
            "series": "Spider-Man",
            "issue_number": "300",
            "year": 2020,
            "author": "David Michelinie",
            "cover_image_url": "http://example.com/cover.jpg",
        }

        with patch("app.metadata.comic_vine.ComicVineClient", return_value=mock_client):
            metadata = {
                "title": "Homem Aranha",
                "series": "Homem Aranha",
                "issue_number": "300",
                "year": 2020,
            }
            result = await organizer._enrich_comic_metadata_if_needed(
                Path("test.cbz"), metadata
            )

        self.assertEqual(result["title"], "Homem Aranha")
        self.assertEqual(result["series"], "Homem Aranha")

    async def test_enrichment_fields_are_populated(self):
        organizer = self._create_organizer()
        organizer.logger = MagicMock()

        comic_vine_response = {
            "name": "Batman #100",
            "issue_number": "100",
            "cover_date": "2020-05-01",
            "volume": {"name": "Batman"},
            "image": {"super_url": "http://example.com/cover.jpg"},
            "id": 12345,
            "person_credits": [
                {"name": "Chuck Dix", "role": "writer"},
                {"name": "Brett Anderson", "role": "penciler"},
            ],
        }

        mock_client = MagicMock()
        mock_client.search_issue = AsyncMock(return_value=[comic_vine_response])
        mock_client.map_to_comic_metadata.return_value = {
            "title": "Batman #100",
            "series": "Batman",
            "issue_number": "100",
            "year": 2020,
            "author": "Chuck Dix",
            "penciller": "Brett Anderson",
            "cover_image_url": "http://example.com/cover.jpg",
            "comic_vine_id": 12345,
        }

        with patch("app.metadata.comic_vine.ComicVineClient", return_value=mock_client):
            metadata = {
                "title": "Batman",
                "series": "Batman",
                "issue_number": "100",
                "year": 2020,
            }
            result = await organizer._enrich_comic_metadata_if_needed(
                Path("test.cbz"), metadata
            )

        self.assertEqual(result.get("author"), "Chuck Dix")
        self.assertEqual(result.get("penciller"), "Brett Anderson")
        self.assertEqual(result.get("cover_image_url"), "http://example.com/cover.jpg")
        self.assertEqual(result.get("comic_vine_id"), 12345)

    async def test_enrichment_is_skipped_when_disabled(self):
        organizer = self._create_organizer(comic_vine_enabled=False)
        organizer.logger = MagicMock()

        metadata = {
            "title": "Homem Aranha",
            "series": "Homem Aranha",
            "issue_number": "300",
            "year": 2020,
        }
        result = await organizer._enrich_comic_metadata_if_needed(
            Path("test.cbz"), metadata
        )

        self.assertEqual(result["title"], "Homem Aranha")
        self.assertIsNone(result.get("author"))

    async def test_enrichment_skips_when_no_series_name(self):
        organizer = self._create_organizer()
        organizer.logger = MagicMock()

        metadata = {
            "issue_number": "300",
            "year": 2020,
        }
        result = await organizer._enrich_comic_metadata_if_needed(
            Path("test.cbz"), metadata
        )

        self.assertIsNone(result.get("author"))

    async def test_enrichment_skips_when_no_issue_number_or_year(self):
        organizer = self._create_organizer()
        organizer.logger = MagicMock()

        metadata = {
            "title": "Homem Aranha",
            "series": "Homem Aranha",
        }
        result = await organizer._enrich_comic_metadata_if_needed(
            Path("test.cbz"), metadata
        )

        self.assertIsNone(result.get("author"))

    async def test_enrichment_does_not_overwrite_existing_fields(self):
        organizer = self._create_organizer()
        organizer.logger = MagicMock()

        comic_vine_response = {
            "name": "Batman #100",
            "issue_number": "100",
            "cover_date": "2020-05-01",
            "volume": {"name": "Batman"},
            "person_credits": [
                {"name": "New Writer", "role": "writer"},
            ],
        }

        mock_client = MagicMock()
        mock_client.search_issue = AsyncMock(return_value=[comic_vine_response])
        mock_client.map_to_comic_metadata.return_value = {
            "title": "Batman #100",
            "series": "Batman",
            "issue_number": "100",
            "year": 2020,
            "author": "New Writer",
        }

        with patch("app.metadata.comic_vine.ComicVineClient", return_value=mock_client):
            metadata = {
                "title": "Batman",
                "series": "Batman",
                "issue_number": "100",
                "year": 2020,
                "author": "Original Writer",
            }
            result = await organizer._enrich_comic_metadata_if_needed(
                Path("test.cbz"), metadata
            )

        self.assertEqual(result.get("author"), "Original Writer")

    async def test_import_error_handled_gracefully(self):
        organizer = self._create_organizer()
        organizer.logger = MagicMock()

        with patch.dict("sys.modules", {"deep_translator": None}):
            with patch("app.metadata.comic_vine.ComicVineClient", side_effect=ImportError):
                metadata = {
                    "title": "Batman",
                    "series": "Batman",
                    "issue_number": "100",
                    "year": 2020,
                }
                result = await organizer._enrich_comic_metadata_if_needed(
                    Path("test.cbz"), metadata
                )

        self.assertEqual(result.get("title"), "Batman")
        organizer.logger.warning.assert_called_once()

    async def test_general_exception_handled_gracefully(self):
        organizer = self._create_organizer()
        organizer.logger = MagicMock()

        with patch("app.metadata.comic_vine.ComicVineClient", side_effect=Exception("API Error")):
            metadata = {
                "title": "Batman",
                "series": "Batman",
                "issue_number": "100",
                "year": 2020,
            }
            result = await organizer._enrich_comic_metadata_if_needed(
                Path("test.cbz"), metadata
            )

        self.assertEqual(result.get("title"), "Batman")
        organizer.logger.warning.assert_called_once()


class TestOrganizarCallsEnrichment(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.cfg = _FakeConfig(self.base)
        self.common_kwargs = {
            "config": self.cfg,
            "database": _FakeDatabase(),
            "conflict_handler": _FakeConflictHandler(),
            "logger": logging.getLogger("test"),
            "dry_run": True,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_organizer(self, **config_overrides):
        if config_overrides:
            for key, value in config_overrides.items():
                setattr(self.cfg, key, value)
        organizer = BookOrganizer(
            **self.common_kwargs,
            book_type="comic",
        )
        return organizer

    async def test_organizar_calls_enrichment_for_comics(self):
        organizer = self._create_organizer()
        organizer.logger = MagicMock()
        organizer._write_comicinfo_xml = MagicMock()
        organizer.organizar_file = AsyncMock()

        mock_client = MagicMock()
        mock_client.search_issue = AsyncMock(return_value=[])
        mock_client.map_to_comic_metadata = MagicMock(return_value={})

        with patch("app.metadata.comic_vine.ComicVineClient", return_value=mock_client):
            with patch.object(organizer, "_extract_comic_metadata", return_value={
                "title": "Batman",
                "series": "Batman",
                "issue_number": "100",
                "year": 2020,
                "filename_schema_valid": True,
            }):
                comic_file = self.base / "downloads" / "comics" / "Batman #100 (2020).cbz"
                comic_file.parent.mkdir(parents=True, exist_ok=True)
                comic_file.touch()
                try:
                    await organizer.organizar(comic_file)
                except Exception as ex:
                    pass

        mock_client.search_issue.assert_called_once()


if __name__ == "__main__":
    unittest.main()
