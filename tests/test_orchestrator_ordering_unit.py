#!/usr/bin/env python3
"""Unit tests for Orquestrador processing order."""

import tempfile
import unittest
from pathlib import Path

from app.core import MediaType, Orquestrador, OrganizationResult


class _FakeScanner:
    def __init__(self, files):
        self._files = files

    def escanear_diretorio(self, _diretorio):
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


class _RecordingOrganizer:
    def __init__(self, sink):
        self.sink = sink

    def pode_processar(self, _file_path: Path) -> bool:
        return True

    async def organizar(self, file_path: Path) -> OrganizationResult:
        self.sink.append(file_path.name)
        return OrganizationResult(success=True, skipped=False, organized_path=file_path)


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
