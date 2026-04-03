#!/usr/bin/env python3
"""Unit tests for genre guard rules and auto-feeding."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.features.genre_guard import core as genre_guard


class TestGenreGuard(unittest.TestCase):
    def setUp(self):
        genre_guard._CATALOG_CACHE = None
        genre_guard._SUSPECT_CACHE = None
        self._env_backup = dict(os.environ)
        for key in [
            "GENRE_HEURISTICS_PROFILE",
            "GENRE_EDITORIAL_OVERLOAD_HITS",
            "GENRE_EDITORIAL_OVERLOAD_MAX_MUSICAL_HITS",
            "GENRE_EDITORIAL_OVERLOAD_MIN_KEYWORD_HITS",
            "GENRE_EDITORIAL_BIAS_MIN_DELTA",
            "GENRE_EDITORIAL_BIAS_MAX_CONFIDENCE",
            "GENRE_MUSICAL_CONFIDENT_MIN_KEYWORD_HITS",
            "GENRE_MUSICAL_CONFIDENT_MIN_SCORE",
        ]:
            os.environ.pop(key, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_bootstrap_invalid_catalog_from_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            csv_path = data_dir / "downloads_genres_invalid.csv"
            csv_path.write_text(
                "genre,count,reason,example_file\n"
                "Billboard Hot 100,4,unknown,/tmp/a.flac\n",
                encoding="utf-8",
            )

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                catalog = genre_guard.load_invalid_catalog(force_reload=True)

            self.assertIn("billboard hot 100", [
                          x.lower() for x in catalog.get("exact", [])])

    def test_folder_name_is_invalid_genre(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                genre_guard.load_invalid_catalog(force_reload=True)
                file_path = Path(tmp) / "downloads" / "musics" / \
                    "Dance Hits 2010s" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                self.assertTrue(genre_guard.is_invalid_genre_value(
                    file_path, "Dance Hits 2010s"))

    def test_suspicious_promotes_to_invalid_after_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                genre_guard.load_invalid_catalog(force_reload=True)
                suspect = genre_guard.load_suspect_catalog(force_reload=True)
                suspect["threshold_for_auto_add"] = 2
                genre_guard.save_suspect_catalog(suspect)

                file_path = Path(tmp) / "downloads" / \
                    "musics" / "x" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                promoted1, _ = genre_guard.track_suspicious_genre(
                    "Billboard Hot 100", file_path)
                promoted2, _ = genre_guard.track_suspicious_genre(
                    "Billboard Hot 100", file_path)

                self.assertFalse(promoted1)
                self.assertTrue(promoted2)

                catalog = genre_guard.load_invalid_catalog(force_reload=True)
                self.assertIn("billboard hot 100", [
                              x.lower() for x in catalog.get("exact", [])])

    def test_sanitize_genre_values_removes_invalid_and_keeps_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                catalog = genre_guard.load_invalid_catalog(force_reload=True)
                exact = set(catalog.get("exact", []))
                exact.add("english")
                catalog["exact"] = sorted(exact)
                genre_guard.save_invalid_catalog(catalog)

                file_path = Path(tmp) / "downloads" / "musics" / \
                    "Dance Hits 2010s" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                valid, removed = genre_guard.sanitize_genre_values(
                    file_path,
                    ["Dance Hits 2010s", "English", "Pop"],
                )

                self.assertEqual(valid, ["Pop"])
                self.assertIn("dance hits 2010s", [x.lower() for x in removed])
                self.assertIn("English", removed)

    def test_whitelisted_subgenre_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                genre_guard.load_invalid_catalog(force_reload=True)
                file_path = Path(tmp) / "downloads" / \
                    "musics" / "x" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                valid, removed = genre_guard.sanitize_genre_values(
                    file_path,
                    ["Dutch House", "Pop"],
                )

                self.assertIn("Dutch House", valid)
                self.assertIn("Pop", valid)
                self.assertEqual(removed, [])

    def test_canonical_normalization_treats_hyphen_and_space_as_same_genre(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                genre_guard.load_invalid_catalog(force_reload=True)

                file_path = Path(tmp) / "downloads" / \
                    "musics" / "x" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                valid, removed = genre_guard.sanitize_genre_values(
                    file_path,
                    ["Blues Rock", "Blues-Rock", "Pop"],
                )

                self.assertIn("Pop", valid)
                self.assertEqual(
                    len([g for g in valid if "blues" in g.lower() and "rock" in g.lower()]), 1)
                self.assertEqual(removed, [])

    def test_invalid_exact_match_works_with_separator_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                catalog = genre_guard.load_invalid_catalog(force_reload=True)
                exact = set(catalog.get("exact", []))
                exact.add("hard heavy")
                catalog["exact"] = sorted(exact)
                genre_guard.save_invalid_catalog(catalog)

                file_path = Path(tmp) / "downloads" / \
                    "musics" / "x" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                valid, removed = genre_guard.sanitize_genre_values(
                    file_path,
                    ["Hard & Heavy", "Pop"],
                )

                self.assertEqual(valid, ["Pop"])
                self.assertEqual(len(removed), 1)
                self.assertIn("hard", removed[0].lower())
                self.assertIn("heavy", removed[0].lower())

    def test_canonical_normalization_applies_to_any_separator_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                catalog = genre_guard.load_invalid_catalog(force_reload=True)
                exact = set(catalog.get("exact", []))
                exact.add("pop & chart")
                catalog["exact"] = sorted(exact)
                genre_guard.save_invalid_catalog(catalog)

                file_path = Path(tmp) / "downloads" / \
                    "musics" / "x" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                valid, removed = genre_guard.sanitize_genre_values(
                    file_path,
                    ["Pop & Chart", "Pop/Chart", "Pop-Chart", "Pop_Chart",
                        "Pop + Chart", "Drum-and-Bass", "Drum & Bass"],
                )

                self.assertTrue(
                    any("pop" in x.lower() and "chart" in x.lower() for x in removed))
                self.assertEqual(
                    len([x for x in removed if "pop" in x.lower() and "chart" in x.lower()]), 1)
                self.assertEqual(
                    len([x for x in valid if "drum" in x.lower() and "bass" in x.lower()]), 1)

    def test_token_editorial_overload_removes_noise_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                genre_guard.load_invalid_catalog(force_reload=True)

                file_path = Path(tmp) / "downloads" / \
                    "musics" / "x" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                valid, removed = genre_guard.sanitize_genre_values(
                    file_path,
                    ["Mood Booster Vibes", "Pop"],
                )

                self.assertEqual(valid, ["Pop"])
                self.assertEqual(len(removed), 1)
                self.assertIn("mood", removed[0].lower())

    def test_token_confidence_keeps_complex_musical_genre(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                genre_guard.load_invalid_catalog(force_reload=True)

                file_path = Path(tmp) / "downloads" / \
                    "musics" / "x" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                valid, removed = genre_guard.sanitize_genre_values(
                    file_path,
                    ["Neo Psychedelic Rock"],
                )

                self.assertEqual(len(valid), 1)
                self.assertEqual(removed, [])

    def test_heuristic_thresholds_are_configurable_via_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                catalog = genre_guard.load_invalid_catalog(force_reload=True)
                catalog["heuristics"] = {
                    "editorial_overload_hits": 10,
                    "editorial_overload_max_musical_hits": 0,
                    "editorial_overload_min_keyword_hits": 0,
                    "editorial_bias_min_delta": 1,
                    "editorial_bias_max_confidence": 0,
                    "musical_confident_min_keyword_hits": 1,
                    "musical_confident_min_score": 2,
                }
                genre_guard.save_invalid_catalog(catalog)

                file_path = Path(tmp) / "downloads" / \
                    "musics" / "x" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                valid, removed = genre_guard.sanitize_genre_values(
                    file_path,
                    ["Mood Booster Vibes"],
                )

                self.assertEqual(removed, [])
                self.assertEqual(len(valid), 1)

    def test_env_profile_strict_increases_editorial_removal(self):
        os.environ["GENRE_HEURISTICS_PROFILE"] = "strict"

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                genre_guard.load_invalid_catalog(force_reload=True)

                file_path = Path(tmp) / "downloads" / \
                    "musics" / "x" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                valid, removed = genre_guard.sanitize_genre_values(
                    file_path,
                    ["Mood Vibes", "Pop"],
                )

                self.assertEqual(valid, ["Pop"])
                self.assertEqual(len(removed), 1)

    def test_env_override_can_relax_editorial_overload(self):
        os.environ["GENRE_HEURISTICS_PROFILE"] = "strict"
        os.environ["GENRE_EDITORIAL_OVERLOAD_HITS"] = "10"

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                genre_guard.load_invalid_catalog(force_reload=True)

                file_path = Path(tmp) / "downloads" / \
                    "musics" / "x" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                valid, removed = genre_guard.sanitize_genre_values(
                    file_path,
                    ["Mood Vibes"],
                )

                self.assertEqual(removed, [])
                self.assertEqual(len(valid), 1)

    def test_unicode_normalization_matches_accent_variants_with_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                catalog = genre_guard.load_invalid_catalog(force_reload=True)
                exact = set(catalog.get("exact", []))
                exact.add("electronique")
                catalog["exact"] = sorted(exact)
                genre_guard.save_invalid_catalog(catalog)

                file_path = Path(tmp) / "downloads" / \
                    "musics" / "x" / "song.flac"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("dummy", encoding="utf-8")

                valid, removed = genre_guard.sanitize_genre_values(
                    file_path,
                    ["Électronique"],
                )

                self.assertEqual(valid, [])
                normalized_removed = [x.lower().replace("é", "e")
                                      for x in removed]
                self.assertIn("electronique", normalized_removed)

    def test_missing_invalid_catalog_is_restored_from_latest_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            backup_dir = data_dir / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_path = backup_dir / "invalid_music_genres_2026-03-23_10-00-00.json"
            backup_path.write_text(
                '{"version":1,"updated_at":"x","exact":["billboard hot 100"],"regex":[],"auto_added":{}}',
                encoding="utf-8",
            )

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                catalog = genre_guard.load_invalid_catalog(force_reload=True)

                self.assertIn("billboard hot 100", [
                              x.lower() for x in catalog.get("exact", [])])
                self.assertTrue(
                    (data_dir / "invalid_music_genres.json").exists())

    def test_missing_suspect_catalog_is_restored_from_latest_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            backup_dir = data_dir / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_path = backup_dir / "suspect_music_genres_2026-03-23_10-00-00.json"
            backup_path.write_text(
                '{"version":1,"updated_at":"x","threshold_for_auto_add":2,"items":{}}',
                encoding="utf-8",
            )

            with patch("app.features.genre_guard.core._data_dir", return_value=data_dir):
                catalog = genre_guard.load_suspect_catalog(force_reload=True)

                self.assertEqual(catalog.get("threshold_for_auto_add"), 2)
                self.assertTrue(
                    (data_dir / "suspect_music_genres.json").exists())


if __name__ == "__main__":
    unittest.main()
