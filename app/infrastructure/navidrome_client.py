"""Navidrome Subsonic API client used by playlist features."""

import hashlib
import secrets
from typing import Any, Dict, List, Optional

import requests

from app.config import Config


class NavidromeClientError(Exception):
    """Raised when Navidrome API returns an error or invalid payload."""


class NavidromeAuthError(NavidromeClientError):
    """Raised when authentication fails against Navidrome."""


class NavidromeClient:
    """Small client wrapper around Navidrome Subsonic-compatible endpoints."""

    def __init__(self, config: Config, timeout: Optional[float] = None):
        self.config = config
        self.base_url = config.navidrome_base_url
        self.timeout = timeout if timeout is not None else config.navidrome_timeout_seconds
        self.session = requests.Session()

    def _build_auth_params(self) -> Dict[str, str]:
        salt = secrets.token_hex(6)
        token = hashlib.md5(
            f"{self.config.navidrome_password}{salt}".encode("utf-8")
        ).hexdigest()
        return {
            "u": self.config.navidrome_username,
            "t": token,
            "s": salt,
            "v": self.config.navidrome_api_version,
            "c": self.config.navidrome_client_name,
            "f": "json",
        }

    def _parse_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        root = payload.get("subsonic-response")
        if not isinstance(root, dict):
            raise NavidromeClientError("Invalid Subsonic response format")

        status = str(root.get("status", "")).lower()
        if status == "ok":
            return root

        error_payload = root.get("error")
        if isinstance(error_payload, dict):
            code = error_payload.get("code")
            message = error_payload.get("message") or "Unknown API error"
            error_message = f"Navidrome API error (code={code}): {message}"
        else:
            error_message = "Navidrome API returned failure status"

        if "auth" in error_message.lower() or "token" in error_message.lower():
            raise NavidromeAuthError(error_message)
        raise NavidromeClientError(error_message)

    def _request(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> Dict[str, Any]:
        if not self.base_url:
            raise NavidromeClientError("NAVIDROME_BASE_URL is not configured")

        all_params: Dict[str, Any] = self._build_auth_params()
        if params:
            all_params.update(params)

        url = f"{self.base_url}/rest/{endpoint}.view"
        response = self.session.request(
            method=method,
            url=url,
            params=all_params,
            timeout=self.timeout,
            verify=self.config.navidrome_verify_tls,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise NavidromeClientError(
                "Navidrome API returned non-JSON payload")

        return self._parse_response(payload)

    @staticmethod
    def _as_subsonic_bool(value: bool) -> str:
        return "true" if value else "false"

    def ping(self) -> bool:
        self._request("ping")
        return True

    def get_playlists(self) -> List[Dict[str, Any]]:
        root = self._request("getPlaylists")
        playlists = root.get("playlists", {}).get("playlist", [])
        if isinstance(playlists, dict):
            return [playlists]
        if isinstance(playlists, list):
            return [item for item in playlists if isinstance(item, dict)]
        return []

    def get_playlist(self, playlist_id: str) -> Dict[str, Any]:
        root = self._request("getPlaylist", params={"id": playlist_id})
        playlist = root.get("playlist")
        if not isinstance(playlist, dict):
            raise NavidromeClientError("Playlist not found or invalid payload")
        return playlist

    def create_playlist(
        self,
        name: str,
        *,
        song_ids: Optional[List[str]] = None,
        public: Optional[bool] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"name": name}
        if song_ids:
            params["songId"] = song_ids
        if public is not None:
            params["public"] = self._as_subsonic_bool(public)

        root = self._request("createPlaylist", params=params)
        playlist = root.get("playlist")
        if not isinstance(playlist, dict):
            raise NavidromeClientError(
                "Invalid createPlaylist response payload")
        return playlist

    def update_playlist(
        self,
        playlist_id: str,
        *,
        name: Optional[str] = None,
        comment: Optional[str] = None,
        public: Optional[bool] = None,
        song_ids_to_add: Optional[List[str]] = None,
        song_indexes_to_remove: Optional[List[int]] = None,
    ) -> None:
        params: Dict[str, Any] = {"playlistId": playlist_id}
        if name is not None:
            params["name"] = name
        if comment is not None:
            params["comment"] = comment
        if public is not None:
            params["public"] = self._as_subsonic_bool(public)
        if song_ids_to_add:
            params["songIdToAdd"] = song_ids_to_add
        if song_indexes_to_remove:
            params["songIndexToRemove"] = [
                str(index) for index in song_indexes_to_remove]

        self._request("updatePlaylist", params=params)

    def delete_playlist(self, playlist_id: str) -> None:
        self._request("deletePlaylist", params={"id": playlist_id})

    def start_scan(self) -> None:
        self._request("startScan")

    def search_songs(self, query: str, song_count: int = 20) -> List[Dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []

        root = self._request(
            "search3",
            params={
                "query": normalized_query,
                "songCount": max(1, int(song_count)),
                "artistCount": 0,
                "albumCount": 0,
            },
        )
        result = root.get("searchResult3")
        if not isinstance(result, dict):
            return []

        songs = result.get("song", [])
        if isinstance(songs, dict):
            return [songs]
        if isinstance(songs, list):
            return [item for item in songs if isinstance(item, dict)]
        return []

    def close(self) -> None:
        self.session.close()
