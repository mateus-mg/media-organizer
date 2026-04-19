"""Persistent local storage for Navidrome playlist management state."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class PlaylistStore:
    """Manage local JSON state for simple and smart playlists."""

    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._ensure_file()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _default_state(self) -> Dict[str, Any]:
        now = self._now_iso()
        return {
            "version": 1,
            "updated_at": now,
            "playlists": [],
        }

    def _ensure_file(self) -> None:
        if self.state_path.exists():
            return
        self._write_state(self._default_state())

    def _read_state(self) -> Dict[str, Any]:
        with self._lock:
            try:
                payload = json.loads(
                    self.state_path.read_text(encoding="utf-8"))
            except Exception:
                payload = self._default_state()
            if not isinstance(payload, dict):
                payload = self._default_state()
            if not isinstance(payload.get("playlists"), list):
                payload["playlists"] = []
            return payload

    def _write_state(self, payload: Dict[str, Any]) -> None:
        payload["updated_at"] = self._now_iso()
        with self._lock:
            self.state_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def list_playlists(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        state = self._read_state()
        playlists = [item for item in state.get(
            "playlists", []) if isinstance(item, dict)]
        if kind is None:
            return playlists
        normalized_kind = str(kind).strip().lower()
        return [p for p in playlists if str(p.get("kind", "")).strip().lower() == normalized_kind]

    def get_playlist(self, local_id: str) -> Optional[Dict[str, Any]]:
        local_id = str(local_id).strip()
        for item in self.list_playlists():
            if str(item.get("local_id", "")).strip() == local_id:
                return item
        return None

    def upsert_playlist(self, playlist: Dict[str, Any]) -> Dict[str, Any]:
        local_id = str(playlist.get("local_id", "")).strip()
        if not local_id:
            raise ValueError("playlist.local_id is required")

        state = self._read_state()
        playlists = [item for item in state.get(
            "playlists", []) if isinstance(item, dict)]

        updated = False
        for index, item in enumerate(playlists):
            if str(item.get("local_id", "")).strip() == local_id:
                merged = dict(item)
                merged.update(playlist)
                merged["updated_at"] = self._now_iso()
                playlists[index] = merged
                updated = True
                break

        if not updated:
            new_item = dict(playlist)
            timestamp = self._now_iso()
            new_item.setdefault("created_at", timestamp)
            new_item["updated_at"] = timestamp
            playlists.append(new_item)

        state["playlists"] = playlists
        self._write_state(state)
        result = self.get_playlist(local_id)
        if result is None:
            raise RuntimeError("Playlist save failed")
        return result

    def delete_playlist(self, local_id: str) -> bool:
        local_id = str(local_id).strip()
        state = self._read_state()
        playlists = [item for item in state.get(
            "playlists", []) if isinstance(item, dict)]
        original_count = len(playlists)

        playlists = [
            item for item in playlists
            if str(item.get("local_id", "")).strip() != local_id
        ]
        if len(playlists) == original_count:
            return False

        state["playlists"] = playlists
        self._write_state(state)
        return True
