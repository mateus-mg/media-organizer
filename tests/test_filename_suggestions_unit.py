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
            file_path = root / "downloads" / "comics" / "Saga 9.pdf"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("x", encoding="utf-8")

            report = self.engine.suggest_for_root(root, media_filter="comics")
            self.assertEqual(report["total_suggestions"], 1)
            item = report["suggestions"][0]

            self.assertEqual(item["media_type"], "COMIC")
            self.assertEqual(item["suggested_name"], "Saga #009.pdf")
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
            self.assertEqual(all_report["total_suggestions"], 2)

            books_report = self.engine.suggest_for_root(
                root, media_filter="books")
            self.assertEqual(books_report["total_suggestions"], 1)
            self.assertEqual(
                books_report["suggestions"][0]["media_type"], "BOOK")

            comics_report = self.engine.suggest_for_root(
                root, media_filter="comics")
            self.assertEqual(comics_report["total_suggestions"], 1)
            self.assertEqual(
                comics_report["suggestions"][0]["media_type"], "COMIC")

    def test_manual_update_report_suggestion_updates_fields_and_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "downloads" / "comics" / "Saga 9.pdf"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("x", encoding="utf-8")

            report = self.engine.suggest_for_root(root, media_filter="comics")
            self.assertEqual(report["changed_suggestions"], 1)

            updated = self.engine.update_report_suggestion(
                report=report,
                index=0,
                new_name="Saga Final #009.pdf",
            )

            item = updated["suggestions"][0]
            self.assertEqual(item["suggested_name"], "Saga Final #009.pdf")
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

            with self.assertRaises(ValueError):
                self.engine.update_report_suggestion(
                    report=report,
                    index=0,
                    new_name="Author - Book.epub",
                )

    def test_manual_learning_updates_future_comic_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "downloads" / "comics" / "Guerras Secretas 1.pdf"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("x", encoding="utf-8")

            report = self.engine.suggest_for_root(root, media_filter="comics")
            self.assertEqual(
                report["suggestions"][0]["suggested_name"], "Guerras Secretas #001.pdf")

            updated = self.engine.update_report_suggestion(
                report=report,
                index=0,
                new_name="Marvel Secret Wars #001.pdf",
            )
            learned = self.engine.learn_from_report(updated, only_manual=True)
            self.assertGreaterEqual(learned["comic_series_aliases"], 1)

            future_file = root / "downloads" / "comics" / "Guerras Secretas 2.pdf"
            future_file.write_text("x", encoding="utf-8")
            future = self.engine.suggest_for_root(root, media_filter="comics")

            mapped = [
                s for s in future["suggestions"]
                if s["original_name"] == "Guerras Secretas 2.pdf"
            ][0]
            self.assertEqual(mapped["suggested_name"],
                             "Marvel Secret Wars #002.pdf")


if __name__ == "__main__":
    unittest.main()
