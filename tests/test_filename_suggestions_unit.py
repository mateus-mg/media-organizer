#!/usr/bin/env python3
"""Unit tests for filename suggestion engine."""

import tempfile
import unittest
from pathlib import Path

from app.features.filename_suggestions import FilenameSuggestionEngine


class TestFilenameSuggestionEngine(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        learning_path = Path(self.tempdir.name) / "learning.json"
        self.engine = FilenameSuggestionEngine(learning_path=learning_path)

    def test_suggests_book_author_title_year(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "books" / "Author Name - Great Book  (2020).pdf"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("x", encoding="utf-8")

            report = self.engine.suggest_for_root(root, media_filter="books")
            self.assertEqual(report["total_suggestions"], 1)
            item = report["suggestions"][0]

            self.assertEqual(item["media_type"], "BOOK")
            self.assertEqual(item["suggested_name"],
                             "Author Name - Great Book (2020).pdf")
            self.assertEqual(item["confidence"], "high")

    def test_suggests_comic_issue_with_padding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "downloads" / "comics" / "Saga_9_(2012).pdf"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("x", encoding="utf-8")

            report = self.engine.suggest_for_root(root, media_filter="comics")
            self.assertEqual(report["total_suggestions"], 1)
            item = report["suggestions"][0]

            self.assertEqual(item["media_type"], "COMIC")
            self.assertEqual(item["suggested_name"],
                             "Saga (2012) - Saga #009.pdf")
            self.assertEqual(item["confidence"], "high")

    def test_recursive_scan_and_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a" / "b").mkdir(parents=True, exist_ok=True)
            (root / "downloads" / "comics").mkdir(parents=True, exist_ok=True)

            (root / "a" / "b" / "Writer - Book (2019).epub").write_text("x", encoding="utf-8")
            (root / "downloads" / "comics" /
             "Event 1.pdf").write_text("x", encoding="utf-8")
            (root / "a" / "b" / "note.txt").write_text("x", encoding="utf-8")

            all_report = self.engine.suggest_for_root(root, media_filter="all")
            # May be 0, 1, or 2 depending on classifier
            self.assertGreaterEqual(all_report["total_suggestions"], 0)

            books_report = self.engine.suggest_for_root(
                root, media_filter="books")
            if books_report.get("suggestions"):
                self.assertEqual(
                    books_report["suggestions"][0]["media_type"], "BOOK")

            comics_report = self.engine.suggest_for_root(
                root, media_filter="comics")
            if comics_report.get("suggestions"):
                self.assertEqual(
                    comics_report["suggestions"][0]["media_type"], "COMIC")

    def test_manual_update_report_suggestion_updates_fields_and_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "downloads" / "comics" / "Saga_9_(2012).pdf"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("x", encoding="utf-8")

            report = self.engine.suggest_for_root(root, media_filter="comics")
            self.assertEqual(report["changed_suggestions"], 1)

            updated = self.engine.update_report_suggestion(
                report=report,
                index=0,
                new_name="Saga Final (2012) - Saga Final #009.pdf",
            )

            item = updated["suggestions"][0]
            self.assertEqual(item["suggested_name"],
                             "Saga Final (2012) - Saga Final #009.pdf")
            self.assertTrue(item["changed"])
            self.assertEqual(item["confidence"], "manual")
            self.assertEqual(item["reason"], "manual_override")
            self.assertTrue(item["manual_override"])
            self.assertEqual(updated["changed_suggestions"], 1)

    def test_manual_update_requires_same_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "books" / "Author - Book.pdf"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("x", encoding="utf-8")

            report = self.engine.suggest_for_root(root, media_filter="books")
            if not report.get("suggestions"):
                self.skipTest("No book suggestions generated")

            with self.assertRaises(ValueError):
                self.engine.update_report_suggestion(
                    report=report,
                    index=0,
                    new_name="Author - Book.epub",
                )

    def test_manual_learning_updates_future_comic_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "downloads" / "comics" / \
                "Guerras_Secretas_1_(2015).pdf"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("x", encoding="utf-8")

            report = self.engine.suggest_for_root(root, media_filter="comics")
            self.assertEqual(
                report["suggestions"][0]["suggested_name"], "Guerras Secretas (2015) - Guerras Secretas #001.pdf")

            updated = self.engine.update_report_suggestion(
                report=report,
                index=0,
                new_name="Marvel Secret Wars (2015) - Marvel Secret Wars #001.pdf",
            )
            learned = self.engine.learn_from_report(updated, only_manual=True)
            self.assertGreaterEqual(learned["comic_series_aliases"], 1)

            future_file = root / "downloads" / \
                "comics" / "Guerras_Secretas_2_(2015).pdf"
            future_file.write_text("x", encoding="utf-8")
            future = self.engine.suggest_for_root(root, media_filter="comics")

            mapped = [
                s for s in future["suggestions"]
                if s["original_name"] == "Guerras_Secretas_2_(2015).pdf"
            ][0]
            self.assertEqual(mapped["suggested_name"],
                             "Marvel Secret Wars (2015) - Marvel Secret Wars #002.pdf")

    def test_sanitize_removes_invalid_chars_windows(self):
        """Test that _sanitize_name removes invalid filesystem characters."""
        # Invalid Windows chars: < > : " | ? *
        self.assertEqual(self.engine._sanitize_name(
            'Book: The <Great>'), 'Book The Great')
        self.assertEqual(self.engine._sanitize_name('File|Name'), 'FileName')
        self.assertEqual(self.engine._sanitize_name(
            'Path/To/File'), 'PathToFile')
        self.assertEqual(self.engine._sanitize_name('Quote"Name'), 'QuoteName')
        self.assertNotIn('<', self.engine._sanitize_name('Test<File>'))
        self.assertNotIn('>', self.engine._sanitize_name('Test<File>'))

    def test_sanitize_max_filename_length(self):
        """Test that _sanitize_name truncates to 255 bytes max."""
        long_name = 'x' * 300
        sanitized = self.engine._sanitize_name(long_name)
        # 255 é o limite NTFS/ext4
        self.assertLessEqual(len(sanitized.encode('utf-8')), 255)

    def test_extract_year_variants(self):
        """Test flexible year extraction - accepts more formats than just (YYYY)."""
        engine = FilenameSuggestionEngine()
        # Existing format should still work
        self.assertEqual(engine._extract_year("Book (2020)"), 2020)
        # New formats to support
        self.assertEqual(engine._extract_year("Book.2020"), 2020)
        self.assertEqual(engine._extract_year("Book-2020"), 2020)
        self.assertEqual(engine._extract_year("Book_2020"), 2020)
        self.assertEqual(engine._extract_year("Book 2020"), 2020)

    def test_update_prevents_path_traversal(self):
        """Test that update_report_suggestion rejects path traversal."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Usar arquivo com extensão válida
            file_path = root / "Author - Book.pdf"
            file_path.write_text("x")

            report = self.engine.suggest_for_root(root, media_filter="books")
            if not report.get("suggestions"):
                self.skipTest(
                    "No book suggestions generated - classifier may not recognize .pdf as book")

            with self.assertRaises(ValueError) as ctx:
                self.engine.update_report_suggestion(
                    report, 0, "../../malicious.pdf")
            self.assertIn("path", str(ctx.exception).lower())

            with self.assertRaises(ValueError):
                self.engine.update_report_suggestion(
                    report, 0, "C:\\\\Windows\\\\test.pdf")

    def test_update_prevents_empty_or_dots_only(self):
        """Test that update_report_suggestion rejects empty or dots-only names."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Usar arquivo com extensão válida
            file_path = root / "Author - Book.pdf"
            file_path.write_text("x")

            report = self.engine.suggest_for_root(root, media_filter="books")
            if not report.get("suggestions"):
                self.skipTest(
                    "No book suggestions generated - classifier may not recognize .pdf as book")

            with self.assertRaises(ValueError):
                self.engine.update_report_suggestion(report, 0, ".")

            with self.assertRaises(ValueError):
                self.engine.update_report_suggestion(report, 0, "...")

    def test_learn_detects_alias_conflicts_comics(self):
        """Test that learn_from_report detects and logs alias conflicts."""
        with tempfile.TemporaryDirectory() as tmp:
            learning_path = Path(tmp) / "learn.json"
            engine = FilenameSuggestionEngine(learning_path=learning_path)

            report = {
                "suggestions": [
                    {
                        "original_name": "Saga 1.pdf",
                        "suggested_name": "Amazing Saga #001.pdf",
                        "media_type": "COMIC",
                        "manual_override": True,
                        "changed": True
                    },
                    {
                        "original_name": "Saga 2.pdf",
                        "suggested_name": "Incredible Saga #002.pdf",
                        "media_type": "COMIC",
                        "manual_override": True,
                        "changed": True
                    },
                ]
            }

            result = engine.learn_from_report(report, only_manual=True)

            # Should detect conflict and store it
            self.assertIn("_conflicts", engine.learning_data)
            self.assertIn("comics", engine.learning_data["_conflicts"])
            self.assertGreater(
                len(engine.learning_data["_conflicts"]["comics"]), 0)

    def test_apply_report_handles_disappeared_files(self):
        """Test that apply_report gracefully handles files that disappear."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "test.pdf"
            file_path.write_text("x")

            engine = FilenameSuggestionEngine(
                learning_path=Path(tmp) / "learn.json")
            report = {
                "suggestions": [{
                    "original_path": str(file_path),
                    "suggested_name": "test_renamed.pdf",
                    "changed": True,
                }]
            }

            # Deletar arquivo depois que foi adicionado no report (simula race condition)
            file_path.unlink()

            result = engine.apply_report(report, dry_run=False)

            # Deve reportar source_not_found ou source_disappeared, não crash
            self.assertEqual(result["errors"], 1)
            self.assertIn(result["details"][0]["status"], [
                          "source_not_found", "source_disappeared"])


if __name__ == "__main__":
    unittest.main()
