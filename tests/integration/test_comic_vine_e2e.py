import asyncio
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


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
        self.comic_vine_download_covers = True
        self.comic_download_covers = False
        self.dry_run = False


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


class TestComicVineE2E(unittest.IsolatedAsyncioTestCase):
    """End-to-end test without real API calls (mocked)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.cfg = _FakeConfig(self.base)
        self.common_kwargs = {
            "config": self.cfg,
            "database": _FakeDatabase(),
            "conflict_handler": _FakeConflictHandler(),
            "logger": logging.getLogger("test"),
            "dry_run": False,
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

    async def test_full_enrichment_flow(self):
        """Test that enrichment works end-to-end with mocks."""
        organizer = self._create_organizer()
        organizer.logger = MagicMock()

        comic_file = self.base / "Guerra Civil II #01.cbz"
        comic_file.touch()

        mock_client = MagicMock()
        mock_client.search_issue = AsyncMock(return_value=[{
            "name": "Civil War II #1",
            "issue_number": "1",
            "cover_date": "2016-01-01",
            "volume": {"name": "Civil War II", "publisher": {"name": "Marvel Comics"}},
            "description": "Test description",
            "image": {"super_url": "http://example.com/c.jpg"},
            "person_credits": [
                {"name": "Mark Millar", "role": "writer"},
                {"name": "Steve McNiven", "role": "penciller"},
                {"name": "Justin Ponsor", "role": "colorist"},
            ],
        }])
        mock_client.map_to_comic_metadata.return_value = {
            "title": "Civil War II #1",
            "series": "Civil War II",
            "issue_number": "1",
            "year": 2016,
            "month": 1,
            "publisher": "Marvel Comics",
            "description": "Test description",
            "cover_image_url": "http://example.com/c.jpg",
            "author": "Mark Millar",
            "penciller": "Steve McNiven",
            "colorist": "Justin Ponsor",
            "comic_vine_id": "12345",
            "comic_vine_url": "https://comicvine.gamespot.com/civil-war-ii-1/4000-12345/",
        }

        with patch("app.metadata.comic_vine.ComicVineClient", return_value=mock_client):
            metadata = {
                "title": "Guerra Civil II #1",
                "series": "Guerra Civil II",
                "issue_number": "1",
                "year": 2016,
            }

            enriched = await organizer._enrich_comic_metadata_if_needed(comic_file, metadata)

            # CRITICAL: Portuguese series/title must NOT be overwritten
            self.assertEqual(enriched.get("series"), "Guerra Civil II")
            self.assertEqual(enriched.get("title"), "Guerra Civil II #1")

            # Enrichment fields must be populated
            self.assertEqual(enriched.get("author"), "Mark Millar")
            self.assertEqual(enriched.get("penciller"), "Steve McNiven")
            self.assertEqual(enriched.get("colorist"), "Justin Ponsor")
            self.assertEqual(enriched.get("publisher"), "Marvel Comics")
            self.assertEqual(enriched.get("description"), "Test description")

    async def test_enrichment_skipped_when_disabled(self):
        """Test that enrichment is skipped when disabled."""
        organizer = self._create_organizer(comic_vine_enabled=False)
        organizer.logger = MagicMock()

        comic_file = self.base / "Test.cbz"
        comic_file.touch()

        metadata = {"title": "Test", "series": "Test Series"}

        result = await organizer._enrich_comic_metadata_if_needed(comic_file, metadata)

        # Should return original metadata unchanged
        self.assertEqual(result.get("title"), "Test")
        self.assertEqual(result.get("series"), "Test Series")


from app.services.organizers import BookOrganizer