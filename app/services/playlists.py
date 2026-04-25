"""Playlist service for Navidrome simple and smart playlists."""

import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import Config
from app.infrastructure import NavidromeClient, PlaylistStore
from app.logging import get_logger
from app.features.smart_playlists import (
    SmartPlaylistBuilder,
    SmartPlaylistDefinition,
    QueryStringParser,
)


class PlaylistService:
    """High-level service for playlist CRUD and local state synchronization."""

    def __init__(self, config: Config, logger=None):
        self.config = config
        self.logger = logger or get_logger(__name__)
        self.store = PlaylistStore(config.navidrome_playlists_state_path)

    @staticmethod
    def _parse_csv(csv_values: str) -> List[str]:
        values: List[str] = []
        for item in str(csv_values or "").split(","):
            cleaned = item.strip()
            if cleaned:
                values.append(cleaned)
        return values

    def _new_local_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:10]}"

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return " ".join(str(value or "").strip().lower().split())

    @staticmethod
    def _smart_all_from_query(query: str) -> List[Dict[str, Any]]:
        """Build a Navidrome Smart Playlist `all` clause from a simple OR query string."""
        raw_terms = re.split(
            r"\s+OR\s+", str(query or ""), flags=re.IGNORECASE)
        terms = [term.strip() for term in raw_terms if term and term.strip()]
        if not terms:
            return []

        any_rules: List[Dict[str, Any]] = []
        for term in terms:
            any_rules.extend(
                [
                    {"contains": {"title": term}},
                    {"contains": {"artist": term}},
                    {"contains": {"album": term}},
                ]
            )
        return [{"any": any_rules}]

    def _music_records_from_organization(self) -> List[Dict[str, Any]]:
        db_path = Path(self.config.database_path)
        if not db_path.exists():
            return []

        try:
            payload = json.loads(db_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, dict):
            return []

        media_map = payload.get("media")
        if not isinstance(media_map, dict):
            return []

        items: List[Dict[str, Any]] = []
        for record in media_map.values():
            if not isinstance(record, dict):
                continue
            metadata = record.get("metadata")
            if not isinstance(metadata, dict):
                continue
            media_type = self._normalize_text(metadata.get("media_type"))
            if media_type != "music":
                continue
            items.append(record)
        return items

    def _record_matches_filters(
        self,
        record: Dict[str, Any],
        *,
        artist_filter: Optional[str],
        genre_filter: Optional[str],
        album_filter: Optional[str],
    ) -> bool:
        metadata = dict(record.get("metadata") or {})

        artist_text = self._normalize_text(
            metadata.get("artist") or metadata.get("primary_artist")
        )
        album_text = self._normalize_text(metadata.get("album"))
        genres_raw = metadata.get("genres")
        genres: List[Any] = genres_raw if isinstance(genres_raw, list) else []
        genres_text = " ".join(self._normalize_text(item) for item in genres)
        if not genres_text:
            genres_text = self._normalize_text(metadata.get("genre"))

        if artist_filter and artist_filter not in artist_text:
            return False
        if genre_filter and genre_filter not in genres_text:
            return False
        if album_filter and album_filter not in album_text:
            return False
        return True

    def _candidate_score(self, candidate: Dict[str, Any], metadata: Dict[str, Any], organized_path: str) -> int:
        score = 0

        title_expected = self._normalize_text(
            metadata.get("title") or metadata.get("track_name"))
        artist_expected = self._normalize_text(
            metadata.get("artist") or metadata.get("primary_artist"))
        album_expected = self._normalize_text(metadata.get("album"))

        title_actual = self._normalize_text(candidate.get("title"))
        artist_actual = self._normalize_text(candidate.get("artist"))
        album_actual = self._normalize_text(candidate.get("album"))
        path_actual = self._normalize_text(candidate.get("path"))
        suffix_expected = self._normalize_text(
            Path(str(organized_path or "")).name)

        if title_expected and title_expected == title_actual:
            score += 50
        elif title_expected and title_expected in title_actual:
            score += 30

        if artist_expected and artist_expected == artist_actual:
            score += 30
        elif artist_expected and artist_expected in artist_actual:
            score += 15

        if album_expected and album_expected == album_actual:
            score += 20
        elif album_expected and album_expected in album_actual:
            score += 10

        if suffix_expected and suffix_expected and suffix_expected in path_actual:
            score += 40

        return score

    def _resolve_song_id_from_record(self, client: NavidromeClient, record: Dict[str, Any]) -> str:
        metadata = dict(record.get("metadata") or {})
        organized_path = str(record.get("organized_path") or "")

        title = str(metadata.get("title") or metadata.get(
            "track_name") or "").strip()
        artist = str(metadata.get("artist") or metadata.get(
            "primary_artist") or "").strip()
        album = str(metadata.get("album") or "").strip()

        search_terms = [term for term in [title, artist, album] if term]
        if not search_terms and organized_path:
            search_terms = [Path(organized_path).stem]
        query = " ".join(search_terms).strip()
        if not query:
            return ""

        candidates = client.search_songs(query, song_count=30)
        if not candidates:
            return ""

        ranked = sorted(
            candidates,
            key=lambda item: self._candidate_score(
                item, metadata, organized_path),
            reverse=True,
        )
        best = ranked[0]
        best_score = self._candidate_score(best, metadata, organized_path)
        if best_score < 30:
            return ""
        return str(best.get("id", "")).strip()

    @staticmethod
    def _song_ids_from_playlist_payload(playlist_payload: Dict[str, Any]) -> List[str]:
        entries = playlist_payload.get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        if not isinstance(entries, list):
            return []
        return [str(item.get("id", "")).strip() for item in entries if isinstance(item, dict) and str(item.get("id", "")).strip()]

    def _resolve_smart_definition(
        self,
        *,
        name: str,
        query: str = "",
        sort: Optional[str] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        limit_percent: Optional[int] = None,
        builder: Optional[SmartPlaylistBuilder] = None,
        nsp_definition: Optional[Dict[str, Any]] = None,
    ) -> SmartPlaylistDefinition:
        if builder is not None:
            definition = builder.build()
        elif nsp_definition:
            definition = self._definition_from_nsp_dict(nsp_definition)
        elif query:
            definition = QueryStringParser().parse(query)
        else:
            raise ValueError("Smart playlist query is required")
        definition.name = name
        if sort is not None:
            definition.sort = sort
        if order is not None:
            definition.order = order
        if limit is not None:
            definition.limit = limit
            definition.limit_percent = None
        if limit_percent is not None:
            definition.limit_percent = limit_percent
            definition.limit = None
        return definition

    @staticmethod
    def _definition_from_nsp_dict(nsp_definition: Dict[str, Any]) -> SmartPlaylistDefinition:
        from app.features.smart_playlists.definition import Rule
        definition = SmartPlaylistDefinition(name="")
        all_rules_raw = nsp_definition.get("all", [])
        any_rules_raw = nsp_definition.get("any", [])
        for rule_dict in all_rules_raw:
            for op, field_value in rule_dict.items():
                for field, value in field_value.items():
                    definition.all_rules.append(Rule(op, field, value))
        for rule_dict in any_rules_raw:
            for op, field_value in rule_dict.items():
                for field, value in field_value.items():
                    definition.any_rules.append(Rule(op, field, value))
        definition.sort = nsp_definition.get("sort")
        definition.order = nsp_definition.get("order")
        definition.limit = nsp_definition.get("limit")
        definition.limit_percent = nsp_definition.get("limitPercent")
        return definition

    def test_connection(self) -> bool:
        client = NavidromeClient(self.config)
        try:
            return client.ping()
        finally:
            client.close()

    def list_remote_playlists(self) -> List[Dict[str, Any]]:
        client = NavidromeClient(self.config)
        try:
            return client.get_playlists()
        finally:
            client.close()

    def trigger_scan(self) -> None:
        client = NavidromeClient(self.config)
        try:
            client.start_scan()
        finally:
            client.close()

    def list_local_playlists(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.store.list_playlists(kind=kind)

    def create_simple_playlist(
        self,
        *,
        name: str,
        song_ids_csv: str = "",
        public: bool = False,
    ) -> Dict[str, Any]:
        name = str(name or "").strip()
        if not name:
            raise ValueError("Playlist name is required")

        song_ids = self._parse_csv(song_ids_csv)
        client = NavidromeClient(self.config)
        try:
            created = client.create_playlist(
                name=name, song_ids=song_ids, public=public)
        finally:
            client.close()

        record = {
            "local_id": self._new_local_id("simple"),
            "kind": "simple",
            "name": name,
            "remote_id": str(created.get("id", "")).strip(),
            "public": public,
            "song_ids": song_ids,
            "status": "active",
        }
        return self.store.upsert_playlist(record)

    def delete_simple_playlist(self, local_id: str, delete_remote: bool = True) -> bool:
        record = self.store.get_playlist(local_id)
        if not record:
            return False

        remote_id = str(record.get("remote_id", "")).strip()
        if delete_remote and remote_id:
            client = NavidromeClient(self.config)
            try:
                client.delete_playlist(remote_id)
            finally:
                client.close()

        return self.store.delete_playlist(local_id)

    def sync_simple_playlist_from_organization(
        self,
        *,
        name: str,
        public: bool = False,
        artist_filter: str = "",
        genre_filter: str = "",
        album_filter: str = "",
        limit: int = 0,
        mode: str = "recreate",
        preview_only: bool = False,
    ) -> Dict[str, Any]:
        name = str(name or "").strip()
        if not name:
            raise ValueError("Playlist name is required")

        normalized_artist = self._normalize_text(artist_filter)
        normalized_genre = self._normalize_text(genre_filter)
        normalized_album = self._normalize_text(album_filter)

        records = self._music_records_from_organization()
        matched = [
            record for record in records
            if self._record_matches_filters(
                record,
                artist_filter=normalized_artist,
                genre_filter=normalized_genre,
                album_filter=normalized_album,
            )
        ]
        if limit > 0:
            matched = matched[:limit]

        normalized_mode = self._normalize_text(mode) or "recreate"
        if normalized_mode not in {"recreate", "incremental"}:
            raise ValueError("mode must be 'recreate' or 'incremental'")

        resolved_ids: List[str] = []
        unresolved: List[str] = []
        to_add: List[str] = []
        to_remove_indexes: List[int] = []
        to_remove_song_ids: List[str] = []
        existing_song_count = 0
        will_update = False
        will_recreate = False
        will_create = False

        client = NavidromeClient(self.config)
        try:
            for record in matched:
                song_id = self._resolve_song_id_from_record(client, record)
                if song_id:
                    resolved_ids.append(song_id)
                else:
                    unresolved.append(
                        str(record.get("organized_path") or record.get("original_path") or ""))

            resolved_ids = list(dict.fromkeys(resolved_ids))

            existing_remote = None
            for playlist in client.get_playlists():
                if self._normalize_text(playlist.get("name")) == self._normalize_text(name):
                    existing_remote = playlist
                    break
            existing_id = ""
            if isinstance(existing_remote, dict):
                existing_id = str(existing_remote.get("id", "")).strip()

            created: Dict[str, Any]
            if normalized_mode == "incremental" and existing_id:
                remote_full = client.get_playlist(existing_id)
                remote_song_ids = self._song_ids_from_playlist_payload(
                    remote_full)
                existing_song_count = len(remote_song_ids)

                remote_set = set(remote_song_ids)
                target_set = set(resolved_ids)

                to_add = [
                    song_id for song_id in resolved_ids if song_id not in remote_set]
                to_remove_indexes = [index for index, song_id in enumerate(
                    remote_song_ids) if song_id not in target_set]
                to_remove_song_ids = [
                    song_id for song_id in remote_song_ids if song_id not in target_set]
                will_update = bool(to_add or to_remove_indexes)

                if will_update and not preview_only:
                    client.update_playlist(
                        existing_id,
                        public=public,
                        song_ids_to_add=to_add,
                        song_indexes_to_remove=to_remove_indexes,
                    )
                created = client.get_playlist(
                    existing_id) if not preview_only else remote_full
            else:
                if existing_id:
                    if preview_only:
                        remote_full = client.get_playlist(existing_id)
                        remote_song_ids = self._song_ids_from_playlist_payload(
                            remote_full)
                        existing_song_count = len(remote_song_ids)
                        to_remove_indexes = list(range(existing_song_count))
                        to_remove_song_ids = list(remote_song_ids)
                        to_add = list(resolved_ids)
                        will_recreate = True
                        created = remote_full
                    else:
                        client.delete_playlist(existing_id)
                        created = client.create_playlist(
                            name=name, song_ids=resolved_ids, public=public)
                else:
                    to_add = list(resolved_ids)
                    will_create = True
                    if preview_only:
                        created = {"id": "", "name": name}
                    else:
                        created = client.create_playlist(
                            name=name, song_ids=resolved_ids, public=public)
        finally:
            client.close()

        report_payload = {
            "playlist": None,
            "matched_records": len(matched),
            "resolved_count": len(resolved_ids),
            "unresolved_count": len(unresolved),
            "unresolved_paths": unresolved[:30],
            "preview": {
                "enabled": bool(preview_only),
                "mode": normalized_mode,
                "existing_remote_id": existing_id,
                "existing_song_count": existing_song_count,
                "target_song_count": len(resolved_ids),
                "to_add_count": len(to_add),
                "to_remove_count": len(to_remove_indexes),
                "to_add_song_ids": to_add[:30],
                "to_remove_song_ids": to_remove_song_ids[:30],
                "will_update": will_update,
                "will_recreate": will_recreate,
                "will_create": will_create,
            },
        }

        if preview_only:
            return report_payload

        local_record = None
        for item in self.store.list_playlists(kind="simple"):
            if self._normalize_text(item.get("name")) == self._normalize_text(name):
                local_record = item
                break

        record_payload = {
            "local_id": str(local_record.get("local_id")) if isinstance(local_record, dict) else self._new_local_id("simple"),
            "kind": "simple",
            "name": name,
            "remote_id": str(created.get("id", "")).strip(),
            "public": public,
            "song_ids": resolved_ids,
            "source": "organization.json",
            "sync_mode": normalized_mode,
            "filters": {
                "artist": artist_filter,
                "genre": genre_filter,
                "album": album_filter,
                "limit": max(0, int(limit or 0)),
            },
            "last_sync": {
                "matched_records": len(matched),
                "resolved": len(resolved_ids),
                "unresolved": len(unresolved),
            },
            "status": "active",
        }
        saved = self.store.upsert_playlist(record_payload)
        report_payload["playlist"] = saved
        return report_payload

    def create_smart_playlist(
        self,
        *,
        name: str,
        query: str = "",
        public: bool = False,
        comment: str = "",
        sort: Optional[str] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        limit_percent: Optional[int] = None,
        builder: Optional[SmartPlaylistBuilder] = None,
        nsp_definition: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        name = str(name or "").strip()
        if not name:
            raise ValueError("Playlist name is required")

        definition = self._resolve_smart_definition(
            name=name,
            query=query,
            sort=sort,
            order=order,
            limit=limit,
            limit_percent=limit_percent,
            builder=builder,
            nsp_definition=nsp_definition,
        )

        local_id = self._new_local_id("smart")
        smart_dir = self.config.navidrome_smart_playlist_dir
        smart_dir.mkdir(parents=True, exist_ok=True)
        nsp_path = smart_dir / f"{name}.nsp"

        payload = definition.to_nsp_dict()
        payload["name"] = name
        payload["comment"] = comment
        payload["public"] = public

        nsp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if self.config.navidrome_smart_playlist_auto_scan:
            self.trigger_scan()

        record = {
            "local_id": local_id,
            "kind": "smart",
            "name": name,
            "query": query or "[advanced-builder]",
            "public": public,
            "comment": comment,
            "nsp_path": str(nsp_path),
            "status": "active",
        }
        return self.store.upsert_playlist(record)

    def update_smart_playlist(
        self,
        *,
        local_id: str,
        query: Optional[str] = None,
        public: Optional[bool] = None,
        comment: Optional[str] = None,
        sort: Optional[str] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        limit_percent: Optional[int] = None,
        builder: Optional[SmartPlaylistBuilder] = None,
        nsp_definition: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        record = self.store.get_playlist(local_id)
        if not record:
            raise ValueError("Smart playlist not found")
        if str(record.get("kind", "")).strip().lower() != "smart":
            raise ValueError("Local id does not belong to a smart playlist")

        nsp_path = Path(str(record.get("nsp_path", "")).strip())
        if not nsp_path.exists():
            raise FileNotFoundError(f"NSP file not found: {nsp_path}")

        name = str(record.get("name", "")).strip()
        new_public = bool(public) if public is not None else bool(record.get("public", False))
        new_comment = str(comment if comment is not None else record.get("comment", "")).strip()

        current_payload = json.loads(nsp_path.read_text(encoding="utf-8"))
        current_definition = self._definition_from_nsp_dict(current_payload)

        if builder is not None:
            definition = builder.build()
        elif nsp_definition:
            definition = self._definition_from_nsp_dict(nsp_definition)
        elif query is not None:
            definition = QueryStringParser().parse(query)
        else:
            definition = current_definition

        definition.name = name
        definition.comment = new_comment
        definition.public = new_public
        if sort is not None:
            definition.sort = sort
        if order is not None:
            definition.order = order
        if limit is not None:
            definition.limit = limit
            definition.limit_percent = None
        if limit_percent is not None:
            definition.limit_percent = limit_percent
            definition.limit = None

        payload = definition.to_nsp_dict()
        nsp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if self.config.navidrome_smart_playlist_auto_scan:
            self.trigger_scan()

        if builder is not None:
            record["query"] = "[advanced-builder]"
        elif nsp_definition:
            record["query"] = "[advanced-builder]"
        elif query is not None:
            record["query"] = query
        record["public"] = new_public
        record["comment"] = new_comment
        return self.store.upsert_playlist(record)

    def delete_smart_playlist(self, local_id: str, delete_file: bool = True) -> bool:
        record = self.store.get_playlist(local_id)
        if not record:
            return False

        if str(record.get("kind", "")).strip().lower() != "smart":
            return False

        nsp_path = Path(str(record.get("nsp_path", "")).strip())
        if delete_file and nsp_path.exists():
            nsp_path.unlink()

        deleted = self.store.delete_playlist(local_id)
        if deleted and self.config.navidrome_smart_playlist_auto_scan:
            self.trigger_scan()
        return deleted
