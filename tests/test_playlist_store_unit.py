"""Unit tests for local playlist store."""

import tempfile
import unittest
from pathlib import Path

from app.infrastructure.playlist_store import PlaylistStore


class TestPlaylistStore(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmp_dir.name) / "playlists_state.json"
        self.store = PlaylistStore(self.state_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_upsert_and_get_playlist(self):
        saved = self.store.upsert_playlist(
            {
                "local_id": "simple_123",
                "kind": "simple",
                "name": "Roadtrip",
                "remote_id": "55",
            }
        )
        self.assertEqual(saved["local_id"], "simple_123")

        fetched = self.store.get_playlist("simple_123")
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched["name"], "Roadtrip")

    def test_list_filter_by_kind(self):
        self.store.upsert_playlist(
            {
                "local_id": "simple_1",
                "kind": "simple",
                "name": "A",
            }
        )
        self.store.upsert_playlist(
            {
                "local_id": "smart_1",
                "kind": "smart",
                "name": "B",
            }
        )

        simple = self.store.list_playlists(kind="simple")
        smart = self.store.list_playlists(kind="smart")

        self.assertEqual(len(simple), 1)
        self.assertEqual(len(smart), 1)

    def test_delete_playlist(self):
        self.store.upsert_playlist(
            {
                "local_id": "smart_x",
                "kind": "smart",
                "name": "X",
            }
        )
        self.assertTrue(self.store.delete_playlist("smart_x"))
        self.assertIsNone(self.store.get_playlist("smart_x"))


if __name__ == "__main__":
    unittest.main()
