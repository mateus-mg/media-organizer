"""
Organizers module for Media Organization System.

Supported organizers:
- BaseOrganizer
- MusicOrganizer
- LyricsOrganizer
- BookOrganizer
- CalibreManager
- RenamerOrganizer
"""

import asyncio
import json
import logging
import re
import shutil
import subprocess
import tempfile
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import Config
from src.core import MediaType, OrganizadorInterface, OrganizationResult
from src.media_constants import AUDIO_EXTS, BOOK_EXTS, COMIC_EXTS
from src.metadata import (
    enrich_book_metadata_with_online_sources,
    enrich_music_metadata_with_online_sources,
)
from src.utils import ConflictResolution, calculate_file_hash
from src.value_utils import is_missing_value


class BaseOrganizer(OrganizadorInterface):
    """Base class for all media organizers."""

    def __init__(
        self,
        config: Config,
        database,
        conflict_handler,
        logger: logging.Logger,
        dry_run: bool = False,
    ):
        self.config = config
        self.database = database
        self.conflict_handler = conflict_handler
        self.logger = logger
        self.dry_run = dry_run

    def sanitize_title(self, text: str) -> str:
        if not text:
            return "Untitled"

        for char in '<>:"/\\|?*':
            text = text.replace(char, "")

        text = re.sub(r"\s+", " ", text).strip()
        text = text.rstrip(". ")
        text = re.sub(r"_+$", "", text)

        if not text:
            return "Untitled"

        if len(text) > 100:
            text = text[:97] + "..."

        return text

    def sanitize_author(self, text: str) -> str:
        if not text or text == "Unknown Author":
            return "Unknown Author"

        for char in '<>:"/\\|?*':
            text = text.replace(char, "")

        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"([A-Z])\.([A-Z])\.", r"\1. \2.", text)

        if len(text) > 50:
            text = text[:47] + "..."

        return text

    def calculate_file_hash(self, file_path: Path) -> str:
        return calculate_file_hash(file_path)

    def _is_missing_value(
        self,
        value: Any,
        *,
        unknown_values: Optional[set[str]] = None,
        unknown_prefix: bool = False,
        treat_empty_collections: bool = False,
    ) -> bool:
        return is_missing_value(
            value,
            unknown_values=unknown_values,
            unknown_prefix=unknown_prefix,
            treat_empty_collections=treat_empty_collections,
        )

    def _merge_fields(
        self,
        base: Dict[str, Any],
        incoming: Dict[str, Any],
        *,
        is_missing,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        merged = dict(base)
        for key, value in incoming.items():
            if is_missing(value):
                continue
            if overwrite or is_missing(merged.get(key)):
                merged[key] = value
        return merged

    def _early_skip_if_conflict(
        self,
        source_path: Path,
        dest_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[OrganizationResult]:
        """Return a skip result before costly metadata work when conflict strategy resolves to skip."""
        final_dest_path, action = self.conflict_handler.resolve(
            source_path, dest_path, self.dry_run
        )
        if action != ConflictResolution.SKIPPED:
            return None

        self.logger.info(
            "Early skip before metadata update: %s",
            source_path.name,
        )
        return OrganizationResult(
            success=True,
            organized_path=final_dest_path or dest_path,
            skipped=True,
            metadata=metadata or {},
        )

    async def organizar_file(
        self,
        source_path: Path,
        dest_path: Path,
        metadata: Dict[str, Any],
    ) -> OrganizationResult:
        try:
            if self.database.is_file_organized(str(source_path)):
                return OrganizationResult(
                    success=True,
                    organized_path=dest_path,
                    skipped=True,
                    metadata=metadata,
                )

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            final_dest_path, action = self.conflict_handler.resolve(
                source_path, dest_path, self.dry_run
            )

            if final_dest_path is None:
                return OrganizationResult(
                    success=False,
                    error_message="Conflict resolution failed",
                )

            if action == ConflictResolution.SKIPPED:
                self.logger.info(
                    "Conflict skip: destination already exists for %s",
                    source_path.name,
                )
                return OrganizationResult(
                    success=True,
                    organized_path=final_dest_path,
                    skipped=True,
                    metadata=metadata,
                )

            if not self.dry_run:
                final_dest_path.hardlink_to(source_path)

                link_registered = False
                try:
                    from src.link_registry import LinkRegistry

                    link_registry = LinkRegistry(
                        self.config.link_registry_path)
                    link_registered = link_registry.register_link(
                        source_path=source_path,
                        dest_path=final_dest_path,
                        metadata=metadata,
                    )
                    link_registry.close()
                except Exception as exc:
                    self.logger.error(
                        "Could not register link for %s: %s",
                        source_path.name,
                        exc,
                    )
                    return OrganizationResult(
                        success=False,
                        error_message=f"Link registry failure: {exc}",
                    )

                if not link_registered:
                    self.logger.error(
                        "Could not register link for %s: register_link returned false",
                        source_path.name,
                    )
                    return OrganizationResult(
                        success=False,
                        error_message="Link registry failure: register_link returned false",
                    )
            else:
                self.logger.info(f"[DRY RUN] Would link: {source_path.name}")

            if not self.dry_run:
                file_hash = self.calculate_file_hash(source_path)
                self.database.adicionar_midia(
                    file_hash=file_hash,
                    original_path=str(source_path),
                    organized_path=str(final_dest_path),
                    metadata=metadata,
                )
            else:
                self.logger.info(
                    "[DRY RUN] Would register database entry for: %s",
                    source_path.name,
                )

            return OrganizationResult(
                success=True,
                organized_path=final_dest_path,
                metadata=metadata,
            )

        except Exception as exc:
            self.logger.error(f"Error organizing {source_path.name}: {exc}")
            return OrganizationResult(
                success=False,
                error_message=str(exc),
            )

    async def organizar(self, file_path: Path) -> OrganizationResult:
        raise NotImplementedError

    def pode_processar(self, file_path: Path) -> bool:
        raise NotImplementedError

    def obter_tipo_midia(self) -> MediaType:
        raise NotImplementedError


class MusicOrganizer(BaseOrganizer):
    """Music organizer with metadata extraction and tag updates."""

    ENRICHABLE_FIELDS = (
        "musicbrainz_trackid",
        "genre",
        "isrc",
        "title",
        "artist",
        "album",
        "year",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.library_path = self.config.library_path_music
        self._online_cache: Dict[str, Dict[str, Any]] = {}

    def _extract_metadata_from_filename(
        self,
        file_path: Path,
        existing_title: Optional[str] = None,
        existing_artist: Optional[str] = None,
    ) -> Dict[str, Any]:
        filename = file_path.stem
        metadata: Dict[str, Any] = {}

        if " - " in filename:
            metadata = self._parse_filename_with_separator(
                filename, existing_title, existing_artist)
            if metadata:
                return metadata

        # No separator or couldn't parse with separator
        metadata["track_name"] = filename
        metadata["title"] = filename
        metadata["artist"] = "Unknown Artist"
        metadata["primary_artist"] = "Unknown Artist"
        return metadata

    def _parse_filename_with_separator(
        self,
        filename: str,
        existing_title: Optional[str],
        existing_artist: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Parse filename containing ' - ' separator.

        Supports both:
        1) Artist - Title (default)
        2) Title - Artist(s) (common in downloads)
        """
        def normalized_token(value: str) -> str:
            return re.sub(r"\s+", " ", (value or "").strip().lower())

        # First, check if filename starts with existing title
        title_prefix = (existing_title or "").strip()
        if title_prefix and filename.lower().startswith(f"{title_prefix.lower()} - "):
            inferred_artist = filename[len(title_prefix) + 3:].strip()
            if " - " in inferred_artist:
                inferred_artist = inferred_artist.rsplit(" - ", 1)[1].strip()
            if inferred_artist:
                return {
                    "artist": inferred_artist,
                    "primary_artist": self._get_primary_artist(inferred_artist),
                    "track_name": title_prefix,
                    "title": title_prefix,
                }

        # Parse as "left - right" separator pattern
        parts = filename.split(" - ", 1)
        if len(parts) != 2:
            return None

        left = parts[0].strip()
        right = parts[1].strip()
        reverse_parts = filename.rsplit(" - ", 1)
        left_last = reverse_parts[0].strip() if len(
            reverse_parts) == 2 else left
        right_last = reverse_parts[1].strip() if len(
            reverse_parts) == 2 else right

        title_hint = normalized_token(existing_title or "")
        left_norm = normalized_token(left)
        right_norm = normalized_token(right)
        left_last_norm = normalized_token(left_last)
        right_last_norm = normalized_token(right_last)
        existing_artist_norm = normalized_token(existing_artist or "")

        # Determine pattern: Title-Artist vs Artist-Title
        if (
            (title_hint and (left_norm ==
             title_hint or left_last_norm == title_hint))
            or (
                self._is_generic_artist_bucket(existing_artist_norm)
                and bool(right_last_norm)
            )
        ):
            return {
                "artist": right_last,
                "primary_artist": self._get_primary_artist(right_last),
                "track_name": left_last,
                "title": left_last,
            }

        return {
            "artist": left,
            "primary_artist": self._get_primary_artist(left),
            "track_name": right,
            "title": right,
        }

    def _get_primary_artist(self, artist_value: str) -> str:
        """Return a stable lead artist for folder routing.

        Preserves common duo connectors and reduces only true collaboration
        separators(comma, feat, ft, x, etc.).
        """
        if not artist_value:
            return "Unknown Artist"

        value = artist_value.strip()
        if not value:
            return "Unknown Artist"

        split_patterns = [
            ",",
            ";",
            " feat. ",
            " feat ",
            " featuring ",
            " ft. ",
            " ft ",
            " with ",
            " com ",
            " x ",
            " /",
        ]

        # Keep reducing while collaboration separators are present so mixed
        # patterns like "Artist A & Artist B, Artist C" end up as
        # "Artist A & Artist B" (duo preserved).
        lead = value
        changed = True
        while changed:
            changed = False
            lower_lead = lead.lower()
            for pattern in split_patterns:
                idx = lower_lead.find(pattern.lower())
                if idx > 0:
                    new_lead = lead[:idx].strip()
                    if new_lead and new_lead != lead:
                        lead = new_lead
                        changed = True
                    break

        return lead

    def _is_generic_artist_bucket(self, artist_value: Any) -> bool:
        if artist_value is None:
            return False
        normalized = str(artist_value).strip().lower()
        return normalized in {"various artists", "various artist", "various", "va"}

    def _read_audio_tags(self, file_path: Path) -> Dict[str, Any]:
        """
        Read Navidrome-compatible audio tags from file using Mutagen.

        Extracts: title, artist(s), album, album_artist, genre(s),
                  track number, disc number, year, compilation flag,
                  and online identifiers (MusicBrainz, ISRC).

        Returns dict with all available tags from file.
        """
        try:
            from mutagen import File

            audio = File(str(file_path), easy=True)
            tags = dict(audio.tags) if audio and audio.tags else {}

            def first_value(*keys: str) -> str:
                for key in keys:
                    value = tags.get(key)
                    if isinstance(value, list):
                        if value and str(value[0]).strip():
                            return str(value[0]).strip()
                    elif value is not None and str(value).strip():
                        return str(value).strip()
                return ""

            def all_values(*keys: str) -> List[str]:
                """Extract all values for given keys (comma-separated or repeated)."""
                results = []
                for key in keys:
                    value = tags.get(key)
                    if isinstance(value, list):
                        for v in value:
                            text = str(v).strip()
                            if text and text.lower() != "unknown":
                                results.append(text)
                    elif value is not None:
                        text = str(value).strip()
                        if text and text.lower() != "unknown":
                            results.append(text)
                # Also split comma-separated values (common in some editors)
                final = []
                for v in results:
                    for part in v.split(","):
                        part_clean = part.strip()
                        if part_clean:
                            final.append(part_clean)
                return list(dict.fromkeys(final))

            year_value = first_value("date", "year")
            track_value = first_value("tracknumber", "track")
            disc_value = first_value("discnumber", "disc")
            compilation_value = first_value("compilation", "tcmp")

            parsed_year: Optional[int] = None
            if year_value:
                year_candidate = year_value[:4]
                if year_candidate.isdigit():
                    parsed_year = int(year_candidate)

            artist_value = first_value("artist")
            album_artist_value = first_value("albumartist")
            all_artists = all_values("artist")
            all_genres = all_values("genre")

            primary_artist_value = self._get_primary_artist(
                album_artist_value or artist_value
            )

            return {
                "title": first_value("title"),
                "track_name": first_value("title"),
                "artist": artist_value or album_artist_value,
                "artists": all_artists,
                "album_artist": album_artist_value,
                "primary_artist": primary_artist_value,
                "album": first_value("album"),
                "genre": first_value("genre"),
                "genres": all_genres,
                "track_number": track_value,
                "disc_number": disc_value,
                "year": parsed_year,
                "date": year_value,
                "originaldate": first_value("originaldate", "originalyear"),
                "releasedate": first_value("releasedate", "releaseyear"),
                "compilation": compilation_value,
                "musicbrainz_trackid": first_value("musicbrainz_trackid"),
                "musicbrainz_albumid": first_value("musicbrainz_albumid"),
                "musicbrainz_releaseinfo": first_value("musicbrainz_releaseinfo"),
                "isrc": first_value("isrc"),
            }
        except Exception as exc:
            self.logger.debug(f"Could not read tags: {exc}")

        return {}

    def _is_missing(self, value: Any) -> bool:
        return self._is_missing_value(value, unknown_prefix=True)

    def _normalize_metadata_values(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        normalized = deepcopy(metadata)

        if self._is_missing(normalized.get("track_name")) and not self._is_missing(normalized.get("title")):
            normalized["track_name"] = normalized.get("title")

        if self._is_missing(normalized.get("title")) and not self._is_missing(normalized.get("track_name")):
            normalized["title"] = normalized.get("track_name")

        track_value = normalized.get("track_number")
        if isinstance(track_value, int):
            normalized["track_number"] = str(track_value)

        year_value = normalized.get("year")
        if isinstance(year_value, str):
            year_candidate = year_value.strip()[:4]
            if year_candidate.isdigit():
                normalized["year"] = int(year_candidate)
            elif year_value.strip() == "":
                normalized["year"] = None

        return normalized

    def _infer_genre_from_source_path(self, file_path: Path) -> Optional[str]:
        if not self.config.infer_genre_from_source_path:
            return None

        ignored = {
            "musics",
            "music",
            "downloads",
            "download",
            "library",
            "media",
        }

        for parent in file_path.parents:
            name = parent.name.strip()
            if not name:
                continue

            lowered = name.lower()
            if lowered in ignored:
                continue

            # Common bucket style: "#3 Eletronica" -> "Eletronica"
            normalized = re.sub(r"^#\d+\s*", "", name).strip()
            if normalized and normalized.lower() not in ignored and len(normalized) >= 3:
                return normalized

        return None

    def _merge_missing_fields(
        self,
        base_metadata: Dict[str, Any],
        fallback_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = self._merge_fields(
            deepcopy(base_metadata),
            fallback_metadata,
            is_missing=self._is_missing,
            overwrite=False,
        )

        if self._is_missing(merged.get("track_name")) and not self._is_missing(merged.get("title")):
            merged["track_name"] = merged.get("title")
        if self._is_missing(merged.get("title")) and not self._is_missing(merged.get("track_name")):
            merged["title"] = merged.get("track_name")

        return merged

    def _determine_final_metadata(
        self,
        existing_tags_metadata: Dict[str, Any],
        filename_metadata: Dict[str, Any],
        file_path: Path,
        online_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        final = {
            "artist": "Unknown Artist",
            "primary_artist": "Unknown Artist",
            "track_name": file_path.stem,
            "title": file_path.stem,
            "album": "Unknown Album",
            "genre": "Unknown",
            "track_number": None,
            "year": None,
            "musicbrainz_trackid": None,
            "isrc": None,
            "media_type": "music",
        }

        final = self._merge_missing_fields(
            final, self._normalize_metadata_values(existing_tags_metadata))

        if online_metadata:
            final = self._merge_missing_fields(
                final, self._normalize_metadata_values(online_metadata))

        final = self._merge_missing_fields(
            final, self._normalize_metadata_values(filename_metadata))

        self._resolve_primary_artist(final, filename_metadata)
        self._resolve_album(final)
        self._resolve_genre(final, file_path)

        return final

    def _resolve_primary_artist(
        self,
        final: Dict[str, Any],
        filename_metadata: Dict[str, Any],
    ) -> None:
        """Resolve primary_artist maintaining stable destination routing.

        If tags are generic (e.g., "Various Artists"), trust filename artist when available.
        """
        if self._is_missing(final.get("primary_artist")) or self._is_generic_artist_bucket(final.get("primary_artist")):
            filename_artist = str(
                filename_metadata.get("artist") or "").strip()
            if not self._is_missing(filename_artist) and not self._is_generic_artist_bucket(filename_artist):
                final["primary_artist"] = self._get_primary_artist(
                    filename_artist)
            else:
                final["primary_artist"] = self._get_primary_artist(
                    str(final.get("album_artist") or final.get("artist") or "")
                )

    def _resolve_album(
        self,
        final: Dict[str, Any],
    ) -> None:
        """Resolve album, preferring 'Singles' when artist known but album missing."""
        if self._is_missing(final.get("album")):
            if not self._is_missing(final.get("artist")):
                final["album"] = "Singles"
            else:
                final["album"] = "Unknown Album"

    def _resolve_genre(
        self,
        final: Dict[str, Any],
        file_path: Path,
    ) -> None:
        """Resolve genre, inferring from source path if necessary."""
        if self._is_missing(final.get("genre")):
            inferred_genre = self._infer_genre_from_source_path(file_path)
            if inferred_genre:
                final["genre"] = inferred_genre
                final.setdefault("genres", [inferred_genre])

    async def _fetch_online_music_metadata(
        self,
        file_path: Path,
        current_metadata: Dict[str, Any],
        needs_genre: bool,
    ) -> Dict[str, Any]:
        artist = (current_metadata.get("artist") or "").strip()
        title = (
            current_metadata.get("title")
            or current_metadata.get("track_name")
            or ""
        ).strip()

        if not artist or not title or artist.lower().startswith("unknown"):
            return {}

        cache_key = f"{artist.lower()}::{title.lower()}"
        cached = self._online_cache.get(cache_key)
        if cached is not None:
            return deepcopy(cached)

        enriched = await enrich_music_metadata_with_online_sources(
            file_path=file_path,
            existing_metadata={"artist": artist, "title": title},
            logger=self.logger,
            lastfm_api_key=self.config.lastfm_api_key,
            fetch_lastfm=needs_genre,
        )

        self._online_cache[cache_key] = deepcopy(enriched)
        return enriched

    def _calculate_missing_fields(
        self,
        metadata: Dict[str, Any],
    ) -> List[str]:
        return [
            field for field in self.ENRICHABLE_FIELDS
            if self._is_missing(metadata.get(field))
        ]

    def _update_audio_tags(
        self,
        file_path: Path,
        original_metadata: Dict[str, Any],
        final_metadata: Dict[str, Any],
        online_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update audio file tags with Navidrome-compatible metadata.

        Writes: title, artist, album_artist, album, genre, track_number,
                disc_number, year, compilation flag, and online identifiers.

        Supports: MP3 (ID3v2), FLAC/OGG/Opus (Vorbis), M4A, WMA.
        """
        try:
            ext = file_path.suffix.lower()
            changed_fields: Dict[str, Any] = {}

            def should_normalize_to_primary(value: Any) -> bool:
                if self._is_missing(value):
                    return True
                normalized = str(value).strip()
                if self._is_generic_artist_bucket(normalized):
                    return True
                return self._get_primary_artist(normalized) != normalized

            candidate_map = {
                "genre": (online_metadata or {}).get("genre")
                or (None if self._is_missing(final_metadata.get("genre")) else final_metadata.get("genre")),
                "musicbrainz_trackid": (online_metadata or {}).get("musicbrainz_trackid"),
                "musicbrainz_albumid": (online_metadata or {}).get("musicbrainz_albumid"),
                "isrc": (online_metadata or {}).get("isrc"),
                "title": (online_metadata or {}).get("title"),
                "artist": (online_metadata or {}).get("artist"),
                "album": (online_metadata or {}).get("album") or final_metadata.get("album"),
                "year": (online_metadata or {}).get("year"),
            }

            for field, candidate in candidate_map.items():
                if self._is_missing(original_metadata.get(field)) and not self._is_missing(candidate):
                    changed_fields[field] = candidate

            primary_artist = str(final_metadata.get(
                "primary_artist") or "").strip()
            if primary_artist and not self._is_missing(primary_artist):
                current_artist_value = original_metadata.get("artist")
                current_artist = str(current_artist_value or "").strip()
                if self._is_missing(current_artist_value) or should_normalize_to_primary(current_artist):
                    changed_fields["artist"] = primary_artist

                current_album_artist_value = (
                    original_metadata.get(
                        "album_artist") or original_metadata.get("artist")
                )
                current_album_artist = str(
                    current_album_artist_value or "").strip()
                if self._is_missing(current_album_artist_value) or should_normalize_to_primary(current_album_artist):
                    changed_fields["album_artist"] = primary_artist

            if not changed_fields:
                self.logger.debug(
                    "File already has normalized metadata or no updates needed: %s", file_path.name)
                return True

            if self.dry_run:
                self.logger.info(
                    "[DRY RUN] Would update %s with fields: %s",
                    file_path.name,
                    ", ".join(sorted(changed_fields.keys())),
                )
                return True

            if ext in {".flac", ".ogg", ".opus"}:
                from mutagen.flac import FLAC

                audio = FLAC(file_path)

                if "genre" in changed_fields:
                    audio["genre"] = [str(changed_fields["genre"])]
                if "musicbrainz_trackid" in changed_fields:
                    audio["musicbrainz_trackid"] = [
                        str(changed_fields["musicbrainz_trackid"])]
                if "musicbrainz_albumid" in changed_fields:
                    audio["musicbrainz_albumid"] = [
                        str(changed_fields["musicbrainz_albumid"])]
                if "isrc" in changed_fields:
                    audio["isrc"] = [str(changed_fields["isrc"])]
                if "title" in changed_fields:
                    audio["title"] = [str(changed_fields["title"])]
                if "artist" in changed_fields:
                    audio["artist"] = [str(changed_fields["artist"])]
                if "album_artist" in changed_fields:
                    audio["albumartist"] = [
                        str(changed_fields["album_artist"])]
                if "album" in changed_fields:
                    audio["album"] = [str(changed_fields["album"])]
                if "year" in changed_fields:
                    audio["date"] = [str(changed_fields["year"])]
                # Preserve disc number if exists
                if "disc_number" in original_metadata and original_metadata["disc_number"]:
                    audio["discnumber"] = [
                        str(original_metadata["disc_number"])]
                # Preserve compilation flag if exists
                if "compilation" in original_metadata and original_metadata["compilation"]:
                    audio["compilation"] = [
                        str(original_metadata["compilation"])]

                audio.save()
                self.logger.info("Updated tags (FLAC): %s | fields: %s",
                                 file_path.name, ", ".join(changed_fields.keys()))
                return True

            if ext == ".mp3":
                from mutagen.id3 import ID3, TALB, TDRC, TCON, TIT2, TPE1, TPE2, TSRC, TXXX, TPOS, TCMP

                audio = ID3(file_path)

                if "genre" in changed_fields:
                    audio["TCON"] = TCON(
                        encoding=3, text=str(changed_fields["genre"]))
                if "musicbrainz_trackid" in changed_fields:
                    audio["TXXX:MusicBrainz Track Id"] = TXXX(
                        encoding=3, desc="MusicBrainz Track Id",
                        text=str(changed_fields["musicbrainz_trackid"]),
                    )
                if "musicbrainz_albumid" in changed_fields:
                    audio["TXXX:MusicBrainz Album Id"] = TXXX(
                        encoding=3, desc="MusicBrainz Album Id",
                        text=str(changed_fields["musicbrainz_albumid"]),
                    )
                if "isrc" in changed_fields:
                    audio["TSRC"] = TSRC(
                        encoding=3, text=str(changed_fields["isrc"]))
                if "title" in changed_fields:
                    audio["TIT2"] = TIT2(
                        encoding=3, text=str(changed_fields["title"]))
                if "artist" in changed_fields:
                    audio["TPE1"] = TPE1(
                        encoding=3, text=str(changed_fields["artist"]))
                if "album_artist" in changed_fields:
                    audio["TPE2"] = TPE2(encoding=3, text=str(
                        changed_fields["album_artist"]))
                if "album" in changed_fields:
                    audio["TALB"] = TALB(
                        encoding=3, text=str(changed_fields["album"]))
                if "year" in changed_fields:
                    audio["TDRC"] = TDRC(
                        encoding=3, text=str(changed_fields["year"]))
                # Preserve disc number if exists
                if "disc_number" in original_metadata and original_metadata["disc_number"]:
                    audio["TPOS"] = TPOS(encoding=3, text=str(
                        original_metadata["disc_number"]))
                # Preserve compilation flag if exists
                if "compilation" in original_metadata and original_metadata["compilation"]:
                    audio["TCMP"] = TCMP(
                        encoding=3, text=original_metadata["compilation"])

                audio.save()
                self.logger.info("Updated tags (MP3): %s | fields: %s",
                                 file_path.name, ", ".join(changed_fields.keys()))
                return True

            if ext == ".m4a":
                from mutagen.mp4 import MP4

                audio = MP4(file_path)

                if "genre" in changed_fields:
                    audio["\xa9gen"] = [str(changed_fields["genre"])]
                if "title" in changed_fields:
                    audio["\xa9nam"] = [str(changed_fields["title"])]
                if "artist" in changed_fields:
                    audio["\xa9ART"] = [str(changed_fields["artist"])]
                if "album_artist" in changed_fields:
                    audio["aART"] = [str(changed_fields["album_artist"])]
                if "album" in changed_fields:
                    audio["\xa9alb"] = [str(changed_fields["album"])]
                if "year" in changed_fields:
                    audio["\xa9day"] = [str(changed_fields["year"])]
                if "isrc" in changed_fields:
                    audio["ISRC"] = [str(changed_fields["isrc"])]

                audio.save()
                self.logger.info("Updated tags (M4A): %s | fields: %s",
                                 file_path.name, ", ".join(changed_fields.keys()))
                return True

            self.logger.info(
                "Tag update not implemented for format %s (%s)", ext, file_path.name)
            return True
        except Exception as exc:
            self.logger.error(
                f"Failed to update tags for {file_path.name}: {exc}")
            return False

    async def organizar(self, file_path: Path) -> OrganizationResult:
        if self.database.is_file_organized(str(file_path)):
            return OrganizationResult(success=True, skipped=True)

        existing_meta = self._read_audio_tags(file_path)
        filename_meta = self._extract_metadata_from_filename(
            file_path,
            existing_title=existing_meta.get("title"),
            existing_artist=existing_meta.get("artist"),
        )

        baseline_meta = self._determine_final_metadata(
            existing_tags_metadata=existing_meta,
            filename_metadata=filename_meta,
            file_path=file_path,
        )
        baseline_dest = self.get_destination_path(file_path, baseline_meta)
        early_skip = self._early_skip_if_conflict(
            file_path,
            baseline_dest,
            baseline_meta,
        )
        if early_skip:
            return early_skip

        online_meta: Dict[str, Any] = {}
        if self.config.enrich_music_metadata_online:
            # Calculate against raw file tags; only true gaps should trigger lookups.
            missing_before_online = self._calculate_missing_fields(
                existing_meta)
            if missing_before_online:
                self.logger.info(
                    "Metadata enrichment start: %s | missing-targets=%s",
                    file_path.name,
                    ",".join(missing_before_online),
                )
                try:
                    online_meta = await asyncio.wait_for(
                        self._fetch_online_music_metadata(
                            file_path,
                            baseline_meta,
                            needs_genre=bool(
                                {"genre", "title", "artist", "album"}.intersection(
                                    missing_before_online
                                )
                            ),
                        ),
                        timeout=20.0,
                    )
                    self.logger.info(
                        "Metadata enrichment done: %s", file_path.name)
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "Metadata enrichment timed out for %s; continuing without online data",
                        file_path.name,
                    )
            else:
                self.logger.info(
                    "Metadata enrichment skipped (no gaps): %s",
                    file_path.name,
                )

        final_meta = self._determine_final_metadata(
            existing_tags_metadata=existing_meta,
            filename_metadata=filename_meta,
            file_path=file_path,
            online_metadata=online_meta,
        )

        final_dest = self.get_destination_path(file_path, final_meta)
        if final_dest != baseline_dest:
            early_skip = self._early_skip_if_conflict(
                file_path,
                final_dest,
                final_meta,
            )
            if early_skip:
                return early_skip

        self._update_audio_tags(file_path, existing_meta,
                                final_meta, online_meta)

        return await self.organizar_file(file_path, final_dest, final_meta)

    def pode_processar(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in AUDIO_EXTS

    def obter_tipo_midia(self) -> MediaType:
        return MediaType.MUSIC

    def get_destination_path(self, file_path: Path, metadata: Dict[str, Any]) -> Path:
        artist_value = metadata.get("primary_artist") or metadata.get(
            "artist", "Unknown Artist")
        artist = self.sanitize_author(artist_value)

        album_value = metadata.get("album")
        if self._is_missing(album_value):
            album = "Singles" if not self._is_missing(
                artist_value) else "Unknown Album"
        else:
            album = self.sanitize_title(str(album_value))

        track_name = self.sanitize_title(
            metadata.get("track_name", file_path.stem))
        track_number = metadata.get("track_number")

        file_name = f"{track_name}{file_path.suffix}"
        if track_number:
            try:
                numeric_track = int(str(track_number).split("/")[0])
                if 1 <= numeric_track <= 99:
                    file_name = f"{numeric_track:02d} - {track_name}{file_path.suffix}"
            except (ValueError, TypeError):
                pass

        return self.library_path / artist / album / file_name


class LyricsOrganizer(BaseOrganizer):
    """Lyrics organizer for sidecar `.lrc` files."""

    AUDIO_EXTS = AUDIO_EXTS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reuse music destination logic for unmatched DB cases.
        self.music_helper = MusicOrganizer(*args, **kwargs)
        self.library_path = self.config.library_path_music

    def pode_processar(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".lrc"

    def obter_tipo_midia(self) -> MediaType:
        return MediaType.LYRICS

    def _find_audio_pairs(self, lyrics_file: Path) -> List[Path]:
        return [
            lyrics_file.with_suffix(ext)
            for ext in self.AUDIO_EXTS
            if lyrics_file.with_suffix(ext).exists()
        ]

    def _dest_from_existing_audio_record(self, lyrics_file: Path) -> Optional[Path]:
        for audio_file in self._find_audio_pairs(lyrics_file):
            record = self.database.get_record_by_original_path(str(audio_file))
            if not record:
                continue

            organized_audio = Path(record.get("organized_path", ""))
            if not organized_audio:
                continue

            return organized_audio.with_suffix(lyrics_file.suffix)

        return None

    def _dest_from_audio_metadata(self, lyrics_file: Path) -> Optional[Path]:
        for audio_file in self._find_audio_pairs(lyrics_file):
            filename_meta = self.music_helper._extract_metadata_from_filename(
                audio_file)
            existing_meta = self.music_helper._read_audio_tags(audio_file)
            final_meta = self.music_helper._determine_final_metadata(
                existing_tags_metadata=existing_meta,
                filename_metadata=filename_meta,
                file_path=audio_file,
                online_metadata=None,
            )
            audio_dest = self.music_helper.get_destination_path(
                audio_file, final_meta)
            return audio_dest.with_suffix(lyrics_file.suffix)

        return None

    def _fallback_dest(self, lyrics_file: Path) -> Path:
        # Use content hash so equal unmatched lyrics collapse to one canonical file.
        lyrics_hash = self.calculate_file_hash(lyrics_file)[:16]
        return self.library_path / "_lyrics_unmatched" / f"{lyrics_hash}.lrc"

    async def organizar(self, file_path: Path) -> OrganizationResult:
        if self.database.is_file_organized(str(file_path)):
            return OrganizationResult(success=True, skipped=True)

        paired_audio = self._find_audio_pairs(file_path)

        dest_path = (
            self._dest_from_existing_audio_record(file_path)
            or self._dest_from_audio_metadata(file_path)
            or self._fallback_dest(file_path)
        )

        metadata: Dict[str, Any] = {
            "media_type": "lyrics",
            "media_subtype": "lyrics_lrc",
            "paired_audio_count": len(paired_audio),
            "paired_audio_candidates": [str(path) for path in paired_audio[:3]],
            "fallback_unmatched": len(paired_audio) == 0,
            "source_name": file_path.name,
        }

        return await self.organizar_file(file_path, dest_path, metadata)


class BookOrganizer(BaseOrganizer):
    """Book organizer supporting books and comics."""

    BOOK_ENRICHABLE_FIELDS = (
        "genre",
        "subjects",
        "series",
        "series_index",
        "description",
        "language",
        "publisher",
        "isbn",
        "year",
        "rating",
    )

    def __init__(self, *args, book_type: str = "book", **kwargs):
        super().__init__(*args, **kwargs)
        self.book_type = book_type

        if book_type == "comic":
            self.library_path = self.config.library_path_comics
        else:
            self.library_path = self.config.library_path_books

        if self.config.calibre_enabled:
            self.calibre_manager = CalibreManager(
                self.config.calibre_library_path)
        else:
            self.calibre_manager = None

    def _normalize_book_genre(self, value: Any) -> Optional[str]:
        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        text = re.sub(r"^\d+\.\s*", "", text)
        text = re.split(r"\s+\d+\.\s+", text)[0].strip()

        for separator in ["|", ";", "/", ","]:
            if separator in text:
                text = text.split(separator)[0].strip()

        if re.search(r"\s[-–—]\s", text):
            text = re.split(r"\s[-–—]\s", text, maxsplit=1)[0].strip()

        cleaned = self.sanitize_title(text)
        return cleaned if cleaned and cleaned != "Untitled" else None

    def _normalize_subject_list(self, value: Any) -> List[str]:
        if value is None:
            return []

        if isinstance(value, (list, tuple, set)):
            raw_values = list(value)
        else:
            raw_values = [value]

        normalized: List[str] = []
        for item in raw_values:
            text = str(item).strip()
            if not text:
                continue
            cleaned = self.sanitize_title(text)
            if cleaned and cleaned not in normalized and cleaned != "Untitled":
                normalized.append(cleaned)

        return normalized

    def _extract_epub_embedded_metadata(self, file_path: Path) -> Dict[str, Any]:
        if file_path.suffix.lower() != ".epub":
            return {}

        try:
            from ebooklib import epub

            book = epub.read_epub(str(file_path), options={"ignore_ncx": True})

            def _first_dc(field: str) -> Optional[str]:
                values = book.get_metadata("DC", field)
                if not values:
                    return None
                text = str(values[0][0]).strip()
                return text if text else None

            creator_entries = book.get_metadata("DC", "creator") or []
            title_entries = book.get_metadata("DC", "title") or []
            creators_by_id: Dict[str, str] = {}
            titles_by_id: Dict[str, str] = {}
            for idx, entry in enumerate(creator_entries):
                value = str(entry[0] or "").strip() if entry else ""
                attrs = entry[1] if len(entry) > 1 and isinstance(
                    entry[1], dict) else {}
                if not value:
                    continue
                creator_id = str(attrs.get("id") or f"creator-{idx}").strip()
                if creator_id:
                    creators_by_id[creator_id] = value

            for idx, entry in enumerate(title_entries):
                value = str(entry[0] or "").strip() if entry else ""
                attrs = entry[1] if len(entry) > 1 and isinstance(
                    entry[1], dict) else {}
                if not value:
                    continue
                title_id = str(attrs.get("id") or f"title-{idx}").strip()
                if title_id:
                    titles_by_id[title_id] = value

            people_roles: Dict[str, str] = {}
            collection_name: Optional[str] = None
            collection_order: Any = None
            role_mapping = {
                "aut": "author",
                "art": "artist",
                "trl": "translator",
                "edt": "editor",
                "ill": "illustrator",
                "clr": "colorist",
            }

            subjects_raw = [entry[0] for entry in (
                book.get_metadata("DC", "subject") or []) if entry]
            subjects = self._normalize_subject_list(subjects_raw)

            series = None
            series_index = None
            collection_values: Dict[str, str] = {}
            collection_positions: Dict[str, Any] = {}
            for entry in book.get_metadata("OPF", "meta") or []:
                attrs = entry[1] if len(entry) > 1 else {}
                if not isinstance(attrs, dict):
                    continue
                name = str(attrs.get("name", "")).strip().lower()
                prop = str(attrs.get("property", "")).strip().lower()
                refines = str(attrs.get("refines", "")).strip().lstrip("#")
                meta_id = str(attrs.get("id", "")).strip()
                content = str(attrs.get("content", "")).strip()
                if not content and len(entry) > 0:
                    content = str(entry[0] or "").strip()
                if not content:
                    continue
                if name == "calibre:series":
                    series = content
                elif name == "calibre:series_index":
                    try:
                        series_index = float(content)
                    except ValueError:
                        series_index = content
                elif prop == "belongs-to-collection":
                    if meta_id:
                        collection_values[meta_id] = content
                    elif series is None:
                        # Fallback when id is absent: use first collection as series.
                        series = content
                elif prop == "group-position" and refines:
                    try:
                        collection_positions[refines] = float(content)
                    except ValueError:
                        collection_positions[refines] = content
                elif prop == "role" and refines:
                    role_key = content.strip().lower()[:3]
                    mapped = role_mapping.get(role_key)
                    person = creators_by_id.get(refines)
                    if mapped and person and mapped not in people_roles:
                        people_roles[mapped] = person
                elif prop == "title-type" and refines and content.strip().lower() == "collection":
                    title_value = titles_by_id.get(refines)
                    if title_value:
                        collection_name = title_value
                elif prop == "display-seq" and refines:
                    title_value = titles_by_id.get(refines)
                    if title_value and (collection_name is None or collection_name == title_value):
                        collection_name = title_value
                        try:
                            collection_order = float(content)
                        except ValueError:
                            collection_order = content

            if series is None and collection_values:
                first_key = next(iter(collection_values.keys()))
                series = collection_values[first_key]
            if series_index is None and collection_values and collection_positions:
                first_key = next(iter(collection_values.keys()))
                if first_key in collection_positions:
                    series_index = collection_positions[first_key]

            metadata: Dict[str, Any] = {
                "title": _first_dc("title"),
                "author": _first_dc("creator"),
                "publisher": _first_dc("publisher"),
                "language": _first_dc("language"),
                "description": _first_dc("description"),
                "isbn": _first_dc("identifier"),
                "subjects": subjects,
                "series": series,
                "series_index": series_index,
                "rating": _first_dc("rating"),
                "collection": collection_name,
                "collection_order": collection_order,
            }

            metadata.update(people_roles)

            if subjects and not metadata.get("genre"):
                metadata["genre"] = self._normalize_book_genre(subjects[0])

            if _first_dc("date"):
                year_match = re.search(r"(\d{4})", str(_first_dc("date")))
                if year_match:
                    metadata["year"] = int(year_match.group(1))

            return {k: v for k, v in metadata.items() if v not in (None, "", [], {})}
        except Exception as exc:
            self.logger.debug(
                "Could not read embedded EPUB metadata for %s: %s",
                file_path.name,
                exc,
            )
            return {}

    def _extract_calibre_book_metadata(self, file_path: Path) -> Dict[str, Any]:
        # Reliable local extraction for EPUB/PDF/MOBI metadata.
        # Uses calibre ebook-meta output, including series and series_index.
        if file_path.suffix.lower() not in {".epub", ".pdf", ".mobi", ".azw", ".azw3"}:
            return {}

        if not shutil.which("ebook-meta"):
            return {}

        try:
            result = subprocess.run(
                ["ebook-meta", str(file_path)],
                capture_output=True,
                text=True,
                timeout=45,
            )
            if result.returncode != 0:
                return {}

            data: Dict[str, str] = {}
            for line in (result.stdout or "").splitlines():
                match = re.match(r"^\s*([^:]+?)\s*:\s*(.*)$", line)
                if not match:
                    continue
                key = match.group(1).strip().lower()
                value = match.group(2).strip()
                if value:
                    data[key] = value

            metadata: Dict[str, Any] = {}

            title = data.get("title")
            if title:
                metadata["title"] = title

            author = data.get("author(s)") or data.get("authors")
            if author:
                metadata["author"] = author.split("&", 1)[0].strip()

            if data.get("publisher"):
                metadata["publisher"] = data["publisher"]
            if data.get("comments"):
                metadata["description"] = data["comments"]

            language_raw = data.get("languages") or data.get("language")
            if language_raw:
                metadata["language"] = language_raw.split(",", 1)[0].strip()

            tags = data.get("tags")
            if tags:
                subjects = [t.strip() for t in tags.split(",") if t.strip()]
                if subjects:
                    metadata["subjects"] = subjects
                    metadata["genre"] = subjects[0]

            identifiers = data.get("identifiers")
            if identifiers:
                isbn_match = re.search(
                    r"isbn:([^,\s]+)", identifiers, re.IGNORECASE)
                if isbn_match:
                    metadata["isbn"] = isbn_match.group(1).strip()

            published = data.get("published")
            if published:
                year_match = re.search(r"(\d{4})", published)
                if year_match:
                    metadata["year"] = int(year_match.group(1))

            rating = data.get("rating")
            if rating:
                try:
                    metadata["rating"] = float(rating)
                except ValueError:
                    metadata["rating"] = rating

            series_raw = data.get("series")
            if series_raw:
                # ebook-meta commonly prints: "Series Name [2.0]"
                series_match = re.match(r"^(.*?)\s*\[(.+)\]\s*$", series_raw)
                if series_match:
                    metadata["series"] = series_match.group(1).strip()
                    index_text = series_match.group(2).strip()
                    try:
                        metadata["series_index"] = float(index_text)
                    except ValueError:
                        metadata["series_index"] = index_text
                else:
                    metadata["series"] = series_raw

            if "series_index" not in metadata and data.get("series index"):
                index_text = data["series index"].strip()
                try:
                    metadata["series_index"] = float(index_text)
                except ValueError:
                    metadata["series_index"] = index_text

            return {k: v for k, v in metadata.items() if v not in (None, "", [], {})}
        except Exception as exc:
            self.logger.debug(
                "Could not extract calibre metadata for %s: %s",
                file_path.name,
                exc,
            )
            return {}

    def _is_missing_book_field(self, value: Any) -> bool:
        return self._is_missing_value(
            value,
            unknown_values={"unknown", "unknown author"},
            treat_empty_collections=True,
        )

    def _merge_missing_book_fields(
        self,
        base: Dict[str, Any],
        fallback: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self._merge_book_fields(base, fallback, overwrite=False)

    def _merge_book_fields(
        self,
        base: Dict[str, Any],
        incoming: Dict[str, Any],
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        merged = self._merge_fields(
            base,
            {k: v for k, v in incoming.items() if k != "subjects"},
            is_missing=self._is_missing_book_field,
            overwrite=overwrite,
        )

        self._merge_book_subjects(merged, incoming, overwrite)
        self._infer_genre_from_subjects(merged)

        return merged

    def _merge_book_subjects(
        self,
        merged: Dict[str, Any],
        incoming: Dict[str, Any],
        overwrite: bool,
    ) -> None:
        """Merge subjects list, avoiding duplicates."""
        incoming_subjects = self._normalize_subject_list(
            incoming.get("subjects"))
        if not incoming_subjects:
            return

        if overwrite:
            merged["subjects"] = incoming_subjects
        else:
            existing = self._normalize_subject_list(merged.get("subjects"))
            combined = existing[:]
            for subject in incoming_subjects:
                if subject not in combined:
                    combined.append(subject)
            if combined:
                merged["subjects"] = combined

    def _infer_genre_from_subjects(
        self,
        merged: Dict[str, Any],
    ) -> None:
        """Infer book genre from subjects when genre is missing."""
        if self._is_missing_book_field(merged.get("genre")):
            subjects = self._normalize_subject_list(merged.get("subjects"))
            if subjects:
                genre = self._normalize_book_genre(subjects[0])
                if genre:
                    merged["genre"] = genre

    def _finalize_book_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        finalized = dict(metadata)

        genre = self._normalize_book_genre(finalized.get("genre"))
        if genre:
            finalized["genre"] = genre

        subjects = self._normalize_subject_list(finalized.get("subjects"))
        if subjects:
            finalized["subjects"] = subjects

        if self._is_missing_book_field(finalized.get("series")):
            finalized.pop("series", None)
            finalized.pop("series_index", None)

        year_value = finalized.get("year")
        if isinstance(year_value, str):
            year_match = re.search(r"(\d{4})", year_value)
            if year_match:
                finalized["year"] = int(year_match.group(1))

        return finalized

    def _book_has_embedded_cover(self, file_path: Path) -> Optional[bool]:
        """Return True/False when ebook-meta can determine cover state."""
        try:
            check = subprocess.run(
                ["which", "ebook-meta"], capture_output=True)
            if check.returncode != 0:
                return None

            probe = subprocess.run(
                ["ebook-meta", str(file_path)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if probe.returncode != 0:
                return None

            for line in probe.stdout.splitlines():
                cleaned = line.strip().lower()
                if cleaned.startswith("has cover"):
                    if ":" in cleaned:
                        value = cleaned.split(":", 1)[1].strip()
                        if value in {"yes", "true", "1"}:
                            return True
                        if value in {"no", "false", "0"}:
                            return False

            # Fallback for calibre variants that do not print "Has cover".
            # We attempt extraction and infer state from output size.
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp_path = Path(tmp.name)
            tmp.close()
            try:
                extract = subprocess.run(
                    ["ebook-meta", str(file_path),
                     "--get-cover", str(tmp_path)],
                    capture_output=True,
                    timeout=30,
                )
                if extract.returncode == 0 and tmp_path.exists() and tmp_path.stat().st_size > 0:
                    return True
                return False
            finally:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
        except Exception:
            return None

    def _download_cover_temp_file(self, cover_url: str) -> Optional[Path]:
        if self._is_missing_book_field(cover_url):
            return None

        try:
            request = urllib.request.Request(
                str(cover_url),
                headers={"User-Agent": "media-organizer/1.0"},
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                content_type = (response.headers.get(
                    "Content-Type") or "").lower()
                if content_type and not content_type.startswith("image/"):
                    self.logger.debug(
                        "Skipping non-image cover response for %s: %s",
                        cover_url,
                        content_type,
                    )
                    return None

                image_bytes = response.read()
                if not image_bytes:
                    return None

            suffix = ".jpg"
            if "png" in content_type:
                suffix = ".png"
            elif "webp" in content_type:
                suffix = ".webp"

            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix)
            temp_path = Path(temp_file.name)
            temp_file.write(image_bytes)
            temp_file.close()
            return temp_path
        except Exception as exc:
            self.logger.debug(
                "Could not download cover from %s: %s", cover_url, exc)
            return None

    def _write_epub_metadata(self, file_path: Path, metadata: Dict[str, Any]) -> bool:
        if file_path.suffix.lower() != ".epub":
            return False

        fields_to_write = {
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "publisher": metadata.get("publisher"),
            "language": metadata.get("language"),
            "description": metadata.get("description"),
            "isbn": metadata.get("isbn"),
            "genre": metadata.get("genre"),
            "subjects": metadata.get("subjects"),
            "series": metadata.get("series"),
            "series_index": metadata.get("series_index"),
            "year": metadata.get("year"),
            "rating": metadata.get("rating"),
            "collection": metadata.get("collection"),
            "collection_order": metadata.get("collection_order"),
        }
        wants_cover_only_update = (
            self.config.book_cover_update_enabled
            and not self._is_missing_book_field(metadata.get("cover_image_url"))
            and self._book_has_embedded_cover(file_path) is False
        )
        if all(self._is_missing_book_field(value) for value in fields_to_write.values()) and not wants_cover_only_update:
            return False

        if self.dry_run:
            changed = [k for k, v in fields_to_write.items(
            ) if not self._is_missing_book_field(v)]
            if (
                self.config.book_cover_update_enabled
                and not self._is_missing_book_field(metadata.get("cover_image_url"))
            ):
                changed.append("cover")
            self.logger.info(
                "[DRY RUN] Would update EPUB metadata for %s: %s",
                file_path.name,
                ", ".join(changed),
            )
            return True

        try:
            # Prefer calibre's ebook-meta because it updates metadata without
            # rebuilding the EPUB package structure (safer for Kavita parser).
            check = subprocess.run(
                ["which", "ebook-meta"], capture_output=True)
            if check.returncode == 0:
                cmd: List[str] = ["ebook-meta", str(file_path)]
                cover_temp_path: Optional[Path] = None

                if not self._is_missing_book_field(fields_to_write["title"]):
                    cmd.extend(["--title", str(fields_to_write["title"])])
                if not self._is_missing_book_field(fields_to_write["author"]):
                    cmd.extend(["--authors", str(fields_to_write["author"])])
                if not self._is_missing_book_field(fields_to_write["publisher"]):
                    cmd.extend(
                        ["--publisher", str(fields_to_write["publisher"])])
                if not self._is_missing_book_field(fields_to_write["language"]):
                    cmd.extend(
                        ["--language", str(fields_to_write["language"])])
                if not self._is_missing_book_field(fields_to_write["description"]):
                    cmd.extend(
                        ["--comments", str(fields_to_write["description"])])
                if not self._is_missing_book_field(fields_to_write["isbn"]):
                    cmd.extend(["--isbn", str(fields_to_write["isbn"])])
                if not self._is_missing_book_field(fields_to_write["year"]):
                    cmd.extend(["--date", f"{fields_to_write['year']}-01-01"])
                if not self._is_missing_book_field(fields_to_write["rating"]):
                    cmd.extend(["--rating", str(fields_to_write["rating"])])

                subjects = self._normalize_subject_list(
                    fields_to_write["subjects"])
                genre = self._normalize_book_genre(fields_to_write["genre"])
                if genre and genre not in subjects:
                    subjects.insert(0, genre)
                if subjects:
                    cmd.extend(["--tags", ", ".join(subjects)])

                series = fields_to_write["series"]
                series_index = fields_to_write["series_index"]
                if not self._is_missing_book_field(series):
                    cmd.extend(["--series", str(series).strip()])
                if not self._is_missing_book_field(series_index):
                    cmd.extend(["--index", str(series_index).strip()])

                # Only update cover when enabled and file has no embedded cover.
                if self.config.book_cover_update_enabled:
                    cover_state = self._book_has_embedded_cover(file_path)
                    if cover_state is False:
                        cover_temp_path = self._download_cover_temp_file(
                            str(metadata.get("cover_image_url") or "")
                        )
                        if cover_temp_path:
                            cmd.extend(["--cover", str(cover_temp_path)])

                try:
                    run = subprocess.run(cmd, capture_output=True, text=True)
                    if run.returncode == 0:
                        self.logger.info(
                            "Updated EPUB metadata for %s (ebook-meta)", file_path.name)
                        return True

                    self.logger.warning(
                        "ebook-meta failed for %s: %s",
                        file_path.name,
                        (run.stderr or run.stdout or "unknown error").strip(),
                    )
                finally:
                    if cover_temp_path and cover_temp_path.exists():
                        cover_temp_path.unlink(missing_ok=True)

            # Legacy fallback (opt-in): ebooklib rebuild can break EPUB3 NAV.
            if not self.config.epub_rewrite_with_ebooklib:
                self.logger.warning(
                    "Skipping ebooklib rewrite for %s. Set EPUB_REWRITE_WITH_EBOOKLIB=true to force legacy mode.",
                    file_path.name,
                )
                return False

            from ebooklib import epub

            book = epub.read_epub(str(file_path), options={"ignore_ncx": True})

            def set_dc(name: str, value: Optional[str]) -> None:
                if self._is_missing_book_field(value):
                    return
                namespace = "http://purl.org/dc/elements/1.1/"
                if hasattr(book, "metadata") and namespace in book.metadata:
                    book.metadata[namespace][name] = []
                book.add_metadata("DC", name, str(value).strip())

            set_dc("title", fields_to_write["title"])
            set_dc("creator", fields_to_write["author"])
            set_dc("publisher", fields_to_write["publisher"])
            set_dc("language", fields_to_write["language"])
            set_dc("description", fields_to_write["description"])
            if not self._is_missing_book_field(fields_to_write["isbn"]):
                set_dc("identifier", str(fields_to_write["isbn"]))
            if not self._is_missing_book_field(fields_to_write["year"]):
                set_dc("date", f"{fields_to_write['year']}-01-01")
            if not self._is_missing_book_field(fields_to_write["rating"]):
                set_dc("rating", str(fields_to_write["rating"]))

            subjects = self._normalize_subject_list(
                fields_to_write["subjects"])
            genre = self._normalize_book_genre(fields_to_write["genre"])
            if genre and genre not in subjects:
                subjects.insert(0, genre)
            if subjects:
                namespace = "http://purl.org/dc/elements/1.1/"
                if hasattr(book, "metadata") and namespace in book.metadata:
                    book.metadata[namespace]["subject"] = []
                for subject in subjects:
                    book.add_metadata("DC", "subject", subject)

            series = fields_to_write["series"]
            series_index = fields_to_write["series_index"]
            if not self._is_missing_book_field(series):
                book.add_metadata("OPF", "meta", "", {
                    "name": "calibre:series",
                    "content": str(series).strip(),
                })
                # EPUB3-compatible series grouping used by Kavita.
                book.add_metadata("OPF", "meta", str(series).strip(), {
                    "property": "belongs-to-collection",
                    "id": "series-collection",
                })
                if not self._is_missing_book_field(series_index):
                    book.add_metadata("OPF", "meta", "", {
                        "name": "calibre:series_index",
                        "content": str(series_index).strip(),
                    })
                    book.add_metadata("OPF", "meta", str(series_index).strip(), {
                        "property": "group-position",
                        "refines": "#series-collection",
                    })

            collection = fields_to_write.get("collection")
            collection_order = fields_to_write.get("collection_order")
            if not self._is_missing_book_field(collection):
                book.add_metadata("DC", "title", str(collection).strip(), {
                    "id": "collection-title",
                })
                book.add_metadata("OPF", "meta", "collection", {
                    "refines": "#collection-title",
                    "property": "title-type",
                })
                if not self._is_missing_book_field(collection_order):
                    book.add_metadata("OPF", "meta", str(collection_order).strip(), {
                        "refines": "#collection-title",
                        "property": "display-seq",
                    })

            epub.write_epub(str(file_path), book)
            self.logger.info(
                "Updated EPUB metadata for %s (ebooklib fallback)", file_path.name)
            return True
        except Exception as exc:
            self.logger.warning(
                "Could not update EPUB metadata for %s: %s",
                file_path.name,
                exc,
            )
            return False

    def _write_pdf_metadata(self, file_path: Path, metadata: Dict[str, Any]) -> bool:
        # Write PDF XMP metadata through calibre ebook-meta.
        # Kavita reads these fields for PDF organization.
        if file_path.suffix.lower() != ".pdf":
            return False

        # Verify ebook-meta is available
        check = subprocess.run(
            ["which", "ebook-meta"], capture_output=True
        )
        if check.returncode != 0:
            self.logger.debug(
                "ebook-meta not available; skipping PDF metadata write for %s",
                file_path.name,
            )
            return False

        cmd: List[str] = ["ebook-meta", str(file_path)]
        cover_temp_path: Optional[Path] = None

        # Map metadata fields to ebook-meta flags
        if not self._is_missing_book_field(metadata.get("title")):
            cmd.extend(["--title", str(metadata["title"])])
        if not self._is_missing_book_field(metadata.get("author")):
            cmd.extend(["--authors", str(metadata["author"])])
        if not self._is_missing_book_field(metadata.get("publisher")):
            cmd.extend(["--publisher", str(metadata["publisher"])])
        if not self._is_missing_book_field(metadata.get("description")):
            cmd.extend(["--comments", str(metadata["description"])])
        if not self._is_missing_book_field(metadata.get("language")):
            cmd.extend(["--language", str(metadata["language"])])
        if not self._is_missing_book_field(metadata.get("isbn")):
            cmd.extend(["--isbn", str(metadata["isbn"])])
        if not self._is_missing_book_field(metadata.get("series")):
            cmd.extend(["--series", str(metadata["series"])])
        if not self._is_missing_book_field(metadata.get("series_index")):
            cmd.extend(["--index", str(metadata["series_index"])])
        if not self._is_missing_book_field(metadata.get("year")):
            cmd.extend(["--date", f"{metadata['year']}-01-01"])
        if not self._is_missing_book_field(metadata.get("rating")):
            cmd.extend(["--rating", str(metadata["rating"])])

        if self.config.book_cover_update_enabled:
            cover_state = self._book_has_embedded_cover(file_path)
            if cover_state is False:
                cover_temp_path = self._download_cover_temp_file(
                    str(metadata.get("cover_image_url") or "")
                )
                if cover_temp_path:
                    cmd.extend(["--cover", str(cover_temp_path)])

        subjects = self._normalize_subject_list(metadata.get("subjects"))
        genre = self._normalize_book_genre(metadata.get("genre"))
        if genre and genre not in subjects:
            subjects.insert(0, genre)
        if subjects:
            cmd.extend(["--tags", ",".join(subjects)])

        # Nothing to update
        if len(cmd) == 2:
            return False

        if self.dry_run:
            changed = [cmd[i]
                       for i in range(2, len(cmd)) if cmd[i].startswith("--")]
            self.logger.info(
                "[DRY RUN] Would update PDF metadata for %s: %s",
                file_path.name,
                ", ".join(changed),
            )
            return True

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode == 0:
                self.logger.info("Updated PDF metadata for %s", file_path.name)
                return True
            self.logger.warning(
                "ebook-meta failed for %s: %s",
                file_path.name,
                result.stderr.decode("utf-8", errors="replace"),
            )
            return False
        except Exception as exc:
            self.logger.warning(
                "Could not update PDF metadata for %s: %s",
                file_path.name,
                exc,
            )
            return False
        finally:
            if cover_temp_path and cover_temp_path.exists():
                cover_temp_path.unlink(missing_ok=True)

    def _read_comicinfo_xml(self, file_path: Path) -> Dict[str, Any]:
        """Read ComicInfo.xml from a CBZ(ZIP) archive.

        Kavita uses ComicInfo.xml(v2.1 schema) as the canonical metadata source
        for comics and manga. This method extracts all relevant fields.
        """
        ext = file_path.suffix.lower()
        if ext not in {".cbz", ".cbr"}:
            return {}

        def _parse_comicinfo_xml(raw: bytes) -> Dict[str, Any]:
            import xml.etree.ElementTree as ET

            root = ET.fromstring(raw)

            def get_text(tag: str) -> Optional[str]:
                el = root.find(tag)
                return el.text.strip() if el is not None and el.text else None

            year_str = get_text("Year")
            year = int(year_str) if year_str and year_str.isdigit() else None

            result: Dict[str, Any] = {
                "title": get_text("Series"),
                "chapter_title": get_text("Title"),
                "localized_series": get_text("LocalizedSeries"),
                "series_sort": get_text("SeriesSort"),
                "issue_number": get_text("Number"),
                "page_count": get_text("PageCount"),
                "count": get_text("Count"),
                "volume": get_text("Volume"),
                "alternative_series": get_text("AlternativeSeries"),
                "alternative_count": get_text("AlternativeCount"),
                "publisher": get_text("Publisher"),
                "imprint": get_text("Imprint"),
                "year": year,
                "month": get_text("Month"),
                "day": get_text("Day"),
                "description": get_text("Summary"),
                "genre": get_text("Genre"),
                "tags": get_text("Tags"),
                "author": get_text("Writer"),
                "penciller": get_text("Penciller"),
                "inker": get_text("Inker"),
                "colorist": get_text("Colorist"),
                "letterer": get_text("Letterer"),
                "cover_artist": get_text("CoverArtist"),
                "editor": get_text("Editor"),
                "translator": get_text("Translator"),
                "language": get_text("LanguageISO"),
                "isbn": get_text("GTIN"),
                "story_arc": get_text("StoryArc"),
                "story_arc_number": get_text("StoryArcNumber"),
                "age_rating": get_text("AgeRating"),
                "series_group": get_text("SeriesGroup"),
                "format": get_text("Format"),
                "web": get_text("Web"),
            }
            return {k: v for k, v in result.items() if v is not None}

        try:
            if ext == ".cbz":
                import zipfile

                with zipfile.ZipFile(str(file_path), "r") as zf:
                    names = zf.namelist()
                    # Case-insensitive lookup; must be at root of archive
                    ci_name = next(
                        (n for n in names if n.lower() == "comicinfo.xml"), None
                    )
                    if not ci_name:
                        return {}

                    with zf.open(ci_name) as f:
                        return _parse_comicinfo_xml(f.read())
            else:
                # CBR (RAR): read ComicInfo.xml using unrar/7z without conversion.
                listing_cmd = None
                if shutil.which("unrar"):
                    listing_cmd = ["unrar", "lb", str(file_path)]
                elif shutil.which("7z"):
                    listing_cmd = ["7z", "l", "-ba", str(file_path)]
                if not listing_cmd:
                    return {}

                listing = subprocess.run(
                    listing_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if listing.returncode != 0:
                    return {}

                names = [ln.strip() for ln in (
                    listing.stdout or "").splitlines() if ln.strip()]
                ci_name = next(
                    (n for n in names if n.lower().endswith("comicinfo.xml")), None)
                if not ci_name:
                    return {}

                if shutil.which("unrar"):
                    read_cmd = ["unrar", "p", "-inul", str(file_path), ci_name]
                else:
                    read_cmd = ["7z", "x", "-so", str(file_path), ci_name]

                content = subprocess.run(
                    read_cmd,
                    capture_output=True,
                    timeout=30,
                )
                if content.returncode != 0 or not content.stdout:
                    return {}
                return _parse_comicinfo_xml(content.stdout)
        except Exception as exc:
            self.logger.debug(
                "Could not read ComicInfo.xml from %s: %s",
                file_path.name,
                exc,
            )
            return {}

    def _read_comicinfo_sidecar(self, file_path: Path) -> Dict[str, Any]:
        """Read sidecar metadata in `.comicinfo.xml` format.

        Supported names:
        - `<archive>.comicinfo.xml`
        - `.comicinfo.xml` in the same folder (folder-level fallback)
        """
        candidates = [
            file_path.parent / f"{file_path.stem}.comicinfo.xml",
            file_path.parent / ".comicinfo.xml",
        ]
        existing = next(
            (p for p in candidates if p.exists() and p.is_file()), None)
        if not existing:
            return {}

        try:
            # Reuse the same parser by feeding sidecar content as raw XML bytes.
            import xml.etree.ElementTree as ET

            raw = existing.read_bytes()
            root = ET.fromstring(raw)

            def get_text(tag: str) -> Optional[str]:
                el = root.find(tag)
                return el.text.strip() if el is not None and el.text else None

            year_str = get_text("Year")
            year = int(year_str) if year_str and year_str.isdigit() else None
            result: Dict[str, Any] = {
                "title": get_text("Series"),
                "chapter_title": get_text("Title"),
                "localized_series": get_text("LocalizedSeries"),
                "series_sort": get_text("SeriesSort"),
                "issue_number": get_text("Number"),
                "page_count": get_text("PageCount"),
                "count": get_text("Count"),
                "volume": get_text("Volume"),
                "alternative_series": get_text("AlternativeSeries"),
                "alternative_count": get_text("AlternativeCount"),
                "publisher": get_text("Publisher"),
                "imprint": get_text("Imprint"),
                "year": year,
                "month": get_text("Month"),
                "day": get_text("Day"),
                "description": get_text("Summary"),
                "genre": get_text("Genre"),
                "tags": get_text("Tags"),
                "author": get_text("Writer"),
                "penciller": get_text("Penciller"),
                "inker": get_text("Inker"),
                "colorist": get_text("Colorist"),
                "letterer": get_text("Letterer"),
                "cover_artist": get_text("CoverArtist"),
                "editor": get_text("Editor"),
                "translator": get_text("Translator"),
                "language": get_text("LanguageISO"),
                "isbn": get_text("GTIN"),
                "story_arc": get_text("StoryArc"),
                "story_arc_number": get_text("StoryArcNumber"),
                "age_rating": get_text("AgeRating"),
                "series_group": get_text("SeriesGroup"),
                "format": get_text("Format"),
                "web": get_text("Web"),
            }
            return {k: v for k, v in result.items() if v is not None}
        except Exception as exc:
            self.logger.debug(
                "Could not read sidecar .comicinfo.xml for %s: %s",
                file_path.name,
                exc,
            )
            return {}

    def _write_comicinfo_sidecar(self, file_path: Path, xml_content: str) -> bool:
        """Write a per-archive sidecar in Kavita-compatible `.comicinfo.xml` format."""
        sidecar_path = file_path.parent / f"{file_path.stem}.comicinfo.xml"
        if self.dry_run:
            self.logger.info(
                "[DRY RUN] Would write sidecar %s", sidecar_path.name)
            return True

        try:
            sidecar_path.write_text(xml_content, encoding="utf-8")
            self.logger.info("Written sidecar %s", sidecar_path.name)
            return True
        except Exception as exc:
            self.logger.warning(
                "Could not write sidecar .comicinfo.xml for %s: %s",
                file_path.name,
                exc,
            )
            return False

    def _write_comicinfo_xml(self, file_path: Path, metadata: Dict[str, Any]) -> bool:
        """Write or update ComicInfo.xml inside a comic archive.

        Kavita reads ComicInfo.xml for comic metadata.
        - CBZ: writes directly via zipfile.
        - CBR: attempts in-place update via archive tools (no format conversion).
        """
        ext = file_path.suffix.lower()
        if ext not in {".cbz", ".cbr"}:
            return False

        def _esc(text: str) -> str:
            return (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        def _tag(name: str, value: Any) -> str:
            if value is None or str(value).strip() == "":
                return ""
            return f"  <{name}>{_esc(str(value).strip())}</{name}>\n"

        xml_lines = [
            '<?xml version="1.0" encoding="utf-8"?>\n',
            '<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
            ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n',
            _tag("Title", metadata.get("chapter_title")),
            _tag("Series", metadata.get("title")),
            _tag("LocalizedSeries", metadata.get("localized_series")),
            _tag("SeriesSort", metadata.get("series_sort")),
            _tag("Number", metadata.get("issue_number")),
            _tag("PageCount", metadata.get("page_count")),
            _tag("Count", metadata.get("count")),
            _tag("Volume", metadata.get("volume")),
            _tag("AlternativeSeries", metadata.get("alternative_series")),
            _tag("AlternativeCount", metadata.get("alternative_count")),
            _tag("Summary", metadata.get("description")),
            _tag("Year", metadata.get("year")),
            _tag("Month", metadata.get("month")),
            _tag("Day", metadata.get("day")),
            _tag("Publisher", metadata.get("publisher")),
            _tag("Imprint", metadata.get("imprint")),
            _tag("Writer", metadata.get("author")),
            _tag("Penciller", metadata.get("penciller")),
            _tag("Inker", metadata.get("inker")),
            _tag("Colorist", metadata.get("colorist")),
            _tag("Letterer", metadata.get("letterer")),
            _tag("CoverArtist", metadata.get("cover_artist")),
            _tag("Editor", metadata.get("editor")),
            _tag("Translator", metadata.get("translator")),
            _tag("Genre", metadata.get("genre")),
            _tag("Tags", metadata.get("tags")),
            _tag("LanguageISO", metadata.get("language")),
            _tag("GTIN", metadata.get("isbn")),
            _tag("Web", metadata.get("web")),
            _tag("StoryArc", metadata.get("story_arc")),
            _tag("StoryArcNumber", metadata.get("story_arc_number")),
            _tag("SeriesGroup", metadata.get("series_group")),
            _tag("Format", metadata.get("format")),
            _tag("AgeRating", metadata.get("age_rating")),
            "</ComicInfo>\n",
        ]
        xml_content = "".join(ln for ln in xml_lines if ln)

        if self.dry_run:
            self.logger.info(
                "[DRY RUN] Would write ComicInfo.xml to %s", file_path.name
            )
            return True

        try:
            import zipfile

            temp_path = Path(tempfile.mktemp(
                suffix=file_path.suffix, dir=file_path.parent))
            cover_temp_path: Optional[Path] = None
            cover_archive_name: Optional[str] = None
            if self.config.comic_download_covers:
                cover_temp_path = self._download_cover_temp_file(
                    str(metadata.get("cover_image_url") or "")
                )
                if cover_temp_path:
                    cover_archive_name = f"0000_cover{cover_temp_path.suffix.lower() or '.jpg'}"

            if ext == ".cbz":
                with zipfile.ZipFile(str(file_path), "r") as src, zipfile.ZipFile(
                    str(temp_path), "w", zipfile.ZIP_DEFLATED
                ) as dst:
                    if cover_temp_path and cover_archive_name:
                        dst.write(str(cover_temp_path), cover_archive_name)
                    for item in src.infolist():
                        if item.filename.lower() != "comicinfo.xml":
                            if cover_archive_name and item.filename.lower() == cover_archive_name.lower():
                                continue
                            dst.writestr(item, src.read(item.filename))
                    dst.writestr("ComicInfo.xml", xml_content.encode("utf-8"))

                shutil.move(str(temp_path), str(file_path))
                self.logger.info("Written ComicInfo.xml to %s", file_path.name)
                return True

            # CBR update path (without conversion): requires writable archive tool.
            tool_cmd: Optional[List[str]] = None
            if shutil.which("rar"):
                tool_cmd = ["rar", "a", "-idq", "-ep",
                            str(file_path), "ComicInfo.xml"]
            elif shutil.which("7z"):
                # 7z may not support updating RAR depending on build; best-effort only.
                tool_cmd = ["7z", "u", str(file_path), "ComicInfo.xml"]

            if not tool_cmd:
                self.logger.warning(
                    "Skipping ComicInfo write for %s: no writable CBR tool (rar/7z update)",
                    file_path.name,
                )
                return self._write_comicinfo_sidecar(file_path, xml_content)

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_dir_path = Path(tmp_dir)
                comicinfo_path = tmp_dir_path / "ComicInfo.xml"
                comicinfo_path.write_text(xml_content, encoding="utf-8")

                cmd = tool_cmd[:]
                if cmd[0] == "rar":
                    cmd = ["rar", "a", "-idq", "-ep",
                           str(file_path), str(comicinfo_path)]
                    if cover_temp_path and cover_archive_name:
                        cover_dest = tmp_dir_path / cover_archive_name
                        shutil.copy2(str(cover_temp_path), str(cover_dest))
                        cmd.append(str(cover_dest))
                else:
                    cmd = ["7z", "u", str(file_path), str(comicinfo_path)]
                    if cover_temp_path and cover_archive_name:
                        cover_dest = tmp_dir_path / cover_archive_name
                        shutil.copy2(str(cover_temp_path), str(cover_dest))
                        cmd.append(str(cover_dest))

                run = subprocess.run(cmd, capture_output=True, timeout=120)
                if run.returncode != 0:
                    self.logger.warning(
                        "Could not write ComicInfo.xml to CBR %s: %s",
                        file_path.name,
                        (run.stderr.decode("utf-8", errors="replace")
                         if run.stderr else "tool failed"),
                    )
                    return self._write_comicinfo_sidecar(file_path, xml_content)

                self.logger.info("Written ComicInfo.xml to %s", file_path.name)
                return True
        except Exception as exc:
            self.logger.warning(
                "Could not write ComicInfo.xml to %s: %s",
                file_path.name,
                exc,
            )
            self._write_comicinfo_sidecar(file_path, xml_content)
            if "temp_path" in dir() and temp_path.exists():
                temp_path.unlink(missing_ok=True)
            return False
        finally:
            if "cover_temp_path" in dir() and cover_temp_path and cover_temp_path.exists():
                cover_temp_path.unlink(missing_ok=True)

    async def _enrich_book_metadata_if_needed(
        self,
        file_path: Path,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        updated = dict(metadata)
        overwrite_with_online = (
            self.config.book_metadata_trust_mode == "replace_with_online"
        )

        # When overwrite mode is enabled, avoid trusting embedded/local fields.
        # Keep filename-derived metadata as base and let online provider rewrite.
        if not overwrite_with_online:
            embedded_metadata = self._extract_epub_embedded_metadata(file_path)
            updated = self._merge_missing_book_fields(
                updated, embedded_metadata)

            calibre_metadata = self._extract_calibre_book_metadata(file_path)
            updated = self._merge_missing_book_fields(
                updated, calibre_metadata)

        missing_fields = [
            field for field in self.BOOK_ENRICHABLE_FIELDS
            if self._is_missing_book_field(updated.get(field))
        ]
        needs_cover_lookup = False
        if self.config.book_cover_update_enabled:
            cover_state = self._book_has_embedded_cover(file_path)
            needs_cover_lookup = cover_state is False

        if (
            (missing_fields or needs_cover_lookup or overwrite_with_online)
            and self.config.enrich_book_metadata
            and self.config.enrich_book_metadata_online
        ):
            online_metadata = await enrich_book_metadata_with_online_sources(
                file_path=file_path,
                existing_metadata=dict(updated),
                logger=self.logger,
                use_google_books=self.config.enrich_book_metadata_google_books,
                google_books_min_match_score=self.config.book_cover_min_match_score,
                google_books_api_key=self.config.google_books_api_key,
                include_cover_url=needs_cover_lookup,
            )
            if isinstance(online_metadata, dict):
                updated = self._merge_book_fields(
                    updated,
                    online_metadata,
                    overwrite=overwrite_with_online,
                )
                if overwrite_with_online:
                    self.logger.info(
                        "Applied online-trusted overwrite for book metadata: %s",
                        file_path.name,
                    )
            else:
                self.logger.debug(
                    "Ignoring non-dict online metadata for %s",
                    file_path.name,
                )

        return self._finalize_book_metadata(updated)

    def _detect_book_type(self, file_path: Path) -> str:
        ext = file_path.suffix.lower()
        if ext in {".cbz", ".cbr", ".cb7", ".cbt"}:
            return "comic"
        return "book"

    def _extract_book_metadata(self, file_path: Path) -> Dict[str, Any]:
        from src.utils import normalize_title

        filename = file_path.stem
        working_name = filename
        metadata: Dict[str, Any] = {
            "title": normalize_title(filename),
            "author": "Unknown Author",
            "authors": [],
            "year": None,
            "media_type": "book",
            "media_subtype": "book",
        }

        # Optional explicit series marker in filename:
        #   Author - Title [Series;Index] (Year)
        #   Author - Title [Series] (Year)
        # The last [] block is interpreted as series metadata only when
        # it appears after the title section and before optional year.
        series_block_match = re.search(
            r"\s\[([^\[\]]+)\]\s*(?:\(\d{4}\))?\s*$", working_name)
        if series_block_match:
            series_block = series_block_match.group(1).strip()
            parts = [p.strip() for p in series_block.split(";", 1)]
            if parts and parts[0]:
                metadata["series"] = normalize_title(parts[0])

            if len(parts) == 2 and parts[1]:
                index_raw = parts[1]
                try:
                    metadata["series_index"] = float(index_raw)
                except ValueError:
                    metadata["series_index"] = index_raw

            # Remove series marker from filename before author/title parsing
            working_name = re.sub(
                r"\s\[[^\[\]]+\]\s*(?:\(\d{4}\))?\s*$", "", working_name).strip()

            # Re-append year for normal year extraction path below
            year_suffix = re.search(r"\((\d{4})\)\s*$", filename)
            if year_suffix:
                working_name = f"{working_name} ({year_suffix.group(1)})"

        year_match = re.search(r"\((\d{4})\)", working_name)
        if year_match:
            metadata["year"] = int(year_match.group(1))

        if " - " in working_name:
            parts = working_name.split(" - ", 1)
            if len(parts) == 2:
                raw_author = parts[0].strip()
                # Support comma-separated multiple authors
                authors = [a.strip()
                           for a in raw_author.split(",") if a.strip()]
                metadata["authors"] = authors
                # First author used for folder path; full string kept for display
                metadata["author"] = authors[0] if authors else raw_author
                # Strip year from title — already captured in metadata["year"]
                title_part = re.sub(
                    r"\s*\(\d{4}\)\s*", "", parts[1].strip()).strip()
                metadata["title"] = normalize_title(title_part)

        return metadata

    def _extract_comic_metadata(self, file_path: Path) -> Dict[str, Any]:
        from src.utils import normalize_comic_filename

        series, issue, publisher, year = normalize_comic_filename(
            file_path.stem)

        base: Dict[str, Any] = {
            "title": series or "Unknown Series",
            "issue_number": issue,
            "publisher": publisher or "Unknown",
            "year": year,
            "media_type": "comic",
            "media_subtype": "comic",
        }

        # Prefer embedded ComicInfo.xml, with sidecar fallback when available.
        embedded = self._read_comicinfo_xml(file_path)
        if not embedded:
            embedded = self._read_comicinfo_sidecar(file_path)
        if embedded:
            for key, value in embedded.items():
                if not self._is_missing_book_field(value):
                    base[key] = value

        return base

    def get_book_destination_path(self, file_path: Path, metadata: Dict[str, Any]) -> Path:
        author = self.sanitize_author(metadata.get("author", "Unknown Author"))
        # Keep all books under a stable author folder; avoid creating one folder per file.
        return self.library_path / author / file_path.name

    def get_comic_destination_path(self, file_path: Path, metadata: Dict[str, Any]) -> Path:
        series = self.sanitize_title(metadata.get("title", "Unknown Series"))
        issue = metadata.get("issue_number")

        if issue:
            file_name = f"{series} #{issue}{file_path.suffix}"
        else:
            file_name = file_path.name

        # Keep comics grouped by series only; year differences should not split folders.
        return self.library_path / series / file_name

    async def organizar(self, file_path: Path) -> OrganizationResult:
        if self.database.is_file_organized(str(file_path)):
            return OrganizationResult(success=True, skipped=True)

        detected_type = self._detect_book_type(file_path)
        final_type = self.book_type if self.book_type != "book" else detected_type

        if final_type == "comic":
            metadata = self._extract_comic_metadata(file_path)
            dest_path = self.get_comic_destination_path(file_path, metadata)
            early_skip = self._early_skip_if_conflict(
                file_path, dest_path, metadata)
            if early_skip:
                return early_skip
            self._write_comicinfo_xml(file_path, metadata)
        else:
            metadata = self._extract_book_metadata(file_path)

            baseline_dest = self.get_book_destination_path(file_path, metadata)
            early_skip = self._early_skip_if_conflict(
                file_path,
                baseline_dest,
                metadata,
            )
            if early_skip:
                return early_skip

            metadata = await self._enrich_book_metadata_if_needed(file_path, metadata)
            dest_path = self.get_book_destination_path(file_path, metadata)
            if dest_path != baseline_dest:
                early_skip = self._early_skip_if_conflict(
                    file_path, dest_path, metadata)
                if early_skip:
                    return early_skip

            ext = file_path.suffix.lower()
            if ext == ".epub":
                self._write_epub_metadata(file_path, metadata)
            elif ext == ".pdf":
                self._write_pdf_metadata(file_path, metadata)

        return await self.organizar_file(file_path, dest_path, metadata)

    def pode_processar(self, file_path: Path) -> bool:
        if self.book_type == "comic":
            return file_path.suffix.lower() in COMIC_EXTS
        return file_path.suffix.lower() in (BOOK_EXTS | COMIC_EXTS)

    def obter_tipo_midia(self) -> MediaType:
        if self.book_type == "comic":
            return MediaType.COMIC
        return MediaType.BOOK


class CalibreManager:
    """Calibre integration for metadata management."""

    def __init__(self, library_path: Optional[Path] = None):
        self.library_path = library_path
        self.enabled = library_path is not None and library_path.exists()

    def add_book(self, book_path: Path, metadata: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False

        try:
            cmd = ["calibredb", "add", str(book_path)]
            if self.library_path:
                cmd.extend(["--library-path", str(self.library_path)])

            result = subprocess.run(cmd, capture_output=True, timeout=60)
            return result.returncode == 0
        except Exception:
            return False

    def update_metadata(self, book_path: Path, metadata: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False

        try:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=book_path.suffix, delete=False) as tmp:
                temp_path = Path(tmp.name)

            cmd = ["ebook-convert", str(book_path), str(temp_path)]

            if metadata.get("title"):
                cmd.extend(["--title", metadata["title"]])
            if metadata.get("author"):
                cmd.extend(["--authors", metadata["author"]])

            result = subprocess.run(cmd, capture_output=True, timeout=120)

            if result.returncode == 0:
                shutil.move(str(temp_path), str(book_path))
                return True

            temp_path.unlink(missing_ok=True)
            return False
        except Exception:
            return False

    def search_books(self, query: str) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []

        try:
            cmd = ["calibredb", "list", "--search", query, "--as-json"]
            if self.library_path:
                cmd.extend(["--library-path", str(self.library_path)])

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("books", [])
            return []
        except Exception:
            return []


class RenamerOrganizer(BaseOrganizer):
    """Renamer organizer for music, books, and comics."""

    AUDIO_EXTS = {".mp3", ".flac", ".m4a",
                  ".ogg", ".opus", ".aac", ".wav", ".m4b"}
    BOOK_EXTS = {".epub", ".pdf", ".mobi", ".azw", ".azw3"}
    COMIC_EXTS = {".cbz", ".cbr", ".cb7", ".cbt"}

    def pode_processar(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        return ext in (self.AUDIO_EXTS | self.BOOK_EXTS | self.COMIC_EXTS)

    def obter_tipo_midia(self) -> MediaType:
        return MediaType.RENAMER

    async def organizar(self, file_path: Path) -> OrganizationResult:
        metadata = self._extract_metadata_from_context(file_path)
        if not metadata:
            return OrganizationResult(
                success=False,
                error_message="Could not determine rename pattern",
            )

        new_name = self._build_new_name(file_path, metadata)
        dest_path = file_path.parent / new_name

        if file_path == dest_path:
            return OrganizationResult(
                success=True,
                organized_path=dest_path,
                skipped=True,
                metadata=metadata,
            )

        final_dest, _ = self.conflict_handler.resolve(
            file_path, dest_path, self.dry_run)

        if final_dest is None:
            return OrganizationResult(
                success=False,
                error_message="Conflict resolution failed",
            )

        if not self.dry_run:
            file_path.rename(final_dest)
            self.logger.info(f"Renamed: {file_path.name} -> {final_dest.name}")

            file_hash = self.calculate_file_hash(final_dest)
            self.database.adicionar_midia(
                file_hash=file_hash,
                original_path=str(file_path),
                organized_path=str(final_dest),
                metadata=metadata,
            )
        else:
            self.logger.info(
                f"[DRY-RUN] Would rename: {file_path.name} -> {final_dest.name}")

        return OrganizationResult(
            success=True,
            organized_path=final_dest,
            metadata=metadata,
        )

    def _extract_metadata_from_context(self, file_path: Path) -> Optional[Dict[str, Any]]:
        import os

        rename_type = os.getenv("RENAMER_TYPE", "music")
        title = os.getenv("RENAMER_TITLE", file_path.stem)
        year = int(os.getenv("RENAMER_YEAR", "2024"))
        track = int(os.getenv("RENAMER_TRACK", "1"))
        issue = int(os.getenv("RENAMER_ISSUE", "1"))
        author = os.getenv("RENAMER_AUTHOR", "")

        return {
            "type": rename_type,
            "title": title,
            "year": year,
            "track": track,
            "issue": issue,
            "author": author,
        }

    def _build_new_name(self, file_path: Path, metadata: Dict[str, Any]) -> str:
        ext = file_path.suffix
        title = self.sanitize_title(metadata["title"])

        if metadata["type"] == "music":
            track_fmt = f"{metadata['track']:02d}"
            return f"{track_fmt} - {title}{ext}"

        if metadata["type"] == "book":
            author = self.sanitize_author(metadata.get("author", "Unknown"))
            return f"{author} - {title} ({metadata['year']}){ext}"

        if metadata["type"] == "comic":
            issue_fmt = f"#{metadata['issue']:03d}"
            return f"{title} {issue_fmt}{ext}"

        return file_path.name

    def rename_batch(self, folder: Path, metadata: Dict[str, Any]) -> Dict[str, int]:
        import os

        stats = {"processed": 0, "renamed": 0, "failed": 0, "skipped": 0}

        os.environ["RENAMER_TYPE"] = metadata.get("type", "music")
        os.environ["RENAMER_TITLE"] = metadata.get("title", "")
        os.environ["RENAMER_YEAR"] = str(metadata.get("year", 2024))
        os.environ["RENAMER_TRACK"] = str(metadata.get("track", 1))
        os.environ["RENAMER_ISSUE"] = str(metadata.get("issue", 1))
        os.environ["RENAMER_AUTHOR"] = metadata.get("author", "")

        extensions = self.AUDIO_EXTS | self.BOOK_EXTS | self.COMIC_EXTS
        files: List[Path] = []
        for ext in extensions:
            files.extend(folder.glob(f"*{ext}"))
            files.extend(folder.glob(f"*{ext.upper()}"))

        for file in files:
            stats["processed"] += 1
            result = asyncio.run(self.organizar(file))

            if result.success:
                if result.skipped:
                    stats["skipped"] += 1
                else:
                    stats["renamed"] += 1
            else:
                stats["failed"] += 1

        return stats
