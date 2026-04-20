#!/usr/bin/env python3
"""Unit tests for Orquestrador processing order."""

import io
import logging
import tempfile
import unittest
from pathlib import Path

from app.core import MediaType, Orquestrador, OrganizationResult


class _FakeScanner:
    def __init__(self, files):
        self._files = files

    def scan_directory(self, _directory):
        return list(self._files)


class _FakeDatabase:
    def is_file_organized(self, _file_path):
        return False


class _FakeClassifier:
    def classificar_tipo_midia(self, file_path: Path):
        if file_path.suffix.lower() == ".lrc":
            return MediaType.LYRICS
        if file_path.suffix.lower() in {".mp3", ".flac", ".m4a", ".ogg", ".wav", ".aac", ".opus", ".m4b"}:
            return MediaType.MUSIC
        return MediaType.UNKNOWN


class _ComicsClassifier:
    def classificar_tipo_midia(self, file_path: Path):
        suffix = file_path.suffix.lower()
        if suffix in {".cbr", ".cbz", ".pdf"}:
            return MediaType.COMIC
        if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            return MediaType.ARTWORK
        return MediaType.UNKNOWN


class _BooksClassifier:
    def classificar_tipo_midia(self, file_path: Path):
        suffix = file_path.suffix.lower()
        if suffix in {".epub", ".mobi", ".azw3", ".pdf"}:
            return MediaType.BOOK
        return MediaType.UNKNOWN


class _BooksAndComicsClassifier:
    def classificar_tipo_midia(self, file_path: Path):
        suffix = file_path.suffix.lower()
        if suffix in {".epub", ".mobi", ".azw3"}:
            return MediaType.BOOK
        if suffix in {".cbr", ".cbz", ".pdf"}:
            return MediaType.COMIC
        return MediaType.UNKNOWN


class _RecordingOrganizer:
    def __init__(self, sink):
        self.sink = sink

    def pode_processar(self, _file_path: Path) -> bool:
        return True

    async def organizar(self, file_path: Path) -> OrganizationResult:
        self.sink.append(file_path.name)
        return OrganizationResult(success=True, skipped=False, organized_path=file_path)


def _build_logger_and_stream(name: str):
    stream = io.StringIO()
    logger = logging.getLogger(name)
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger, stream


class TestOrquestradorOrdering(unittest.IsolatedAsyncioTestCase):
    async def test_processes_music_and_lyrics_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            track1 = base / "Song One.mp3"
            lyric1 = base / "Song One.lrc"
            track2 = base / "Song Two.mp3"
            lyric2 = base / "Song Two.lrc"

            for file_path in [track1, lyric1, track2, lyric2]:
                file_path.write_text("x", encoding="utf-8")

            # Intentionally shuffled scan order to validate reordering.
            scan_order = [lyric2, lyric1, track1, track2]
            processed = []

            orchestrator = Orquestrador(
                validators=[],
                organizadores={
                    MediaType.MUSIC: _RecordingOrganizer(processed),
                    MediaType.LYRICS: _RecordingOrganizer(processed),
                },
                classifier=_FakeClassifier(),
                scanner=_FakeScanner(scan_order),
                database=_FakeDatabase(),
                file_completion_validator=None,
            )

            await orchestrator.organizar_arquivos(
                diretorio_origem=base,
                validar_completude_arquivo=False,
                source_label="Music",
                progress_unit="tracks",
            )

            self.assertEqual(
                processed,
                ["Song Two.mp3", "Song Two.lrc", "Song One.mp3", "Song One.lrc"],
            )

    async def test_deduplicates_identical_lyrics_across_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder_a = base / "a"
            folder_b = base / "b"
            folder_a.mkdir(parents=True, exist_ok=True)
            folder_b.mkdir(parents=True, exist_ok=True)

            lyric_a = folder_a / "Hello - Adele.lrc"
            lyric_b = folder_b / "Hello - Adele.lrc"
            lyric_a.write_text("[00:01.00]Hello", encoding="utf-8")
            lyric_b.write_text("[00:01.00]Hello", encoding="utf-8")

            processed = []
            organizer = _RecordingOrganizer(processed)
            organizer.dry_run = False

            orchestrator = Orquestrador(
                validators=[],
                organizadores={
                    MediaType.LYRICS: organizer,
                },
                classifier=_FakeClassifier(),
                scanner=_FakeScanner([lyric_a, lyric_b]),
                database=_FakeDatabase(),
                file_completion_validator=None,
            )

            await orchestrator.organizar_arquivos(
                diretorio_origem=base,
                validar_completude_arquivo=False,
                source_label="Music",
                progress_unit="tracks",
            )

            self.assertEqual(len(processed), 1)
            self.assertEqual(processed[0], "Hello - Adele.lrc")

    async def test_progress_breakdown_is_dynamic_for_comics(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            issue_1 = base / "Invencivel 001.cbr"
            issue_2 = base / "Invencivel 002.cbr"
            for file_path in [issue_1, issue_2]:
                file_path.write_text("x", encoding="utf-8")

            processed = []
            logger, stream = _build_logger_and_stream(
                "test.orchestrator.comics.dynamic")
            orchestrator = Orquestrador(
                validators=[],
                organizadores={
                    MediaType.COMIC: _RecordingOrganizer(processed),
                },
                classifier=_ComicsClassifier(),
                scanner=_FakeScanner([issue_1, issue_2]),
                database=_FakeDatabase(),
                file_completion_validator=None,
                logger=logger,
            )

            await orchestrator.organizar_arquivos(
                diretorio_origem=base,
                validar_completude_arquivo=False,
                source_label="Comics",
                progress_unit="files",
            )

            log_text = stream.getvalue()
            self.assertIn("Comics breakdown: comic=2", log_text)
            self.assertIn("comic(o/s/f)=2/0/0", log_text)
            self.assertNotIn("tracks(o/s/f)", log_text)
            self.assertNotIn("lyrics(o/s/f)", log_text)
            self.assertNotIn("artwork(o/s/f)=0/0/0", log_text)

    async def test_progress_log_uses_configured_progress_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            track = base / "Song One.mp3"
            track.write_text("x", encoding="utf-8")

            processed = []
            logger, stream = _build_logger_and_stream(
                "test.orchestrator.progress.unit")
            orchestrator = Orquestrador(
                validators=[],
                organizadores={
                    MediaType.MUSIC: _RecordingOrganizer(processed),
                },
                classifier=_FakeClassifier(),
                scanner=_FakeScanner([track]),
                database=_FakeDatabase(),
                file_completion_validator=None,
                logger=logger,
            )

            await orchestrator.organizar_arquivos(
                diretorio_origem=base,
                validar_completude_arquivo=False,
                source_label="Music",
                progress_unit="tracks",
            )

            log_text = stream.getvalue()
            self.assertIn("Music progress: 1/1 processed tracks", log_text)

    async def test_progress_breakdown_is_dynamic_for_books(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            book_1 = base / "Duna.epub"
            book_2 = base / "Neuromancer.mobi"
            for file_path in [book_1, book_2]:
                file_path.write_text("x", encoding="utf-8")

            processed = []
            logger, stream = _build_logger_and_stream(
                "test.orchestrator.books.dynamic")
            orchestrator = Orquestrador(
                validators=[],
                organizadores={
                    MediaType.BOOK: _RecordingOrganizer(processed),
                },
                classifier=_BooksClassifier(),
                scanner=_FakeScanner([book_1, book_2]),
                database=_FakeDatabase(),
                file_completion_validator=None,
                logger=logger,
            )

            await orchestrator.organizar_arquivos(
                diretorio_origem=base,
                validar_completude_arquivo=False,
                source_label="Books",
                progress_unit="books",
            )

            log_text = stream.getvalue()
            self.assertIn("Books breakdown: book=2", log_text)
            self.assertIn("Books progress: 2/2 processed books", log_text)
            self.assertIn("book(o/s/f)=2/0/0", log_text)
            self.assertNotIn("tracks(o/s/f)", log_text)
            self.assertNotIn("lyrics(o/s/f)", log_text)
            self.assertNotIn("artwork(o/s/f)=0/0/0", log_text)

    async def test_books_cycle_ignores_unknown_files_before_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            book = base / "Duna.epub"
            image = base / "_ Capa.jpg"
            for file_path in [book, image]:
                file_path.write_text("x", encoding="utf-8")

            processed = []
            logger, stream = _build_logger_and_stream(
                "test.orchestrator.books.prefilter.unknown")
            orchestrator = Orquestrador(
                validators=[],
                organizadores={
                    MediaType.BOOK: _RecordingOrganizer(processed),
                },
                classifier=_BooksClassifier(),
                scanner=_FakeScanner([book, image]),
                database=_FakeDatabase(),
                file_completion_validator=None,
                logger=logger,
            )

            await orchestrator.organizar_arquivos(
                diretorio_origem=base,
                validar_completude_arquivo=False,
                source_label="Books",
                progress_unit="books",
            )

            log_text = stream.getvalue()
            self.assertIn(
                "Books pre-filter: ignored=1 unsupported books", log_text)
            self.assertIn("Books progress: 1/1 processed books", log_text)
            self.assertIn(
                "Books organization completed: 1/1 organized | skipped=0 failed=0", log_text)

    async def test_progress_breakdown_is_dynamic_for_mixed_books_and_comics(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            book = base / "Duna.epub"
            comic = base / "Invencivel 001.cbr"
            for file_path in [book, comic]:
                file_path.write_text("x", encoding="utf-8")

            processed_books = []
            processed_comics = []
            logger, stream = _build_logger_and_stream(
                "test.orchestrator.mixed.books.comics")
            orchestrator = Orquestrador(
                validators=[],
                organizadores={
                    MediaType.BOOK: _RecordingOrganizer(processed_books),
                    MediaType.COMIC: _RecordingOrganizer(processed_comics),
                },
                classifier=_BooksAndComicsClassifier(),
                scanner=_FakeScanner([book, comic]),
                database=_FakeDatabase(),
                file_completion_validator=None,
                logger=logger,
            )

            await orchestrator.organizar_arquivos(
                diretorio_origem=base,
                validar_completude_arquivo=False,
                source_label="Library",
                progress_unit="files",
            )

            log_text = stream.getvalue()
            self.assertIn("Library breakdown:", log_text)
            self.assertIn("book=1", log_text)
            self.assertIn("comic=1", log_text)
            self.assertIn("book(o/s/f)=1/0/0", log_text)
            self.assertIn("comic(o/s/f)=1/0/0", log_text)
            self.assertNotIn("tracks(o/s/f)", log_text)

    async def test_deduplicates_semantic_lyrics_with_different_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder_a = base / "a"
            folder_b = base / "b"
            folder_a.mkdir(parents=True, exist_ok=True)
            folder_b.mkdir(parents=True, exist_ok=True)

            # Same song identity (same stem), different content.
            lyric_a = folder_a / "Hello - Adele.lrc"
            lyric_b = folder_b / "Hello - Adele.lrc"
            lyric_a.write_text("[00:01.00]Hello from A", encoding="utf-8")
            lyric_b.write_text(
                "[00:02.00]Different body from B", encoding="utf-8")

            # Candidate A has local paired audio, should be preferred by ranking.
            (folder_a / "Hello - Adele.flac").write_text("x", encoding="utf-8")

            processed = []
            organizer = _RecordingOrganizer(processed)
            organizer.dry_run = False

            orchestrator = Orquestrador(
                validators=[],
                organizadores={
                    MediaType.MUSIC: organizer,
                    MediaType.LYRICS: organizer,
                },
                classifier=_FakeClassifier(),
                scanner=_FakeScanner([lyric_a, lyric_b]),
                database=_FakeDatabase(),
                file_completion_validator=None,
            )

            await orchestrator.organizar_arquivos(
                diretorio_origem=base,
                validar_completude_arquivo=False,
                source_label="Music",
                progress_unit="tracks",
            )

            self.assertEqual(len(processed), 1)
            self.assertEqual(processed[0], "Hello - Adele.lrc")


if __name__ == "__main__":
    unittest.main()
