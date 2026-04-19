"""Unit tests for Navidrome Subsonic API client."""

import unittest
from unittest.mock import MagicMock, patch

from app.infrastructure.navidrome_client import NavidromeClient, NavidromeClientError


class TestNavidromeClient(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        self.config.navidrome_base_url = "http://localhost:4533"
        self.config.navidrome_timeout_seconds = 10.0
        self.config.navidrome_verify_tls = True
        self.config.navidrome_username = "admin"
        self.config.navidrome_password = "secret"
        self.config.navidrome_api_version = "1.16.1"
        self.config.navidrome_client_name = "media-organizer-test"

    def _response_mock(self, payload):
        response = MagicMock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response

    @patch("app.infrastructure.navidrome_client.requests.Session.request")
    def test_ping_success(self, request_mock):
        request_mock.return_value = self._response_mock(
            {"subsonic-response": {"status": "ok"}}
        )

        client = NavidromeClient(self.config)
        try:
            self.assertTrue(client.ping())
        finally:
            client.close()

    @patch("app.infrastructure.navidrome_client.requests.Session.request")
    def test_get_playlists_handles_single_playlist_dict(self, request_mock):
        request_mock.return_value = self._response_mock(
            {
                "subsonic-response": {
                    "status": "ok",
                    "playlists": {
                        "playlist": {
                            "id": "1",
                            "name": "Test Playlist",
                            "songCount": 5,
                        }
                    },
                }
            }
        )

        client = NavidromeClient(self.config)
        try:
            playlists = client.get_playlists()
            self.assertEqual(len(playlists), 1)
            self.assertEqual(playlists[0]["id"], "1")
        finally:
            client.close()

    @patch("app.infrastructure.navidrome_client.requests.Session.request")
    def test_get_playlist_returns_playlist(self, request_mock):
        request_mock.return_value = self._response_mock(
            {
                "subsonic-response": {
                    "status": "ok",
                    "playlist": {
                        "id": "99",
                        "name": "Roadtrip",
                    },
                }
            }
        )

        client = NavidromeClient(self.config)
        try:
            playlist = client.get_playlist("99")
            self.assertEqual(playlist["name"], "Roadtrip")
        finally:
            client.close()

    @patch("app.infrastructure.navidrome_client.requests.Session.request")
    def test_api_failure_raises_client_error(self, request_mock):
        request_mock.return_value = self._response_mock(
            {
                "subsonic-response": {
                    "status": "failed",
                    "error": {
                        "code": 0,
                        "message": "Invalid API key",
                    },
                }
            }
        )

        client = NavidromeClient(self.config)
        try:
            with self.assertRaises(NavidromeClientError):
                client.ping()
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
