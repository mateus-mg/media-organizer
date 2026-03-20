#!/usr/bin/env python3
"""Unit tests for organizers."""

import asyncio
import io
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.core import MediaType
from src.organizers import BookOrganizer, LyricsOrganizer, MusicOrganizer


class _FakeDatabase:
    def __init__(self):
        self.organized = set()
        self.records = {}

    def is_file_organized(self, file_path):
        return file_path in self.organized

    def adicionar_midia(self, file_hash, original_path, organized_path, metadata):
        self.records[original_path] = {
            "file_hash": file_hash,
            "organized_path": organized_path,
            "metadata": metadata,
        }
        return True

    def get_record_by_original_path(self, file_path):
        return self.records.get(file_path)


class _FakeConflictHandler:
    def resolve(self, source_path, dest_path, dry_run=False):
        return dest_path, "no_conflict"


class _FakeConfig:
    def __init__(self, base):
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
        self.lastfm_api_key = ""


class TestMusicOrganizer(unittest.TestCase):
    def test_extract_metadata_supports_title_artist_filename_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            organizer = MusicOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
            )

            src = base / "Dancing With A Stranger - Sam Smith, Normani.flac"
            src.write_text("dummy", encoding="utf-8")

            meta = organizer._extract_metadata_from_filename(
                src,
                existing_title="Dancing With A Stranger",
            )

            self.assertEqual(meta["title"], "Dancing With A Stranger")
            self.assertEqual(meta["artist"], "Sam Smith, Normani")
            self.assertEqual(meta["primary_artist"], "Sam Smith")

    def test_extract_metadata_uses_existing_generic_artist_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            organizer = MusicOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
            )

            src = base / "Home - Live - Michael Buble, Blake Shelton.flac"
            src.write_text("dummy", encoding="utf-8")

            meta = organizer._extract_metadata_from_filename(
                src,
                existing_title="Home - Live",
                existing_artist="Various Artists",
            )

            self.assertEqual(meta["title"], "Home - Live")
            self.assertEqual(meta["artist"], "Michael Buble, Blake Shelton")
            self.assertEqual(meta["primary_artist"], "Michael Buble")

    def test_extract_metadata_uses_title_prefix_when_filename_has_many_hyphens(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            organizer = MusicOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
            )

            src = base / "Girls Like You - Cardi B Version - Maroon 5, Cardi B.flac"
            src.write_text("dummy", encoding="utf-8")

            meta = organizer._extract_metadata_from_filename(
                src,
                existing_title="Girls Like You - Cardi B Version",
                existing_artist="Various Artists",
            )

            self.assertEqual(meta["title"], "Girls Like You - Cardi B Version")
            self.assertEqual(meta["artist"], "Maroon 5, Cardi B")
            self.assertEqual(meta["primary_artist"], "Maroon 5")

    def test_get_primary_artist_preserves_duo_and_reduces_collaboration(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            organizer = MusicOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
            )

            primary = organizer._get_primary_artist(
                "Guilherme & Benuto, Hugo & Guilherme"
            )
            self.assertEqual(primary, "Guilherme & Benuto")

    def test_get_primary_artist_preserves_other_duo_market_connectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            organizer = MusicOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
            )

            self.assertEqual(
                organizer._get_primary_artist(
                    "Zé Neto e Cristiano, Ana Castela"),
                "Zé Neto e Cristiano",
            )
            self.assertEqual(
                organizer._get_primary_artist("Mau y Ricky, Manuel Turizo"),
                "Mau y Ricky",
            )
            self.assertEqual(
                organizer._get_primary_artist(
                    "Simon and Garfunkel, Paul Simon"),
                "Simon and Garfunkel",
            )

    def test_update_audio_tags_normalizes_collaborative_artist_in_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)

            stream = io.StringIO()
            logger = logging.getLogger("test.music.normalize.collab")
            logger.handlers = []
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler(stream)
            logger.addHandler(handler)
            logger.propagate = False

            organizer = MusicOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logger,
                dry_run=True,
            )

            file_path = base / "sample.mp3"
            file_path.write_text("dummy", encoding="utf-8")

            result = organizer._update_audio_tags(
                file_path=file_path,
                original_metadata={
                    "artist": "Artist A, Artist B",
                    "album_artist": "Artist A, Artist B",
                    "album": "Singles",
                    "genre": "Pop",
                    "title": "Song",
                    "year": 2024,
                    "musicbrainz_trackid": "mbid-1",
                    "isrc": "isrc-1",
                },
                final_metadata={
                    "primary_artist": "Artist A", "album": "Singles"},
                online_metadata=None,
            )

            self.assertTrue(result)
            log_output = stream.getvalue()
            self.assertIn("Would update", log_output)
            self.assertIn("album_artist, artist", log_output)

    def test_update_audio_tags_skips_when_artist_already_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)

            stream = io.StringIO()
            logger = logging.getLogger("test.music.normalize.clean")
            logger.handlers = []
            logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler(stream)
            logger.addHandler(handler)
            logger.propagate = False

            organizer = MusicOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logger,
                dry_run=True,
            )

            file_path = base / "sample.flac"
            file_path.write_text("dummy", encoding="utf-8")

            result = organizer._update_audio_tags(
                file_path=file_path,
                original_metadata={
                    "artist": "Artist A",
                    "album_artist": "Artist A",
                    "album": "Singles",
                    "genre": "Pop",
                    "title": "Song",
                    "year": 2024,
                    "musicbrainz_trackid": "mbid-1",
                    "isrc": "isrc-1",
                },
                final_metadata={
                    "primary_artist": "Artist A", "album": "Singles"},
                online_metadata=None,
            )

            self.assertTrue(result)
            self.assertIn(
                "File already has normalized metadata or no updates needed",
                stream.getvalue(),
            )

    def test_update_audio_tags_normalizes_various_artists_in_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)

            stream = io.StringIO()
            logger = logging.getLogger("test.music.normalize.various")
            logger.handlers = []
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler(stream)
            logger.addHandler(handler)
            logger.propagate = False

            organizer = MusicOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logger,
                dry_run=True,
            )

            file_path = base / "sample.flac"
            file_path.write_text("dummy", encoding="utf-8")

            result = organizer._update_audio_tags(
                file_path=file_path,
                original_metadata={
                    "artist": "Various Artists",
                    "album_artist": "Various Artists",
                    "album": "Unknown Album",
                },
                final_metadata={
                    "primary_artist": "Sam Smith", "album": "Singles"},
                online_metadata=None,
            )

            self.assertTrue(result)
            log_output = stream.getvalue()
            self.assertIn("Would update", log_output)
            self.assertIn("album_artist, artist", log_output)

    def test_destination_path_uses_track_number_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            organizer = MusicOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
            )
            src = base / "01 - Song.mp3"
            src.write_text("dummy", encoding="utf-8")

            dest = organizer.get_destination_path(
                src,
                {"artist": "Artist", "album": "Album",
                    "track_name": "Song", "track_number": "1"},
            )

            self.assertEqual(dest.name, "01 - Song.mp3")
            self.assertIn("Artist", str(dest))
            self.assertIn("Album", str(dest))

    def test_destination_path_uses_singles_when_album_missing_and_artist_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            organizer = MusicOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
            )
            src = base / "Solo Song.mp3"
            src.write_text("dummy", encoding="utf-8")

            dest = organizer.get_destination_path(
                src,
                {
                    "artist": "Artist",
                    "album": "",
                    "track_name": "Solo Song",
                    "track_number": None,
                },
            )

            self.assertIn("Artist", str(dest))
            self.assertIn("Singles", str(dest))
            self.assertEqual(dest.name, "Solo Song.mp3")

    def test_final_metadata_sets_album_to_singles_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            organizer = MusicOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
            )

            final = organizer._determine_final_metadata(
                existing_tags_metadata={"artist": "Artist", "album": ""},
                filename_metadata={
                    "track_name": "Solo Song", "title": "Solo Song"},
                file_path=base / "Solo Song.mp3",
                online_metadata=None,
            )

            self.assertEqual(final.get("artist"), "Artist")
            self.assertEqual(final.get("album"), "Singles")


class TestLyricsOrganizer(unittest.IsolatedAsyncioTestCase):
    async def test_lyrics_follow_existing_audio_record_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            db = _FakeDatabase()
            organizer = LyricsOrganizer(
                config=cfg,
                database=db,
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
            )

            source_dir = base / "downloads"
            source_dir.mkdir(parents=True, exist_ok=True)
            audio = source_dir / "track.mp3"
            lyrics = source_dir / "track.lrc"
            audio.write_text("audio", encoding="utf-8")
            lyrics.write_text("[00:01] line", encoding="utf-8")

            db.records[str(audio)] = {
                "organized_path": str(base / "library" / "music" / "Artist" / "Album" / "track.mp3")
            }

            result = await organizer.organizar(lyrics)

            self.assertTrue(result.success)
            self.assertEqual(result.metadata.get("media_type"), "lyrics")
            self.assertTrue(str(result.organized_path).endswith("track.lrc"))

    async def test_unmatched_lyrics_go_to_fallback_hash_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            organizer = LyricsOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
            )

            lyrics = base / "downloads" / "lonely.lrc"
            lyrics.parent.mkdir(parents=True, exist_ok=True)
            lyrics.write_text("[00:01] lonely", encoding="utf-8")

            result = await organizer.organizar(lyrics)

            self.assertTrue(result.success)
            self.assertIn("_lyrics_unmatched", str(result.organized_path))
            self.assertTrue(str(result.organized_path).endswith(".lrc"))


class TestBookOrganizer(unittest.TestCase):
    def test_book_and_comic_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            common_kwargs = {
                "config": cfg,
                "database": _FakeDatabase(),
                "conflict_handler": _FakeConflictHandler(),
                "logger": logging.getLogger("test"),
                "dry_run": True,
            }
            book_org = BookOrganizer(**common_kwargs, book_type="book")
            comic_org = BookOrganizer(**common_kwargs, book_type="comic")

            self.assertEqual(book_org.obter_tipo_midia(), MediaType.BOOK)
            self.assertEqual(comic_org.obter_tipo_midia(), MediaType.COMIC)
            self.assertTrue(book_org.pode_processar(Path("a.epub")))
            self.assertTrue(comic_org.pode_processar(Path("a.cbz")))

    def test_multi_author_book_uses_first_author_for_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            org = BookOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
                book_type="book",
            )

            src = base / "Author One, Author Two - Shared Book (2021).epub"
            src.write_text("x", encoding="utf-8")

            # Test metadata extraction
            meta = org._extract_book_metadata(src)
            self.assertEqual(meta["authors"], ["Author One", "Author Two"])
            self.assertEqual(meta["author"], "Author One")
            # Year is extracted separately; title should not repeat it
            self.assertEqual(meta["title"], "Shared Book")
            self.assertEqual(meta["year"], 2021)

            # Test folder path uses first author only (check folder, not filename)
            dest = org.get_book_destination_path(src, meta)
            folder = str(dest.parent)
            self.assertIn("Author One", folder)
            self.assertNotIn("Author Two", folder)

    def test_single_author_book_authors_list_has_one_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            org = BookOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
                book_type="book",
            )

            src = base / "Martin Fowler - Refactoring (1999).epub"
            src.write_text("x", encoding="utf-8")

            meta = org._extract_book_metadata(src)
            self.assertEqual(meta["authors"], ["Martin Fowler"])
            self.assertEqual(meta["author"], "Martin Fowler")

    def test_book_destination_does_not_create_title_subfolder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            org = BookOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
                book_type="book",
            )

            src = base / "Author Name - Great Book (2020).epub"
            src.write_text("x", encoding="utf-8")

            meta = org._extract_book_metadata(src)
            dest = org.get_book_destination_path(src, meta)

            self.assertEqual(
                dest.parent, cfg.library_path_books / "Author Name")
            self.assertEqual(dest.name, src.name)

    def test_normalize_book_genre_keeps_single_primary_genre(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            org = BookOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
                book_type="book",
            )

            self.assertEqual(
                org._normalize_book_genre("Ficção - Fantasia - Juvenil"),
                "Ficção",
            )
            self.assertEqual(
                org._normalize_book_genre(
                    "1. Amor - Aspectos religiosos - Cristianismo 2. Deus - Amor"
                ),
                "Amor",
            )
            self.assertEqual(
                org._normalize_book_genre("Fiction / Fantasy / Epic"),
                "Fiction",
            )

    def test_book_destination_ignores_genre_and_uses_author_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            org = BookOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
                book_type="book",
            )

            src = base / "Author Name - Great Book (2020).epub"
            src.write_text("x", encoding="utf-8")

            meta = org._extract_book_metadata(src)
            meta["genre"] = "Fantasy"
            dest = org.get_book_destination_path(src, meta)

            self.assertEqual(
                dest.parent, cfg.library_path_books / "Author Name")
            self.assertEqual(dest.name, src.name)

    def test_book_destination_without_genre_uses_author_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            org = BookOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
                book_type="book",
            )

            src = base / "Author Name - Great Book (2020).epub"
            src.write_text("x", encoding="utf-8")

            meta = org._extract_book_metadata(src)
            dest = org.get_book_destination_path(src, meta)

            self.assertEqual(
                dest.parent, cfg.library_path_books / "Author Name")

    def test_online_book_enrichment_fills_genre_only_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            cfg.enrich_book_metadata = True
            cfg.enrich_book_metadata_online = True
            org = BookOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
                book_type="book",
            )

            src = base / "Author Name - Great Book (2020).epub"
            src.write_text("x", encoding="utf-8")

            with patch.object(org, "_extract_epub_embedded_metadata", return_value={}), patch(
                "src.organizers.enrich_book_metadata_with_online_sources",
                new=AsyncMock(return_value={
                    "title": "Great Book",
                    "author": "Author Name",
                    "genre": "Science Fiction",
                    "series": "Saga Book",
                    "series_index": 2,
                    "subjects": ["Science Fiction", "Adventure"],
                }),
            ) as enrich_mock:
                enriched = asyncio.run(
                    org._enrich_book_metadata_if_needed(
                        src,
                        {
                            "title": "Great Book",
                            "author": "Author Name",
                        },
                    )
                )

                self.assertEqual(enriched.get("genre"), "Science Fiction")
                self.assertEqual(enriched.get("series"), "Saga Book")
                self.assertEqual(enriched.get("series_index"), 2)
                self.assertEqual(
                    enriched.get("subjects"),
                    ["Science Fiction", "Adventure"],
                )
                enrich_mock.assert_awaited_once()

            with patch.object(
                org,
                "_extract_epub_embedded_metadata",
                return_value={"genre": "Fantasy", "series": "Series A"},
            ), patch(
                "src.organizers.enrich_book_metadata_with_online_sources",
                new=AsyncMock(),
            ) as enrich_mock:
                enriched = asyncio.run(
                    org._enrich_book_metadata_if_needed(
                        src,
                        {
                            "title": "Great Book",
                            "author": "Author Name",
                        },
                    )
                )

                self.assertEqual(enriched.get("genre"), "Fantasy")
                self.assertEqual(enriched.get("series"), "Series A")
                enrich_mock.assert_awaited_once()

    def test_comic_destination_uses_series_folder_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = _FakeConfig(base)
            org = BookOrganizer(
                config=cfg,
                database=_FakeDatabase(),
                conflict_handler=_FakeConflictHandler(),
                logger=logging.getLogger("test"),
                dry_run=True,
                book_type="comic",
            )

            src = base / "Guerra Civil I #003 (Marvel) (2006).cbr"
            src.write_text("x", encoding="utf-8")

            meta = org._extract_comic_metadata(src)
            dest = org.get_comic_destination_path(src, meta)

            self.assertEqual(
                dest.parent, cfg.library_path_comics / "Guerra Civil I")
            self.assertTrue(dest.name.startswith("Guerra Civil I #003"))


if __name__ == "__main__":
    unittest.main()
