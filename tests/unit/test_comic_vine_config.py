#!/usr/bin/env python3
"""Unit tests for Comic Vine configuration properties."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.config import Config


class TestComicVineConfig(unittest.TestCase):
    def setUp(self):
        self.env = {
            "LIBRARY_PATH_MUSIC": "/tmp/lib/music",
            "LIBRARY_PATH_BOOKS": "/tmp/lib/books",
            "LIBRARY_PATH_COMICS": "/tmp/lib/comics",
            "DOWNLOAD_PATH_MUSIC": "/tmp/down/music",
            "DOWNLOAD_PATH_BOOKS": "/tmp/down/books",
            "DOWNLOAD_PATH_COMICS": "/tmp/down/comics",
        }

    def test_comic_vine_api_key_defaults_to_empty_string(self):
        with patch.dict(os.environ, self.env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_api_key, "")

    def test_comic_vine_api_key_strips_whitespace(self):
        env = {**self.env, "COMIC_VINE_API_KEY": "  abc123  "}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_api_key, "abc123")

    def test_comic_vine_enabled_returns_false_when_api_key_empty(self):
        with patch.dict(os.environ, self.env, clear=False):
            config = Config()
            self.assertFalse(config.comic_vine_enabled)

    def test_comic_vine_enabled_returns_true_when_api_key_set(self):
        env = {**self.env, "COMIC_VINE_API_KEY": "test_api_key"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertTrue(config.comic_vine_enabled)

    def test_comic_vine_api_delay_seconds_defaults_to_1_0(self):
        with patch.dict(os.environ, self.env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_api_delay_seconds, 1.0)

    def test_comic_vine_api_delay_seconds_respects_env_value(self):
        env = {**self.env, "COMIC_VINE_API_DELAY_SECONDS": "2.5"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_api_delay_seconds, 2.5)

    def test_comic_vine_api_delay_seconds_enforces_minimum_0_5(self):
        env = {**self.env, "COMIC_VINE_API_DELAY_SECONDS": "0.1"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_api_delay_seconds, 0.5)

    def test_comic_vine_api_delay_seconds_defaults_on_invalid_value(self):
        env = {**self.env, "COMIC_VINE_API_DELAY_SECONDS": "invalid"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_api_delay_seconds, 1.0)

    def test_comic_vine_translate_series_names_defaults_to_true(self):
        with patch.dict(os.environ, self.env, clear=False):
            config = Config()
            self.assertTrue(config.comic_vine_translate_series_names)

    def test_comic_vine_translate_series_names_respects_false(self):
        env = {**self.env, "COMIC_VINE_TRANSLATE_SERIES_NAMES": "false"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertFalse(config.comic_vine_translate_series_names)

    def test_comic_vine_timeout_seconds_defaults_to_15_0(self):
        with patch.dict(os.environ, self.env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_timeout_seconds, 15.0)

    def test_comic_vine_timeout_seconds_respects_env_value(self):
        env = {**self.env, "COMIC_VINE_TIMEOUT_SECONDS": "30.0"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_timeout_seconds, 30.0)

    def test_comic_vine_timeout_seconds_enforces_minimum_5_0(self):
        env = {**self.env, "COMIC_VINE_TIMEOUT_SECONDS": "2.0"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_timeout_seconds, 5.0)

    def test_comic_vine_timeout_seconds_defaults_on_invalid_value(self):
        env = {**self.env, "COMIC_VINE_TIMEOUT_SECONDS": "invalid"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_timeout_seconds, 15.0)

    def test_comic_vine_min_match_score_defaults_to_75(self):
        with patch.dict(os.environ, self.env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_min_match_score, 75)

    def test_comic_vine_min_match_score_respects_env_value(self):
        env = {**self.env, "COMIC_VINE_MIN_MATCH_SCORE": "85"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_min_match_score, 85)

    def test_comic_vine_min_match_score_enforces_minimum_0(self):
        env = {**self.env, "COMIC_VINE_MIN_MATCH_SCORE": "-10"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_min_match_score, 0)

    def test_comic_vine_min_match_score_defaults_on_invalid_value(self):
        env = {**self.env, "COMIC_VINE_MIN_MATCH_SCORE": "invalid"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertEqual(config.comic_vine_min_match_score, 75)

    def test_comic_vine_download_covers_defaults_to_true(self):
        with patch.dict(os.environ, self.env, clear=False):
            config = Config()
            self.assertTrue(config.comic_vine_download_covers)

    def test_comic_vine_download_covers_respects_false(self):
        env = {**self.env, "COMIC_VINE_DOWNLOAD_COVERS": "false"}
        with patch.dict(os.environ, env, clear=False):
            config = Config()
            self.assertFalse(config.comic_vine_download_covers)


if __name__ == "__main__":
    unittest.main()
