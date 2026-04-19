#!/usr/bin/env python3
"""Unit tests for file detection and scanning."""

import tempfile
import unittest
from pathlib import Path

from app.core import MediaType
from app.core.detection import FileScanner, MediaClassifier


class TestMediaClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = MediaClassifier()

    def test_classifies_supported_types(self):
        self.assertEqual(self.classifier.classificar_tipo_midia(
            Path("song.mp3")), MediaType.MUSIC)
        self.assertEqual(self.classifier.classificar_tipo_midia(
            Path("song.aac")), MediaType.MUSIC)
        self.assertEqual(self.classifier.classificar_tipo_midia(
            Path("song.wma")), MediaType.MUSIC)
        self.assertEqual(self.classifier.classificar_tipo_midia(
            Path("lyrics.lrc")), MediaType.LYRICS)
        self.assertEqual(self.classifier.classificar_tipo_midia(
            Path("book.epub")), MediaType.BOOK)
        self.assertEqual(self.classifier.classificar_tipo_midia(
            Path("downloads/comics/Batman #001.pdf")), MediaType.COMIC)
        self.assertEqual(self.classifier.classificar_tipo_midia(
            Path("downloads/books/Batman #001.pdf")), MediaType.BOOK)
        self.assertEqual(self.classifier.classificar_tipo_midia(
            Path("comic.cbz")), MediaType.COMIC)
        self.assertEqual(self.classifier.classificar_tipo_midia(
            Path("unknown.bin")), MediaType.UNKNOWN)

    def test_extracts_book_metadata_from_filename(self):
        metadata = self.classifier.extrair_metadados(
            Path("Author Name - Great Book (2024).epub"))

        self.assertEqual(metadata.media_type, MediaType.BOOK)
        self.assertEqual(metadata.author, "Author Name")
        self.assertEqual(metadata.title, "Great Book")
        self.assertEqual(metadata.year, 2024)

    def test_classifies_artwork_only_for_music_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            music_image = root / "downloads" / "musics" / "Album" / "cover.jpg"
            music_image.parent.mkdir(parents=True, exist_ok=True)
            music_image.write_text("x", encoding="utf-8")

            books_image = root / "downloads" / "books" / "Book" / "cover.jpg"
            books_image.parent.mkdir(parents=True, exist_ok=True)
            books_image.write_text("x", encoding="utf-8")

            comics_image = root / "downloads" / "comics" / "Series" / "cover.jpg"
            comics_image.parent.mkdir(parents=True, exist_ok=True)
            comics_image.write_text("x", encoding="utf-8")

            self.assertEqual(
                self.classifier.classificar_tipo_midia(music_image),
                MediaType.ARTWORK,
            )
            self.assertEqual(
                self.classifier.classificar_tipo_midia(books_image),
                MediaType.UNKNOWN,
            )
            self.assertEqual(
                self.classifier.classificar_tipo_midia(comics_image),
                MediaType.UNKNOWN,
            )

    def test_classifies_artwork_when_local_audio_pair_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cover = root / "misc" / "song.jpg"
            cover.parent.mkdir(parents=True, exist_ok=True)
            cover.write_text("x", encoding="utf-8")
            cover.with_suffix(".mp3").write_text("x", encoding="utf-8")

            self.assertEqual(
                self.classifier.classificar_tipo_midia(cover),
                MediaType.ARTWORK,
            )


class TestFileScanner(unittest.TestCase):
    def test_scan_and_filter(self):
        scanner = FileScanner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid_music = root / "track.mp3"
            valid_music.write_text("ok", encoding="utf-8")

            uppercase_music = root / "TRACK.WMA"
            uppercase_music.write_text("ok", encoding="utf-8")

            lyrics = root / "track.lrc"
            lyrics.write_text("[00:01]line", encoding="utf-8")

            hidden = root / ".hidden.mp3"
            hidden.write_text("hidden", encoding="utf-8")

            incomplete = root / "unfinished.part"
            incomplete.write_text("partial", encoding="utf-8")

            junk = root / "BLUDV.MP4"
            junk.write_text("junk", encoding="utf-8")

            all_files = scanner.escanear_diretorio(root)
            filtered = scanner.filtrar_arquivos_para_organizacao(all_files)

            self.assertIn(valid_music, filtered)
            self.assertIn(uppercase_music, filtered)
            self.assertIn(lyrics, filtered)
            self.assertNotIn(hidden, filtered)
            self.assertNotIn(incomplete, filtered)


if __name__ == "__main__":
    unittest.main()
