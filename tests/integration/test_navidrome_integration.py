"""Integration tests for Navidrome smart playlists using real server.

These tests require a running Navidrome test server.
Use: docker-compose -f docker-compose.test.yml up -d

Default test credentials: admin / test123
Test server: http://localhost:4534
"""

import json
import os
import time
from pathlib import Path

import pytest
import requests

from app.config import Config
from app.features.smart_playlists import SmartPlaylistBuilder
from app.infrastructure import NavidromeClient
from app.services import PlaylistService


TEST_BASE_URL = os.environ.get("NAVIDROME_TEST_URL", "http://localhost:4534")
TEST_USERNAME = os.environ.get("NAVIDROME_TEST_USER", "admin")
TEST_PASSWORD = os.environ.get("NAVIDROME_TEST_PASS", "test123")


@pytest.fixture(scope="session")
def navidrome_test_server():
    """Ensure Navidrome test server is available."""
    try:
        response = requests.get(f"{TEST_BASE_URL}/app", timeout=5)
        if response.status_code == 200:
            return True
    except requests.ConnectionError:
        pass
    pytest.skip(
        f"Navidrome test server not available at {TEST_BASE_URL}. "
        "Run: docker-compose -f docker-compose.test.yml up -d"
    )


@pytest.fixture
def test_config(tmp_path, navidrome_test_server, monkeypatch):
    """Create test config pointing to test server."""
    monkeypatch.setenv("NAVIDROME_ENABLED", "true")
    monkeypatch.setenv("NAVIDROME_BASE_URL", TEST_BASE_URL)
    monkeypatch.setenv("NAVIDROME_USERNAME", TEST_USERNAME)
    monkeypatch.setenv("NAVIDROME_PASSWORD", TEST_PASSWORD)
    monkeypatch.setenv("NAVIDROME_API_VERSION", "1.16.1")
    monkeypatch.setenv("NAVIDROME_CLIENT_NAME", "media-organizer-test")
    monkeypatch.setenv("NAVIDROME_VERIFY_TLS", "true")
    monkeypatch.setenv("NAVIDROME_SMART_PLAYLIST_DIR", str(tmp_path / "smart"))
    monkeypatch.setenv("NAVIDROME_SMART_PLAYLIST_AUTO_SCAN", "false")
    monkeypatch.setenv("NAVIDROME_PLAYLISTS_STATE_PATH", str(tmp_path / "playlists_state.json"))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "organization.json"))
    config = Config()
    return config


@pytest.fixture
def navidrome_client(test_config):
    """Create authenticated Navidrome client."""
    client = NavidromeClient(test_config)
    yield client
    client.close()


@pytest.fixture
def playlist_service(test_config):
    """Create PlaylistService for tests."""
    return PlaylistService(test_config)


def _is_navidrome_api_available() -> bool:
    """Check if Navidrome API accepts our credentials."""
    import os
    from app.config import Config
    from app.infrastructure import NavidromeClient
    os.environ.setdefault("NAVIDROME_ENABLED", "true")
    os.environ.setdefault("NAVIDROME_BASE_URL", TEST_BASE_URL)
    os.environ.setdefault("NAVIDROME_USERNAME", TEST_USERNAME)
    os.environ.setdefault("NAVIDROME_PASSWORD", TEST_PASSWORD)
    try:
        config = Config()
        client = NavidromeClient(config)
        # Use getPlaylists (requires auth) instead of ping (often anonymous)
        client.get_playlists()
        client.close()
        return True
    except Exception:
        return False


NAVIDROME_API_AVAILABLE = _is_navidrome_api_available()


@pytest.fixture(autouse=True)
def cleanup_navidrome_playlists(navidrome_client):
    """Clean up test playlists after each test."""
    yield
    if not NAVIDROME_API_AVAILABLE:
        return
    try:
        playlists = navidrome_client.get_playlists()
        for playlist in playlists:
            name = str(playlist.get("name", ""))
            if name.startswith("TEST_"):
                try:
                    navidrome_client.delete_playlist(playlist["id"])
                except Exception:
                    pass
    except Exception:
        pass


def _check_auth(client):
    """Skip test if Navidrome auth fails."""
    try:
        client.ping()
    except Exception as e:
        if "username or password" in str(e).lower() or "auth" in str(e).lower():
            pytest.skip(f"Navidrome auth failed: {e}")
        raise


class TestNavidromeConnection:
    """Test basic connectivity to Navidrome test server."""

    def test_ping_server(self, navidrome_client):
        _check_auth(navidrome_client)
        assert navidrome_client.ping() is True

    def test_get_playlists_empty(self, navidrome_client):
        _check_auth(navidrome_client)
        playlists = navidrome_client.get_playlists()
        assert isinstance(playlists, list)


class TestSmartPlaylistIntegration:
    """Test smart playlist creation via real Navidrome API."""

    def test_create_smart_playlist_with_query_string(self, playlist_service):
        """Create a smart playlist using query string syntax."""
        result = playlist_service.create_smart_playlist(
            name="TEST_Rock_2020",
            query="genre:rock year:gt:2020",
            public=False,
            comment="Integration test",
        )

        assert result["kind"] == "smart"
        assert result["name"] == "TEST_Rock_2020"
        assert Path(result["nsp_path"]).exists()

        # Verify NSP file content
        nsp_content = json.loads(Path(result["nsp_path"]).read_text())
        assert nsp_content["name"] == "TEST_Rock_2020"
        assert nsp_content["comment"] == "Integration test"
        assert nsp_content["public"] is False
        assert "all" in nsp_content
        assert nsp_content["all"][0] == {"contains": {"genre": "rock"}}
        assert nsp_content["all"][1] == {"gt": {"year": 2020}}

    def test_create_smart_playlist_with_builder(self, playlist_service):
        """Create a smart playlist using builder API."""
        builder = SmartPlaylistBuilder("TEST_Builder_HighRated")
        builder.all_of(
            builder.field("rating").gt(3),
            builder.field("loved").is_(True),
        ).sort("-rating", "title").limit(50)

        result = playlist_service.create_smart_playlist(
            name="TEST_Builder_HighRated",
            builder=builder,
            comment="Builder integration test",
        )

        assert result["kind"] == "smart"
        nsp_content = json.loads(Path(result["nsp_path"]).read_text())
        assert nsp_content["sort"] == "-rating,title"
        assert nsp_content["limit"] == 50
        assert nsp_content["all"][0] == {"gt": {"rating": 3}}
        assert nsp_content["all"][1] == {"is": {"loved": True}}

    def test_create_smart_playlist_with_sort_order_limit(self, playlist_service):
        """Test direct sort, order, and limit parameters."""
        result = playlist_service.create_smart_playlist(
            name="TEST_SortOrderLimit",
            query="genre:electronic",
            sort="-playcount",
            order="desc",
            limit=25,
        )

        nsp_content = json.loads(Path(result["nsp_path"]).read_text())
        assert nsp_content["sort"] == "-playcount"
        assert nsp_content["order"] == "desc"
        assert nsp_content["limit"] == 25

    def test_update_smart_playlist_changes_rules(self, playlist_service):
        """Update an existing smart playlist."""
        created = playlist_service.create_smart_playlist(
            name="TEST_UpdateTarget",
            query="genre:rock",
        )

        updated = playlist_service.update_smart_playlist(
            local_id=created["local_id"],
            query="genre:metal",
            sort="-year",
            limit=100,
        )

        assert updated["local_id"] == created["local_id"]
        nsp_content = json.loads(Path(updated["nsp_path"]).read_text())
        assert nsp_content["all"][0] == {"contains": {"genre": "metal"}}
        assert nsp_content["sort"] == "-year"
        assert nsp_content["limit"] == 100

    def test_nsp_definition_backward_compatibility(self, playlist_service):
        """Ensure raw NSP definition still works."""
        result = playlist_service.create_smart_playlist(
            name="TEST_NSP_Raw",
            nsp_definition={
                "all": [{"is": {"loved": True}}],
                "sort": "random",
                "limit": 10,
            },
        )

        nsp_content = json.loads(Path(result["nsp_path"]).read_text())
        assert nsp_content["all"] == [{"is": {"loved": True}}]
        assert nsp_content["sort"] == "random"
        assert nsp_content["limit"] == 10

    def test_limit_and_limit_percent_mutual_exclusion(self, playlist_service):
        """Verify limit overrides limit_percent and vice versa."""
        result = playlist_service.create_smart_playlist(
            name="TEST_LimitExclusion",
            query="genre:rock",
            limit=50,
        )
        nsp_content = json.loads(Path(result["nsp_path"]).read_text())
        assert nsp_content["limit"] == 50
        assert "limitPercent" not in nsp_content

    def test_invalid_field_raises_error(self, playlist_service):
        """Test that invalid fields are rejected."""
        with pytest.raises(ValueError, match="Invalid field"):
            playlist_service.create_smart_playlist(
                name="TEST_InvalidField",
                query="invalidfield:value",
            )

    def test_invalid_operator_raises_error(self, playlist_service):
        """Test that invalid operators are rejected."""
        with pytest.raises(ValueError, match="not allowed"):
            playlist_service.create_smart_playlist(
                name="TEST_InvalidOperator",
                query="genre:gt:rock",
            )


class TestSimplePlaylistIntegration:
    """Test simple playlist operations with real Navidrome API."""

    def test_test_connection(self, playlist_service):
        """Test connection to Navidrome."""
        client = NavidromeClient(playlist_service.config)
        _check_auth(client)
        assert playlist_service.test_connection() is True

    def test_list_remote_playlists(self, playlist_service):
        """List remote playlists."""
        client = NavidromeClient(playlist_service.config)
        _check_auth(client)
        playlists = playlist_service.list_remote_playlists()
        assert isinstance(playlists, list)

    def test_create_and_delete_simple_playlist(self, playlist_service, navidrome_client):
        """Create a simple playlist and verify it appears remotely."""
        _check_auth(navidrome_client)
        result = playlist_service.create_simple_playlist(
            name="TEST_SimplePlaylist",
            song_ids_csv="",
            public=True,
        )

        assert result["kind"] == "simple"
        assert result["remote_id"]

        # Verify it exists remotely
        remote_playlists = navidrome_client.get_playlists()
        names = [p["name"] for p in remote_playlists]
        assert "TEST_SimplePlaylist" in names

        # Delete it
        deleted = playlist_service.delete_simple_playlist(result["local_id"])
        assert deleted is True

        # Verify it's gone
        remote_playlists = navidrome_client.get_playlists()
        names = [p["name"] for p in remote_playlists]
        assert "TEST_SimplePlaylist" not in names


class TestPlaylistStoreIntegration:
    """Test local state persistence."""

    def test_local_playlist_persistence(self, playlist_service):
        """Test that playlists are persisted locally."""
        created = playlist_service.create_smart_playlist(
            name="TEST_Persistence",
            query="genre:jazz",
        )

        # Reload from store
        local = playlist_service.list_local_playlists(kind="smart")
        names = [p["name"] for p in local]
        assert "TEST_Persistence" in names

    def test_delete_smart_playlist_removes_file(self, playlist_service):
        """Test deleting smart playlist removes NSP file."""
        created = playlist_service.create_smart_playlist(
            name="TEST_DeleteFile",
            query="genre:classical",
        )

        nsp_path = Path(created["nsp_path"])
        assert nsp_path.exists()

        playlist_service.delete_smart_playlist(created["local_id"])

        assert not nsp_path.exists()
