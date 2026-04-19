"""Unit tests for Navidrome CLI commands in app.main."""

import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from app.main import cli


class TestMainNavidromeCli(unittest.TestCase):
    @patch("app.main.PlaylistService")
    @patch("app.main.Config")
    def test_navidrome_sync_simple_defaults_to_incremental_mode(self, config_cls, service_cls):
        config = MagicMock()
        config.navidrome_enabled = True
        config_cls.return_value = config

        service = MagicMock()
        service.sync_simple_playlist_from_organization.return_value = {
            "matched_records": 2,
            "resolved_count": 2,
            "unresolved_count": 0,
            "unresolved_paths": [],
            "preview": {
                "to_add_count": 0,
                "to_remove_count": 0,
                "existing_song_count": 2,
                "target_song_count": 2,
            },
        }
        service_cls.return_value = service

        runner = CliRunner()
        result = runner.invoke(
            cli, ["navidrome-sync-simple", "--name", "Gym Mix"])

        self.assertEqual(result.exit_code, 0)
        service.sync_simple_playlist_from_organization.assert_called_once_with(
            name="Gym Mix",
            public=False,
            artist_filter="",
            genre_filter="",
            album_filter="",
            limit=0,
            mode="incremental",
            preview_only=False,
        )
        self.assertIn("Simple playlist synced (incremental)", result.output)

    @patch("app.main.PlaylistService")
    @patch("app.main.Config")
    def test_navidrome_sync_simple_recreate_mode(self, config_cls, service_cls):
        config = MagicMock()
        config.navidrome_enabled = True
        config_cls.return_value = config

        service = MagicMock()
        service.sync_simple_playlist_from_organization.return_value = {
            "matched_records": 1,
            "resolved_count": 1,
            "unresolved_count": 0,
            "unresolved_paths": [],
            "preview": {
                "to_add_count": 1,
                "to_remove_count": 0,
                "existing_song_count": 0,
                "target_song_count": 1,
            },
        }
        service_cls.return_value = service

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "navidrome-sync-simple",
                "--name",
                "Road Trip",
                "--artist",
                "artist",
                "--genre",
                "rock",
                "--album",
                "hits",
                "--limit",
                "25",
                "--public",
                "--mode",
                "recreate",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        service.sync_simple_playlist_from_organization.assert_called_once_with(
            name="Road Trip",
            public=True,
            artist_filter="artist",
            genre_filter="rock",
            album_filter="hits",
            limit=25,
            mode="recreate",
            preview_only=False,
        )
        self.assertIn("Simple playlist synced (recreate)", result.output)

    @patch("app.main.PlaylistService")
    @patch("app.main.Config")
    def test_navidrome_sync_simple_preview_diff(self, config_cls, service_cls):
        config = MagicMock()
        config.navidrome_enabled = True
        config_cls.return_value = config

        service = MagicMock()
        service.sync_simple_playlist_from_organization.return_value = {
            "matched_records": 3,
            "resolved_count": 2,
            "unresolved_count": 1,
            "unresolved_paths": ["/x/y/z.flac"],
            "preview": {
                "to_add_count": 2,
                "to_remove_count": 1,
                "existing_song_count": 4,
                "target_song_count": 5,
                "to_add_song_ids": ["song-a", "song-b"],
                "to_remove_song_ids": ["song-old"],
            },
        }
        service_cls.return_value = service

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["navidrome-sync-simple", "--name", "Gym Mix", "--preview-diff"],
        )

        self.assertEqual(result.exit_code, 0)
        service.sync_simple_playlist_from_organization.assert_called_once_with(
            name="Gym Mix",
            public=False,
            artist_filter="",
            genre_filter="",
            album_filter="",
            limit=0,
            mode="incremental",
            preview_only=True,
        )
        self.assertIn(
            "Simple playlist preview generated (incremental)", result.output)
        self.assertIn(
            "Diff: add=2 | remove=1 | existing=4 | target=5", result.output)
        self.assertIn(
            "Resumo: adicionaria 2 música(s) e removeria 1 música(s)", result.output)
        self.assertIn("Sample IDs to add:", result.output)
        self.assertIn("+ song-a", result.output)
        self.assertIn("Sample IDs to remove:", result.output)
        self.assertIn("- song-old", result.output)

    @patch("app.main.PlaylistService")
    @patch("app.main.Config")
    def test_navidrome_sync_simple_disabled(self, config_cls, service_cls):
        config = MagicMock()
        config.navidrome_enabled = False
        config_cls.return_value = config

        runner = CliRunner()
        result = runner.invoke(cli, ["navidrome-sync-simple", "--name", "Any"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("NAVIDROME_ENABLED=false", result.output)
        service_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
