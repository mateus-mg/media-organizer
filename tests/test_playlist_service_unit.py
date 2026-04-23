"""Unit tests for playlist service."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.features.smart_playlists import SmartPlaylistBuilder
from app.services.playlists import PlaylistService


class TestPlaylistService(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

        self.config = MagicMock()
        self.config.navidrome_playlists_state_path = self.tmp_path / "playlists_state.json"
        self.config.navidrome_smart_playlist_dir = self.tmp_path / "smart"
        self.config.navidrome_smart_playlist_auto_scan = False

    def tearDown(self):
        self.tmp_dir.cleanup()

    @patch("app.services.playlists.NavidromeClient")
    def test_create_simple_playlist_persists_local(self, client_cls):
        client = MagicMock()
        client.create_playlist.return_value = {"id": "777", "name": "Gym"}
        client_cls.return_value = client

        service = PlaylistService(self.config)
        created = service.create_simple_playlist(
            name="Gym", song_ids_csv="11,22", public=True)

        self.assertEqual(created["kind"], "simple")
        self.assertEqual(created["remote_id"], "777")
        self.assertEqual(created["song_ids"], ["11", "22"])

    def test_create_and_update_smart_playlist(self):
        service = PlaylistService(self.config)
        created = service.create_smart_playlist(
            name="Smart EDM",
            query="genre:edm",
            public=False,
            comment="initial",
        )

        self.assertEqual(created["kind"], "smart")
        nsp_path = Path(created["nsp_path"])
        self.assertTrue(nsp_path.exists())

        updated = service.update_smart_playlist(
            local_id=created["local_id"],
            query="genre:house",
            comment="updated",
            public=True,
        )

        self.assertEqual(updated["query"], "genre:house")
        self.assertTrue(updated["public"])

    @patch("app.services.playlists.NavidromeClient")
    def test_sync_simple_playlist_from_organization(self, client_cls):
        organization_payload = {
            "media": {
                "1": {
                    "organized_path": "/library/Artist/Album/01 - Song A.flac",
                    "metadata": {
                        "media_type": "music",
                        "artist": "Artist",
                        "title": "Song A",
                        "album": "Album",
                        "genres": ["Pop"],
                    },
                },
                "2": {
                    "organized_path": "/library/Other/Album/02 - Song B.flac",
                    "metadata": {
                        "media_type": "music",
                        "artist": "Other",
                        "title": "Song B",
                        "album": "Album",
                        "genres": ["Rock"],
                    },
                },
            }
        }
        db_path = self.tmp_path / "organization.json"
        db_path.write_text(__import__("json").dumps(
            organization_payload), encoding="utf-8")
        self.config.database_path = db_path

        client = MagicMock()
        client.get_playlists.return_value = []
        client.search_songs.return_value = [
            {
                "id": "song-id-1",
                "title": "Song A",
                "artist": "Artist",
                "album": "Album",
                "path": "Artist/Album/01 - Song A.flac",
            }
        ]
        client.create_playlist.return_value = {"id": "remote-123"}
        client_cls.return_value = client

        service = PlaylistService(self.config)
        report = service.sync_simple_playlist_from_organization(
            name="My Synced Playlist",
            artist_filter="artist",
        )

        self.assertEqual(report["matched_records"], 1)
        self.assertEqual(report["resolved_count"], 1)
        self.assertEqual(report["unresolved_count"], 0)
        self.assertEqual(report["playlist"]["remote_id"], "remote-123")
        self.assertFalse(report["preview"]["enabled"])

    @patch("app.services.playlists.NavidromeClient")
    def test_sync_simple_playlist_incremental_updates_existing(self, client_cls):
        organization_payload = {
            "media": {
                "1": {
                    "organized_path": "/library/Artist/Album/01 - Song A.flac",
                    "metadata": {
                        "media_type": "music",
                        "artist": "Artist",
                        "title": "Song A",
                        "album": "Album",
                    },
                },
                "2": {
                    "organized_path": "/library/Artist/Album/02 - Song B.flac",
                    "metadata": {
                        "media_type": "music",
                        "artist": "Artist",
                        "title": "Song B",
                        "album": "Album",
                    },
                },
            }
        }
        db_path = self.tmp_path / "organization.json"
        db_path.write_text(__import__("json").dumps(
            organization_payload), encoding="utf-8")
        self.config.database_path = db_path

        client = MagicMock()
        client.get_playlists.return_value = [
            {"id": "remote-123", "name": "My Synced Playlist"}]
        client.search_songs.side_effect = [
            [{"id": "song-id-1", "title": "Song A",
                "artist": "Artist", "album": "Album"}],
            [{"id": "song-id-2", "title": "Song B",
                "artist": "Artist", "album": "Album"}],
        ]
        client.get_playlist.side_effect = [
            {"id": "remote-123",
                "entry": [{"id": "song-id-1"}, {"id": "song-old"}]},
            {"id": "remote-123",
                "entry": [{"id": "song-id-1"}, {"id": "song-id-2"}]},
        ]
        client_cls.return_value = client

        service = PlaylistService(self.config)
        report = service.sync_simple_playlist_from_organization(
            name="My Synced Playlist",
            mode="incremental",
            public=True,
        )

        client.update_playlist.assert_called_once_with(
            "remote-123",
            public=True,
            song_ids_to_add=["song-id-2"],
            song_indexes_to_remove=[1],
        )
        client.create_playlist.assert_not_called()
        client.delete_playlist.assert_not_called()
        self.assertEqual(report["playlist"]["remote_id"], "remote-123")
        self.assertEqual(report["playlist"].get("sync_mode"), "incremental")

    @patch("app.services.playlists.NavidromeClient")
    def test_sync_simple_playlist_invalid_mode_raises(self, client_cls):
        client_cls.return_value = MagicMock()
        self.config.database_path = self.tmp_path / "missing.json"

        service = PlaylistService(self.config)
        with self.assertRaises(ValueError):
            service.sync_simple_playlist_from_organization(
                name="My Synced Playlist",
                mode="invalid-mode",
            )

    @patch("app.services.playlists.NavidromeClient")
    def test_sync_simple_playlist_preview_does_not_apply_or_persist(self, client_cls):
        organization_payload = {
            "media": {
                "1": {
                    "organized_path": "/library/Artist/Album/01 - Song A.flac",
                    "metadata": {
                        "media_type": "music",
                        "artist": "Artist",
                        "title": "Song A",
                        "album": "Album",
                    },
                },
                "2": {
                    "organized_path": "/library/Artist/Album/02 - Song B.flac",
                    "metadata": {
                        "media_type": "music",
                        "artist": "Artist",
                        "title": "Song B",
                        "album": "Album",
                    },
                },
            }
        }
        db_path = self.tmp_path / "organization.json"
        db_path.write_text(__import__("json").dumps(
            organization_payload), encoding="utf-8")
        self.config.database_path = db_path

        client = MagicMock()
        client.get_playlists.return_value = [
            {"id": "remote-123", "name": "My Synced Playlist"}]
        client.search_songs.side_effect = [
            [{"id": "song-id-1", "title": "Song A",
                "artist": "Artist", "album": "Album"}],
            [{"id": "song-id-2", "title": "Song B",
                "artist": "Artist", "album": "Album"}],
        ]
        client.get_playlist.return_value = {
            "id": "remote-123",
            "entry": [{"id": "song-id-1"}, {"id": "song-old"}],
        }
        client_cls.return_value = client

        service = PlaylistService(self.config)
        report = service.sync_simple_playlist_from_organization(
            name="My Synced Playlist",
            mode="incremental",
            preview_only=True,
            public=True,
        )

        client.update_playlist.assert_not_called()
        client.create_playlist.assert_not_called()
        client.delete_playlist.assert_not_called()
        self.assertIsNone(report["playlist"])
        self.assertTrue(report["preview"]["enabled"])
        self.assertEqual(report["preview"]["to_add_count"], 1)
        self.assertEqual(report["preview"]["to_remove_count"], 1)
        self.assertEqual(service.list_local_playlists(kind="simple"), [])

    def test_create_smart_playlist_with_builder(self):
        service = PlaylistService(self.config)
        builder = SmartPlaylistBuilder("Builder Test")
        builder.all_of(
            builder.field("genre").contains("rock"),
            builder.field("year").gt(2020),
        ).limit(30)
        created = service.create_smart_playlist(name="Builder Test", builder=builder)
        self.assertEqual(created["kind"], "smart")
        nsp_path = Path(created["nsp_path"])
        payload = json.loads(nsp_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["limit"], 30)
        self.assertIn("all", payload)

    def test_create_smart_playlist_with_query_string(self):
        service = PlaylistService(self.config)
        created = service.create_smart_playlist(
            name="Query Test", query="genre:rock year:gt:2020", limit=25)
        self.assertEqual(created["kind"], "smart")
        nsp_path = Path(created["nsp_path"])
        payload = json.loads(nsp_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["limit"], 25)
        self.assertEqual(payload["all"][0], {"contains": {"genre": "rock"}})

    def test_create_smart_playlist_with_sort_and_order(self):
        service = PlaylistService(self.config)
        created = service.create_smart_playlist(
            name="Sorted", query="genre:rock", sort="-rating,title", order="asc")
        nsp_path = Path(created["nsp_path"])
        payload = json.loads(nsp_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["sort"], "-rating,title")
        self.assertEqual(payload["order"], "asc")

    def test_create_smart_playlist_with_nsp_definition(self):
        service = PlaylistService(self.config)
        created = service.create_smart_playlist(
            name="NSP Test",
            nsp_definition={
                "all": [{"is": {"loved": True}}],
                "sort": "random",
                "limit": 10,
            },
        )
        nsp_path = Path(created["nsp_path"])
        payload = json.loads(nsp_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["all"], [{"is": {"loved": True}}])
        self.assertEqual(payload["sort"], "random")

    def test_update_smart_playlist_changes_sort_and_limit(self):
        service = PlaylistService(self.config)
        created = service.create_smart_playlist(
            name="Update Test", query="genre:rock")
        updated = service.update_smart_playlist(
            local_id=created["local_id"],
            sort="-playcount",
            limit=50,
        )
        self.assertEqual(updated["local_id"], created["local_id"])
        nsp_path = Path(updated["nsp_path"])
        payload = json.loads(nsp_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["sort"], "-playcount")
        self.assertEqual(payload["limit"], 50)


if __name__ == "__main__":
    unittest.main()
