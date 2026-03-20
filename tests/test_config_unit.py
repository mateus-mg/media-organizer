#!/usr/bin/env python3
"""Unit tests for configuration handling."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import Config


class TestConfig(unittest.TestCase):
    def test_is_valid_with_minimum_required_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            env = {
                "DATABASE_PATH": str(base / "organization.json"),
                "LIBRARY_PATH_MUSIC": str(base / "lib" / "music"),
                "LIBRARY_PATH_BOOKS": str(base / "lib" / "books"),
                "LIBRARY_PATH_COMICS": str(base / "lib" / "comics"),
                "DOWNLOAD_PATH_MUSIC": str(base / "down" / "music"),
                "DOWNLOAD_PATH_BOOKS": str(base / "down" / "books"),
                "DOWNLOAD_PATH_COMICS": str(base / "down" / "comics"),
            }
            with patch.dict(os.environ, env, clear=False):
                config = Config()
                valid, errors = config.is_valid()

            self.assertTrue(valid)
            self.assertEqual(errors, [])

    def test_conflict_strategy_falls_back_to_skip(self):
        with patch.dict(os.environ, {"CONFLICT_STRATEGY": "invalid"}, clear=False):
            config = Config()
            self.assertEqual(config.conflict_strategy, "skip")

    def test_download_and_library_maps_expose_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            env = {
                "LIBRARY_PATH_MUSIC": str(base / "lib" / "music"),
                "LIBRARY_PATH_BOOKS": str(base / "lib" / "books"),
                "LIBRARY_PATH_COMICS": str(base / "lib" / "comics"),
                "DOWNLOAD_PATH_MUSIC": str(base / "down" / "music"),
                "DOWNLOAD_PATH_BOOKS": str(base / "down" / "books"),
                "DOWNLOAD_PATH_COMICS": str(base / "down" / "comics"),
            }
            with patch.dict(os.environ, env, clear=False):
                config = Config()
                downloads = config.get_all_download_paths()
                libraries = config.get_all_library_paths()

            self.assertEqual(set(downloads.keys()), {
                             "music", "books", "comics"})
            self.assertEqual(set(libraries.keys()), {
                             "music", "books", "comics"})


if __name__ == "__main__":
    unittest.main()
