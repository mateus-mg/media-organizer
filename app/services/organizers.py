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
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, cast

from app.config import Config
from app.core import MediaType, OrganizadorInterface, OrganizationResult
from app.features.genre_guard import load_genre_exceptions, load_musical_keywords, sanitize_genre_values
from app.infrastructure.link_registry import LinkRegistry
from app.config.constants import AUDIO_EXTS, BOOK_EXTS, COMIC_EXTS, IMAGE_EXTS
from app.metadata.metadata import (
    enrich_book_metadata_with_online_sources,
    enrich_music_metadata_with_online_sources,
)
from app.utils.helpers import (
    ConflictResolution,
    calculate_file_hash,
    normalize_comic_series_title,
    parse_book_filename_fields,
    parse_comic_filename_fields,
)
from app.utils.value_utils import is_missing_value


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
        self._link_registry: Optional[LinkRegistry] = None

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

        return self._handle_conflict_skip(
            source_path=source_path,
            dest_path=final_dest_path or dest_path,
            metadata=metadata,
            early_skip=True,
        )

    def _paths_are_content_equivalent(self, source_path: Path, dest_path: Path) -> bool:
        """Return True when source and destination represent the same content."""
        try:
            if not source_path.exists() or not dest_path.exists():
                return False

            if source_path.samefile(dest_path):
                return True

            source_stat = source_path.stat()
            dest_stat = dest_path.stat()

            if source_stat.st_size != dest_stat.st_size:
                return False

            if (
                source_stat.st_ino == dest_stat.st_ino
                and source_stat.st_dev == dest_stat.st_dev
            ):
                return True

            # Fallback for non-hardlink duplicates with same size.
            source_hash = self.calculate_file_hash(source_path)
            dest_hash = self.calculate_file_hash(dest_path)
            return bool(source_hash and source_hash == dest_hash)
        except Exception:
            return False

    def _register_existing_source_mapping(
        self,
        source_path: Path,
        dest_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Register source->destination mapping without counting as new organized media."""
        try:
            if self.database.get_record_by_original_path(str(source_path)):
                return True

            media_table = getattr(self.database, "media_table", None)
            if media_table is None:
                return False

            from tinydb import Query

            Media = Query()
            destination_record = media_table.get(
                Media.organized_path == str(dest_path)
            )

            record_metadata = dict(metadata or {})
            if not record_metadata and isinstance(destination_record, dict):
                record_metadata = dict(
                    destination_record.get("metadata") or {})

            file_hash = ""
            if isinstance(destination_record, dict):
                file_hash = str(destination_record.get(
                    "file_hash") or "").strip()
            if not file_hash:
                file_hash = self.calculate_file_hash(source_path)

            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            media_table.insert(
                {
                    "file_hash": file_hash,
                    "original_path": str(source_path),
                    "organized_path": str(dest_path),
                    "processed_date": now,
                    "last_checked": now,
                    "file_exists": True,
                    "hardlink_created": False,
                    "metadata": record_metadata,
                    "errors": [],
                }
            )

            if self.database.backup_enabled:
                self.database.create_backup_if_needed()

            try:
                link_registry = self._get_link_registry()
                link_registry.register_link(
                    source_path=source_path,
                    dest_path=dest_path,
                    metadata=record_metadata,
                )
            except Exception as exc:
                self.logger.warning(
                    "Conflict mapping registered but link registry update failed for %s: %s",
                    source_path.name,
                    exc,
                )

            return True
        except Exception as exc:
            self.logger.error(
                "Could not register existing conflict mapping for %s: %s",
                source_path.name,
                exc,
            )
            return False

    def _handle_conflict_skip(
        self,
        source_path: Path,
        dest_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
        early_skip: bool = False,
    ) -> OrganizationResult:
        equivalent = self._paths_are_content_equivalent(source_path, dest_path)
        reason = "conflict_destination_exists"

        if equivalent:
            reason = "conflict_destination_already_organized"
            if not self.dry_run:
                registered = self._register_existing_source_mapping(
                    source_path=source_path,
                    dest_path=dest_path,
                    metadata=metadata,
                )
                if not registered:
                    reason = "conflict_destination_exists"

        if early_skip:
            self.logger.info(
                "Early skip before metadata update: source=%s destination=%s reason=%s",
                str(source_path),
                str(dest_path),
                reason,
            )
        else:
            self.logger.info(
                "Conflict skip: source=%s destination=%s reason=%s",
                str(source_path),
                str(dest_path),
                reason,
            )
        return OrganizationResult(
            success=True,
            organized_path=dest_path,
            skipped=True,
            skip_reason=reason,
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
                    skip_reason="already_registered_in_database",
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
                return self._handle_conflict_skip(
                    source_path=source_path,
                    dest_path=final_dest_path,
                    metadata=metadata,
                    early_skip=False,
                )

            if not self.dry_run:
                final_dest_path.hardlink_to(source_path)

                link_registered = False
                try:
                    link_registry = self._get_link_registry()
                    link_registered = link_registry.register_link(
                        source_path=source_path,
                        dest_path=final_dest_path,
                        metadata=metadata,
                    )
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

    def _get_link_registry(self) -> LinkRegistry:
        if self._link_registry is None:
            self._link_registry = LinkRegistry(self.config.link_registry_path)
        return self._link_registry

    def close(self):
        if self._link_registry is not None:
            self._link_registry.close()
            self._link_registry = None

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

    GENERIC_GENRE_HINTS = {
        "pop",
        "rock",
        "metal",
        "jazz",
        "blues",
        "house",
        "techno",
        "trance",
        "edm",
        "electro",
        "electronic",
        "dance",
        "disco",
        "rap",
        "hip hop",
        "hip-hop",
        "trap",
        "r&b",
        "rnb",
        "soul",
        "funk",
        "reggae",
        "reggaeton",
        "country",
        "folk",
        "classical",
        "ambient",
        "instrumental",
        "indie",
        "alternative",
        "garage",
        "hardcore",
        "gospel",
        "christian",
        "worship",
        "easy listening",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.library_path = self.config.library_path_music
        self._online_cache: Dict[str, Dict[str, Any]] = {}
        self._genre_lexicon: Optional[set[str]] = None
        database_path = getattr(
            self.config, "database_path", "data/organization.json")
        self._genre_enrichment_retry_queue_path = (
            Path(database_path).parent / "genre_enrichment_retry_queue.json"
        )
        # Tracks whether the last tag-write call actually changed on-disk tags.
        self._last_audio_tag_write_had_changes: bool = False

    def _normalize_artist_name(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)

        # Keep mixed-case stylistic names and acronyms as authored.
        if any(ch.islower() for ch in text) and any(ch.isupper() for ch in text):
            return text
        if text.isupper() and len(text) <= 5:
            return text

        return text.title()

    def _canonicalize_artist_alias(self, value: Any) -> str:
        """Canonicalize known artist alias punctuation variants.

        Keeps names like "fun." intact and only normalizes known suffix forms
        that create duplicate folders, such as "Jr."/"Sr.".
        """
        text = self._normalize_artist_name(value)
        if not text:
            return ""
        return re.sub(r"\b(Jr|Sr)\.$", r"\1", text, flags=re.IGNORECASE)

    def _normalize_album_name(self, album: str) -> str:
        """Normalize album names by cleaning spacing and unsafe characters only.

        Does not remove subtitles like Deluxe, Remix, Edition, and similar.
        Keeps valid characters such as: ()-:

        Examples:
            "Purpose  (Deluxe)" -> "Purpose (Deluxe)"
            "Believe   (Deluxe   Edition)" -> "Believe (Deluxe Edition)"
            "My   Worlds" -> "My Worlds"
            "Never Say Never: The Remixes" -> "Never Say Never: The Remixes"
        """
        if not album:
            return "Unknown Album"

        album = album.strip()

        # Remove only problematic characters and keep ()-: intact.
        for char in '<>"/\\|?*':
            album = album.replace(char, '')

        # Normalize repeated spaces.
        album = re.sub(r'\s+', ' ', album).strip()

        # Remove extra spaces inside parentheses.
        album = re.sub(r'\(\s+', '(', album)
        album = re.sub(r'\s+\)', ')', album)

        # Normalize spacing around colons.
        album = re.sub(r'\s*:\s*', ': ', album).strip()

        return album if album else "Unknown Album"

    def _extract_release_year(self, metadata: Dict[str, Any]) -> Optional[int]:
        year_value = metadata.get("year")
        if isinstance(year_value, int):
            return year_value
        if isinstance(year_value, str):
            year_candidate = year_value.strip()[:4]
            if year_candidate.isdigit():
                return int(year_candidate)

        for key in ("date", "originaldate", "releasedate"):
            raw_value = metadata.get(key)
            if not raw_value:
                continue
            year_candidate = str(raw_value).strip()[:4]
            if year_candidate.isdigit():
                return int(year_candidate)
        return None

    def _parse_numeric_tag_value(self, value: Any) -> Optional[int]:
        """Parse tags like '3', '03', or '3/12' into an integer value."""
        text = str(value or "").strip()
        if not text:
            return None
        match = re.match(r"^(\d+)(?:\s*/\s*\d+)?$", text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _normalize_track_number_for_compare(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        numeric_value = self._parse_numeric_tag_value(text)
        if numeric_value is not None:
            return str(numeric_value)

        return text

    def _extract_track_from_filename(self, file_path: Path) -> Optional[int]:
        """Extract leading track index from file names like '03 - Song Name.flac'."""
        stem = str(file_path.stem or "").strip()
        match = re.match(r"^(\d{1,3})\s*[-_.\s]", stem)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _has_legacy_year_tag(self, file_path: Path) -> bool:
        """Return True when file still contains legacy YEAR tag that should be removed."""
        ext = file_path.suffix.lower()
        if ext not in {".flac", ".ogg", ".opus"}:
            return False
        try:
            from mutagen import File as MutagenFile

            audio = MutagenFile(file_path)
            tags = getattr(audio, "tags", None)
            if tags is None:
                return False
            return "year" in tags
        except Exception:
            return False

    def _infer_album_from_library_path(self, file_path: Path) -> str:
        """Infer album name from organized library path .../Artist/Album/Track.ext."""
        try:
            parent_album = str(file_path.parent.name or "").strip()
            if not parent_album:
                return ""

            library_music = self.library_path
            if library_music and str(library_music).strip():
                try:
                    relative = file_path.resolve().relative_to(library_music.resolve())
                    # Expected layout: Artist/Album/Track
                    if len(relative.parts) >= 3:
                        return self._normalize_album_name(parent_album)
                except Exception:
                    return ""

            # Conservative fallback: only accept path-based album when under known library tree marker.
            path_text = str(file_path).replace("\\", "/").lower()
            if "/library/musics/" in path_text:
                return self._normalize_album_name(parent_album)
        except Exception:
            return ""
        return ""

    def _normalize_album_identity(self, metadata: Dict[str, Any]) -> tuple[str, str]:
        primary_artist = self._get_primary_artist(
            str(
                metadata.get("primary_artist")
                or metadata.get("album_artist")
                or metadata.get("artist")
                or ""
            )
        )
        album = self._normalize_album_name(str(metadata.get("album") or ""))
        return primary_artist.casefold(), album.casefold()

    def _is_music_record_for_recheck(self, metadata: Dict[str, Any], organized_path: Path) -> bool:
        """Best-effort detection for music records, even when media_type is missing."""
        media_type = str(metadata.get("media_type") or "").strip().lower()
        media_subtype = str(metadata.get("media_subtype")
                            or "").strip().lower()
        if media_type == "music" or media_subtype == "music":
            return True

        ext = organized_path.suffix.lower()
        if ext in AUDIO_EXTS:
            return True

        path_text = str(organized_path).replace("\\", "/").lower()
        return "/library/musics/" in path_text

    def _prefer_album_variant(self, values: List[str]) -> str:
        cleaned = [str(value).strip()
                   for value in values if str(value).strip()]
        if not cleaned:
            return ""

        counts = Counter(cleaned)

        def score(text: str) -> tuple[int, int, int, int]:
            words = [word for word in re.split(r"[\s\-:()]+", text) if word]
            title_like = sum(1 for word in words if word[:1].isupper())
            all_upper = 0 if text == text.upper() else 1
            mixed_case = 1 if any(ch.islower() for ch in text) else 0
            return (counts[text], all_upper, mixed_case, title_like)

        return max(cleaned, key=score)

    def _canonical_genre_signature(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""

        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))

        text = re.sub(r"\br\s*(?:&|and)?\s*b\b|\brnb\b", "rnb", text)
        text = re.sub(
            r"\bdrum\s*(?:and|&|n)?\s*bass\b|\bdnb\b",
            "drum bass",
            text,
        )

        text = re.sub(r"[-_/&+]+", " ", text)
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _genre_keyword_lexicon(self) -> set[str]:
        if self._genre_lexicon is not None:
            return self._genre_lexicon

        lexicon: set[str] = set()
        for source in (load_musical_keywords(), load_genre_exceptions()):
            for item in source:
                key = self._canonical_genre_signature(item)
                if not key:
                    continue
                lexicon.add(key)
                for token in key.split():
                    if len(token) >= 3:
                        lexicon.add(token)

        self._genre_lexicon = lexicon
        return self._genre_lexicon

    def _split_compound_genre_token(self, token: str) -> List[str]:
        if len(token) < 6:
            return [token]

        lexicon = self._genre_keyword_lexicon()

        # Detect glued compounds like "europop"/"electropop" using genre-family suffixes.
        family_suffixes = {
            "pop", "rock", "metal", "jazz", "soul", "funk", "house",
            "trance", "wave", "bass", "punk", "folk", "country",
            "blues", "disco", "hop", "rap", "dance",
        }
        for suffix in family_suffixes:
            if token.endswith(suffix) and len(token) > len(suffix) + 2:
                prefix = token[: -len(suffix)]
                if len(prefix) >= 3 and prefix in lexicon:
                    return [prefix, suffix]

        if token in lexicon:
            return [token]

        best_parts: Optional[List[str]] = None
        best_score = -1

        for index in range(3, len(token) - 2):
            left = token[:index]
            right = token[index:]
            if left in lexicon and right in lexicon:
                score = min(len(left), len(right))
                if score > best_score:
                    best_score = score
                    best_parts = [left, right]

        return best_parts or [token]

    def _display_genre_token(self, token: str) -> str:
        acronyms = {
            "edm": "EDM",
            "mpb": "MPB",
            "rnb": "R&B",
        }
        if token == "and":
            return "and"
        if token in acronyms:
            return acronyms[token]
        return token.title()

    def _normalize_genre_name(self, value: Any) -> str:
        """Normalize genre names using canonical rules instead of manual alias lists."""
        signature = self._canonical_genre_signature(value)
        if not signature:
            return ""

        if signature == "drum bass":
            return "Drum & Bass"

        parts: List[str] = []
        for token in signature.split():
            parts.extend(self._split_compound_genre_token(token))

        parts = [part for part in parts if part]
        if not parts:
            return ""

        # Prefer canonical hyphenated compounds for common style families.
        if len(parts) == 2:
            pair = (parts[0], parts[1])
            hyphen_compounds = {
                ("electro", "pop"): "Electro-Pop",
                ("synth", "pop"): "Synth-Pop",
                ("k", "pop"): "K-Pop",
                ("j", "pop"): "J-Pop",
                ("c", "pop"): "C-Pop",
            }
            if pair in hyphen_compounds:
                return hyphen_compounds[pair]

        return " ".join(self._display_genre_token(part) for part in parts)

    def _clean_track_name(self, track_name: str, artist: str) -> str:
        """Remove artist name from track name if present.

        Examples:
            "Love Generation - Bob Sinclar, Gary Pine" + "Bob Sinclar"
            -> "Love Generation"

            "Die With A Smile - Lady Gaga, Bruno Mars" + "Lady Gaga"
            -> "Die With A Smile"
        """
        if not track_name or not artist:
            return track_name or ""

        # Remove artist name if it appears at the end of track_name.
        artist_clean = artist.strip().lower()
        track_clean = track_name.strip()

        # Check whether track ends with " - Artist" or " - Artist, Others".
        if " - " in track_clean:
            parts = track_clean.rsplit(" - ", 1)
            if len(parts) == 2:
                title_part = parts[0].strip()
                artist_part = parts[1].strip().lower()

                # If artist part contains artist_clean, use only title part
                if artist_clean in artist_part or artist_part in artist_clean:
                    return title_part

        # Also check if track_name is exactly "Title - Artist"
        if track_clean.lower().endswith(f" - {artist_clean}"):
            return track_clean[:-len(f" - {artist_clean}")].strip()

        return track_clean

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
                # Clean track_name to remove artist names if present.
                if metadata.get("track_name"):
                    artist = metadata.get("artist") or existing_artist or ""
                    metadata["track_name"] = self._clean_track_name(
                        metadata["track_name"], artist)
                    metadata["title"] = metadata["track_name"]
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

        lead = self._canonicalize_artist_alias(lead)
        if not lead:
            return "Unknown Artist"

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
                """Extract all values for given keys.

                IMPORTANT: Do NOT split by comma if value is already a list (native multi-value).
                Splitting by comma on native multi-value tags causes duplication!
                """
                results = []
                for key in keys:
                    value = tags.get(key)
                    if isinstance(value, list):
                        # Native multi-value tag - use as-is, NO comma split!
                        for v in value:
                            text = str(v).strip()
                            if text and text.lower() != "unknown":
                                results.append(text)
                    elif value is not None:
                        # Single value - may contain comma or semicolon separated genres
                        text = str(value).strip()
                        if text and text.lower() != "unknown":
                            # Check for compound genre first (And, and, &)
                            if ' And ' in text or ' and ' in text or ' & ' in text:
                                # Don't split compound genres
                                results.append(text)
                            elif ',' in text or ';' in text:
                                # Normalize semicolon to comma, then split
                                text = text.replace(';', ',')
                                for part in text.split(","):
                                    part_clean = part.strip()
                                    if part_clean and part_clean.lower() != "unknown":
                                        results.append(part_clean)
                            else:
                                results.append(text)
                # Remove duplicates while preserving order
                return list(dict.fromkeys(results))

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

        artist_value = self._canonicalize_artist_alias(
            normalized.get("artist"))
        if artist_value:
            normalized["artist"] = artist_value

        album_artist_value = self._canonicalize_artist_alias(
            normalized.get("album_artist")
        )
        if album_artist_value:
            normalized["album_artist"] = album_artist_value

        artists_value = normalized.get("artists")
        if isinstance(artists_value, list):
            cleaned_artists = [
                self._canonicalize_artist_alias(item)
                for item in artists_value
                if self._canonicalize_artist_alias(item)
            ]
            normalized["artists"] = list(dict.fromkeys(cleaned_artists))

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

        genres_value = normalized.get("genres")
        if isinstance(genres_value, list):
            cleaned_genres = [
                self._normalize_genre_name(item)
                for item in genres_value
                if self._normalize_genre_name(item)
            ]
            normalized["genres"] = list(dict.fromkeys(cleaned_genres))

        genre_value = self._normalize_genre_name(normalized.get("genre"))
        if genre_value:
            normalized["genre"] = genre_value

        return normalized

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
        complement_genres: bool = False,
    ) -> Dict[str, Any]:
        final = {
            "artist": "Unknown Artist",
            "primary_artist": "Unknown Artist",
            "track_name": file_path.stem,
            "title": file_path.stem,
            "album": "Unknown Album",
            "genre": "",
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

        if online_metadata and complement_genres:
            local_genres = self._coerce_genre_list(existing_tags_metadata)
            online_genres = self._coerce_genre_list(online_metadata)
            merged_genres = self._merge_genre_lists(
                local_genres, online_genres)
            if merged_genres:
                final["genres"] = merged_genres
                final["genre"] = self._select_primary_genre(merged_genres)

        final = self._merge_missing_fields(
            final, self._normalize_metadata_values(filename_metadata))

        self._resolve_primary_artist(final, filename_metadata)
        self._resolve_album(final)
        self._resolve_genre(final, file_path)
        self._clean_final_track_name(final)

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

        # Always canonicalize final primary artist to keep destination routing stable.
        final["primary_artist"] = self._get_primary_artist(
            str(final.get("primary_artist") or final.get(
                "album_artist") or final.get("artist") or "")
        )

    def _resolve_album(
        self,
        final: Dict[str, Any],
    ) -> None:
        """Resolve album, preferring 'Singles' when artist known but album missing.
        """
        if self._is_missing(final.get("album")):
            if not self._is_missing(final.get("artist")):
                final["album"] = "Singles"
            else:
                final["album"] = "Unknown Album"
        else:
            # Normalize album name to keep naming stable and avoid duplicates.
            album = final.get("album")
            if album:
                final["album"] = self._normalize_album_name(album)

    def _select_primary_genre(self, genres: List[str]) -> str:
        """Select the most specific/representative genre from a list.

        Priority:
        1. Specific subgenres over generic terms (e.g., "Dutch House" over "House")
        2. Well-defined genres over broad categories (e.g., "Trance" over "Electronic")
        3. First genre if no differentiation possible

        Returns the selected primary genre or empty string if list is empty.
        """
        if not genres:
            return ""

        if len(genres) == 1:
            return genres[0]

        # Genre specificity scoring - more specific genres get higher scores
        specificity_scores: Dict[str, int] = {
            # Very specific subgenres (highest priority)
            "dutch house": 10, "french house": 10, "deep house": 10,
            "progressive house": 10, "tech house": 10, "electro house": 10,
            "big room house": 10, "future house": 10, "bass house": 10,
            "dutch trance": 10, "psytrance": 10, "psy-trance": 10,
            "progressive trance": 10, "vocal trance": 10, "uplifting trance": 10,
            "tech trance": 10, "acid trance": 10, "goa trance": 10,
            "detroit techno": 10, "minimal techno": 10, "acid techno": 10,
            "hard techno": 10, "dub techno": 10, "melodic techno": 10,
            "uk garage": 10, "uk hip hop": 10, "uk drill": 10, "uk funky": 10,
            "2-step garage": 10, "speed garage": 10, "bassline": 10,
            "drum and bass": 10, "drum & bass": 10, "liquid drum and bass": 10,
            "neurofunk": 10, "jump up": 10, "darkstep": 10, "techstep": 10,
            "hardstyle": 10, "raw hardstyle": 10, "euphoric hardstyle": 10,
            "happy hardcore": 10, "frenchcore": 10, "uptempo hardcore": 10,
            "hands up": 10, "hard nrg": 10, "bouncy techno": 10,
            "trip hop": 10, "trip-hop": 10, "downtempo": 10,
            "nu-disco": 10, "italo disco": 10, "space disco": 10,
            "synthpop": 10, "synth-pop": 10, "electropop": 10, "electro-pop": 10,
            "dance-pop": 10, "vaporwave": 10, "synthwave": 10, "chillwave": 10,
            "future funk": 10, "darkwave": 10, "coldwave": 10, "minimal wave": 10,
            "witch house": 10, "cloud rap": 10, "phonk": 10, "drift phonk": 10,
            "moombahton": 10, "moombahcore": 10, "complextro": 10,
            "trapstep": 10, "drumstep": 10, "halftime": 10,

            # Specific rock/metal subgenres
            "alternative rock": 10, "indie rock": 10, "garage rock": 10,
            "post-punk revival": 10, "new wave": 10, "post-punk": 10,
            "pop punk": 10, "hardcore punk": 10, "skate punk": 10,
            "melodic hardcore": 10, "emo pop": 10, "screamo": 10,
            "post-hardcore": 10, "metalcore": 10, "melodic metalcore": 10,
            "deathcore": 10, "electronicore": 10, "nintendocore": 10,
            "progressive rock": 10, "psychedelic rock": 10, "blues rock": 10,
            "folk rock": 10, "country rock": 10, "southern rock": 10,
            "glam rock": 10, "punk blues": 10, "garage punk": 10,
            "noise rock": 10, "shoegaze": 10, "dream pop": 10,
            "slowcore": 10, "sadcore": 10, "post-rock": 10, "math rock": 10,
            "stoner rock": 10, "desert rock": 10, "grunge": 10,
            "post-grunge": 10, "nu metal": 10, "rap metal": 10,
            "funk metal": 10, "alternative metal": 10, "industrial rock": 10,
            "industrial metal": 10, "neue deutsche härte": 10,
            "symphonic rock": 10, "symphonic metal": 10, "power metal": 10,
            "thrash metal": 10, "death metal": 10, "melodic death metal": 10,
            "technical death metal": 10, "brutal death metal": 10,
            "black metal": 10, "symphonic black metal": 10, "viking metal": 10,
            "folk metal": 10, "celtic metal": 10, "pagan metal": 10,
            "progressive metal": 10, "djent": 10, "groove metal": 10,
            "sludge metal": 10, "doom metal": 10, "stoner metal": 10,
            "drone metal": 10, "funeral doom": 10, "gothic metal": 10,
            "hardcore metal": 10, "crossover thrash": 10, "speed metal": 10,
            "power violence": 10, "grindcore": 10, "deathgrind": 10,

            # Specific hip hop subgenres
            "east coast hip hop": 10, "west coast hip hop": 10,
            "southern hip hop": 10, "midwest hip hop": 10,
            "uk hip hop": 10, "french hip hop": 10, "german hip hop": 10,
            "brazilian hip hop": 10, "trap latino": 10, "latin trap": 10,
            "mumble rap": 10, "conscious hip hop": 10, "gangsta rap": 10,
            "hardcore hip hop": 10, "underground hip hop": 10,
            "alternative hip hop": 10, "jazz rap": 10, "boom bap": 10,
            "cloud rap": 10, "rage rap": 10, "chicago drill": 10,
            "brooklyn drill": 10, "australian drill": 10, "french drill": 10,
            "old school hip hop": 10, "golden age hip hop": 10,
            "new school hip hop": 10, "crunk": 10, "snap music": 10,
            "hyphy": 10, "chopped and screwed": 10, "memphis rap": 10,
            "horrorcore": 10, "industrial hip hop": 10, "abstract hip hop": 10,

            # Specific R&B/Soul subgenres
            "contemporary r&b": 10, "contemporary r b": 10, "neo soul": 10,
            "classic soul": 10, "motown": 10, "northern soul": 10,
            "modern soul": 10, "deep soul": 10, "gospel soul": 10,
            "blue-eyed soul": 10, "british soul": 10, "uk r&b": 10,
            "alternative r&b": 10, "pbr&b": 10, "p-funk": 10, "g-funk": 10,
            "electro funk": 10, "disco funk": 10, "jazz funk": 10,

            # Specific country/folk subgenres
            "country pop": 10, "country rock": 10, "alternative country": 10,
            "alt-country": 10, "outlaw country": 10, "traditional country": 10,
            "classic country": 10, "neotraditional country": 10,
            "bro-country": 10, "country rap": 10, "hick hop": 10,
            "progressive bluegrass": 10, "contemporary folk": 10,
            "indie folk": 10, "freak folk": 10, "anti-folk": 10,
            "folk punk": 10, "americana": 10, "roots rock": 10,
            "heartland rock": 10, "singer-songwriter": 10, "yacht rock": 10,

            # Specific jazz subgenres
            "traditional jazz": 10, "dixieland": 10, "swing": 10,
            "big band": 10, "bebop": 10, "hard bop": 10, "cool jazz": 10,
            "modal jazz": 10, "free jazz": 10, "avant-garde jazz": 10,
            "jazz fusion": 10, "smooth jazz": 10, "contemporary jazz": 10,
            "latin jazz": 10, "bossa nova": 10, "afro-cuban jazz": 10,
            "nu jazz": 10, "acid jazz": 10, "vocal jazz": 10,
            "piano jazz": 10, "guitar jazz": 10, "saxophone jazz": 10,

            # Specific blues subgenres
            "electric blues": 10, "acoustic blues": 10, "delta blues": 10,
            "chicago blues": 10, "texas blues": 10, "british blues": 10,
            "blues rock": 10, "country blues": 10, "jump blues": 10,
            "west coast blues": 10, "piano blues": 10, "harmonica blues": 10,
            "soul blues": 10, "contemporary blues": 10,

            # Specific classical subgenres
            "baroque": 10, "classical period": 10, "romantic": 10,
            "contemporary classical": 10, "modern classical": 10,
            "minimal classical": 10, "neoclassical": 10,
            "ambient classical": 10, "post-minimalism": 10,

            # Specific gospel subgenres (removed: not pure musical genres)
            # "contemporary gospel": 10, "traditional gospel": 10,
            # "urban contemporary gospel": 10, "british black gospel": 10,
            # "australian gospel": 10, "brazilian gospel": 10,
            # "gospel brasileiro": 10, "contemporary christian": 10,
            # "christian rock": 10, "christian metal": 10, "christian hip hop": 10,
            # "christian rap": 10, "christian pop": 10, "christian alternative": 10,
            # "christian punk": 10, "christian hardcore": 10,
            "contemporary worship": 10, "praise and worship": 10,

            # Specific latin subgenres
            "latin pop": 10, "latin rock": 10, "latin jazz": 10,
            "latin urban": 10, "reggaeton flow": 10, "salsa romantica": 10,
            "salsa dura": 10, "merengue hip hop": 10, "cumbia villera": 10,
            "cumbia sonidera": 10, "electronic cumbia": 10, "digital cumbia": 10,
            "corridos tumbados": 10, "regional mexicano": 10,
            "nuevo tango": 10, "funk carioca": 10, "funk brasileiro": 10,
            "brazilian funk": 10, "baile funk": 10, "funk melody": 10,
            "funk ostentação": 10, "funk consciente": 10,

            # Medium specificity genres
            "house": 5, "trance": 5, "techno": 5, "electronic": 5,
            "electro": 5, "dance": 5, "disco": 5, "edm": 5,
            "rock": 5, "metal": 5, "punk": 5, "indie": 5,
            "alternative": 5, "hip hop": 5, "hip-hop": 5, "rap": 5,
            "r&b": 5, "r b": 5, "rnb": 5, "soul": 5, "funk": 5,
            "reggae": 5, "reggaeton": 5, "country": 5, "folk": 5,
            "jazz": 5, "blues": 5, "classical": 5, "ambient": 5,
            "gospel": 5, "christian": 5, "worship": 5,
            "samba": 5, "pagode": 5, "sertanejo": 5, "forró": 5,
            "forro": 5, "bossa": 5, "mpb": 5, "axé": 5, "axe": 5,
            "arrocha": 5, "piseiro": 5, "ska": 5, "ska punk": 5,
            "dancehall": 5, "dub": 5, "trap": 5, "grime": 5,
            "dubstep": 5, "drum and bass": 5, "jungle": 5,
            "hardcore": 5, "eurodance": 5, "euro-dance": 5,
            "balearic": 5, "chillout": 5, "idm": 5, "glitch": 5,
            "minimal": 5, "deep": 5, "progressive": 5, "tech": 5,
            "acid": 5, "psy": 5, "goa": 5, "dark": 5, "forest": 5,
            "melodic": 5, "organic": 5, "future": 5, "rave": 5,
            "bounce": 5, "ebm": 5, "industrial": 5, "aggrotech": 5,
            "futurepop": 5, "wave": 5, "seapunk": 5, "drag": 5,
            "plugg": 5, "rage": 5, "opium": 5, "hyperpop": 5,
            "glitchcore": 5, "breakcore": 5, "speedcore": 5,
            "liquid": 5, "sambass": 5, "atmospheric": 5,
            "intelligent": 5, "footwork": 5, "juke": 5, "ghetto": 5,
            "miami bass": 5, "techno bass": 5, "hip house": 5,
            "electro hop": 5, "electropunk": 5, "indietronica": 5,
            "disco rock": 5, "dance-rock": 5, "electro rock": 5,
            "electronic rock": 5, "synthpunk": 5, "emo": 5,
            "easycore": 5, "pop rock": 5, "soft rock": 5, "hard rock": 5,
            "classic rock": 5, "arena rock": 5, "noise": 5,
            "post-grunge": 5, "swans": 5, "bedroom": 5, "art": 5,
            "experimental": 5, "baroque pop": 5, "chamber pop": 5,
            "sunshine pop": 5, "bubblegum pop": 5, "teen pop": 5,
            "k-pop": 5, "j-pop": 5, "c-pop": 5, "mandopop": 5,
            "cantopop": 5, "t-pop": 5, "v-pop": 5, "p-pop": 5,
            "latin": 5, "brazilian": 5, "tropicália": 5, "tropicalia": 5,
            "brasileiro": 5, "rocksteady": 5, "lovers": 5, "roots": 5,
            "fusion": 5, "east coast": 5, "west coast": 5, "southern": 5,
            "midwest": 5, "mumble": 5, "conscious": 5, "gangsta": 5,
            "underground": 5, "boom bap": 5, "drill": 5, "chicago": 5,
            "brooklyn": 5, "australian": 5, "french": 5, "old school": 5,
            "golden age": 5, "new school": 5, "snap": 5, "hyphy": 5,
            "memphis": 5, "abstract": 5, "flow": 5, "latino": 5,
            "contemporary": 5, "classic": 5, "motown": 5, "northern": 5,
            "modern": 5, "blue-eyed": 5, "british": 5, "boogie": 5,
            "afrobeat": 5, "afro-beat": 5, "afrobeats": 5, "afro-fusion": 5,
            "highlife": 5, "juju": 5, "fuji": 5, "alt-country": 5,
            "outlaw": 5, "traditional": 5, "neotraditional": 5,
            "bro-country": 5, "hick hop": 5, "bluegrass": 5,
            "americana": 5, "heartland": 5, "yacht": 5, "dixieland": 5,
            "swing": 5, "bebop": 5, "cool": 5, "modal": 5, "free": 5,
            "smooth": 5, "nu jazz": 5, "acid jazz": 5, "vocal": 5,
            "piano": 5, "guitar": 5, "saxophone": 5, "electric": 5,
            "acoustic": 5, "delta": 5, "texas": 5, "jump": 5,
            "harmonica": 5, "afro-cuban": 5, "baroque": 5, "romantic": 5,
            "neoclassical": 5, "orchestral": 5, "opera": 5, "choral": 5,
            "early music": 5, "medieval": 5, "renaissance": 5,
            "new age": 5, "meditation": 5, "relaxation": 5, "spa": 5,
            "healing": 5, "bachata": 5, "salsa": 5, "romantica": 5,
            "dura": 5, "merengue": 5, "cumbia": 5, "villera": 5,
            "sonidera": 5, "digital": 5, "vallenato": 5, "bolero": 5,
            "ranchera": 5, "mariachi": 5, "norteño": 5, "banda": 5,
            "corridos": 5, "tumbados": 5, "sierreño": 5, "zapateado": 5,
            "huapango": 5, "son jarocho": 5, "choro": 5, "xote": 5,
            "baião": 5, "baiao": 5, "carioca": 5, "ostentação": 5,
            "consciente": 5, "melody": 5, "tango": 5, "nuevo": 5,
            "milonga": 5, "zamba": 5, "chamamé": 5, "cueca": 5,
            "tonada": 5, "afropop": 5, "amapiano": 5, "gqom": 5,
            "kwaito": 5, "afroswing": 5, "apala": 5, "makossa": 5,
            "bikutsi": 5, "soukous": 5, "rumba": 5, "congolese": 5,
            "mbalax": 5, "benga": 5, "genge": 5, "kapuka": 5,
            "kizomba": 5, "semba": 5, "tarraxinha": 5, "zouk": 5,
            "compas": 5, "cadence": 5, "bouyon": 5, "chouval bwa": 5,
            "biguine": 5, "mazurka": 5, "mento": 5, "calypso": 5,
            "soca": 5, "chutney": 5, "parang": 5, "steelpan": 5,
            "steel drum": 5, "timba": 5, "descarga": 5, "punto guajiro": 5,
            "j-rock": 5, "japanese": 5, "visual kei": 5, "j-core": 5,
            "shibuya-kei": 5, "city": 5, "k-rock": 5, "korean": 5,
            "k-indie": 5, "k-ballad": 5, "chinese": 5, "thai": 5,
            "luk thung": 5, "mor lam": 5, "vietnamese": 5, "pinoy": 5,
            "opm": 5, "indonesian": 5, "malaysian": 5, "bollywood": 5,
            "filmi": 5, "indian": 5, "hindustani": 5, "carnatic": 5,
            "bhangra": 5, "punjabi": 5, "qawwali": 5, "ghazal": 5,
            "world": 5, "celtic": 5, "irish": 5, "scottish": 5,
            "nordic": 5, "scandinavian": 5, "finnish": 5, "balkan": 5,
            "gypsy": 5, "klezmer": 5, "yiddish": 5, "flamenco": 5,
            "fado": 5, "morna": 5, "coladeira": 5, "raï": 5, "gnawa": 5,
            "chaabi": 5, "andalusian": 5, "turkish": 5, "arabesque": 5,
            "greek": 5, "rebetiko": 5, "laiko": 5, "entechno": 5,
            "persian": 5, "arabic": 5, "tarab": 5, "waslah": 5,
            "muwashshah": 5, "film score": 5, "movie": 5, "tv": 5,
            "video game": 5, "vgm": 5, "chiptune": 5, "bitpop": 5,
            "anime": 5, "anison": 5, "image song": 5, "character": 5,
            "musical": 5, "show tunes": 5, "broadway": 5, "west end": 5,
            "cast": 5, "disney": 5,
        }

        # Generic/broad genres (lowest priority) - REMOVIDO gospel/christian/worship
        generic_terms = {
            "pop", "rock", "metal", "jazz", "blues",
            "house", "techno", "trance", "edm", "electro",
            "electronic", "dance", "disco", "rap", "hip hop", "hip-hop",
            "trap", "r&b", "rnb", "soul", "funk", "reggae", "reggaeton",
            "country", "folk", "classical", "ambient", "instrumental",
            "samba", "pagode", "sertanejo", "forro", "forró",
            "bossa", "mpb", "axé", "axe", "arrocha", "piseiro", "indie",
            "alternative", "ballad", "easy listening", "garage", "hardcore",
            # Note: "unknown", "other", "misc", "various" are intentionally excluded
            # because they are handled as invalid values by Genre Guard.
        }

        # Find genre with highest specificity score
        best_genre = genres[0]
        best_score = 0

        for genre in genres:
            genre_lower = genre.lower().strip()
            score = specificity_scores.get(genre_lower, 0)

            # Penalize generic terms (but don't reduce below 1)
            if genre_lower in generic_terms:
                score = max(1, score - 2)

            if score > best_score:
                best_score = score
                best_genre = genre

        return best_genre

    def _resolve_genre(
        self,
        final: Dict[str, Any],
        file_path: Path,
    ) -> None:
        """Resolve genre and remove invalid/polluted values.

        Prevents duplicates by:
        1. Using only list values (`genres`) as independent entries
        2. Filtering invalid genres before downstream enrichment
        3. Avoiding double insertion from both `genre` and `genres`
        """
        raw_genres: List[str] = []

        # Priority 1: Use multi-value genres list if available
        genres_value = final.get("genres")
        if isinstance(genres_value, list):
            # Add each genre individually, never concatenate.
            for v in genres_value:
                genre_str = str(v).strip()
                if genre_str and ',' not in genre_str and ';' not in genre_str:
                    # Keep clean single genre values.
                    raw_genres.append(genre_str)
                elif genre_str and (',' in genre_str or ';' in genre_str):
                    # Split concatenated genres and add each part.
                    separator = ';' if ';' in genre_str else ','
                    for part in genre_str.split(separator):
                        part_clean = part.strip()
                        if part_clean:
                            raw_genres.append(part_clean)

        # Priority 2: Use single genre only if no list
        primary = str(final.get("genre") or "").strip()
        if primary and not raw_genres:
            # Only add primary when no explicit genre list exists.
            if ',' not in primary and ';' not in primary:
                raw_genres.append(primary)
            else:
                # Split concatenated primary genre.
                separator = ';' if ';' in primary else ','
                for part in primary.split(separator):
                    part_clean = part.strip()
                    if part_clean:
                        raw_genres.append(part_clean)

        # Remove duplicates while preserving order
        raw_genres = list(dict.fromkeys(raw_genres))

        # Filter invalid genres
        filtered, removed = sanitize_genre_values(
            file_path,
            raw_genres,
            logger=self.logger,
            track_cycle_stats=False,
        )

        # Keep only normalized cleaned list using canonical signatures.
        normalized_filtered = self._normalize_genre_values(filtered)
        final["genres"] = normalized_filtered

        # Select most specific genre as primary
        final["genre"] = self._select_primary_genre(
            normalized_filtered) if normalized_filtered else ""

        # If all genres were removed, clear genre_source as well.
        if not normalized_filtered and not final.get("genre"):
            final.pop("genre_source", None)

        if removed:
            self.logger.info(
                "Removed invalid genre values for %s: %s",
                file_path.name,
                removed,
            )

    def _clean_final_track_name(self, final: Dict[str, Any]) -> None:
        """Clean track_name and title by removing artist name if present.

        Applies _clean_track_name after all metadata resolution to ensure
        titles do not contain artist names.

        Examples:
            "Love Generation - Bob Sinclar, Gary Pine" + artist "Bob Sinclar"
            -> "Love Generation"
        """
        track_name = final.get("track_name", "")
        artist = final.get("artist", "")

        if track_name:
            cleaned = self._clean_track_name(track_name, artist)
            final["track_name"] = cleaned
            # Manter title sincronizado com track_name
            final["title"] = cleaned

    def _is_folder_name_genre_match(self, file_path: Path, genre_value: Any) -> bool:
        """Detect polluted genre values copied from folder names."""
        genre = str(genre_value or "").strip().lower()
        if not genre:
            return False

        ignored_folder_names = {
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

            candidates = {
                name.strip().lower(),
                re.sub(r"^#\d+\s*", "", name).strip().lower(),
            }
            candidates = {
                c for c in candidates
                if c and c not in ignored_folder_names
            }
            if genre in candidates:
                return True

        return False

    def _sanitize_polluted_genre_from_metadata(
        self,
        metadata: Dict[str, Any],
        file_path: Path,
    ) -> Dict[str, Any]:
        """Remove invalid/polluted genre values."""
        cleaned = deepcopy(metadata)
        raw_genres: List[str] = []

        genres = cleaned.get("genres")
        if isinstance(genres, list):
            raw_genres.extend([str(v).strip()
                              for v in genres if str(v).strip()])

        primary = str(cleaned.get("genre") or "").strip()
        if primary:
            raw_genres.append(primary)

        filtered, removed = sanitize_genre_values(
            file_path, raw_genres, logger=self.logger)
        normalized_filtered = self._normalize_genre_values(filtered)
        cleaned["genres"] = normalized_filtered
        cleaned["genre"] = normalized_filtered[0] if normalized_filtered else ""

        if not self._is_missing(cleaned.get("genre")):
            return cleaned
        if isinstance(cleaned.get("genres"), list) and cleaned["genres"]:
            return cleaned

        if removed:
            self.logger.info(
                "Discarded invalid/polluted genre values for %s: %s",
                file_path.name,
                removed,
            )
        return cleaned

    def _normalize_artist_for_lookup(self, artist_value: Any) -> str:
        artist = str(artist_value or "").strip()
        if not artist:
            return ""
        return self._get_primary_artist(artist)

    def _normalize_title_for_lookup(self, title_value: Any, artist_value: str) -> str:
        title = str(title_value or "").strip()
        if not title:
            return ""

        # Remove track number prefixes like "01 - Song Name".
        title = re.sub(r"^\s*\d{1,3}\s*-\s*", "", title)

        # If title contains trailing artist segment from filename format,
        # keep only the song title portion.
        parts = [part.strip() for part in title.split(" - ") if part.strip()]
        if len(parts) >= 2:
            last_part = parts[-1].lower()
            normalized_artist = artist_value.strip().lower()
            if normalized_artist and (
                last_part == normalized_artist
                or normalized_artist in last_part
                or last_part in normalized_artist
            ):
                parts = parts[:-1]
                title = " - ".join(parts).strip()

        return title

    async def _fetch_online_music_metadata(
        self,
        file_path: Path,
        current_metadata: Dict[str, Any],
        needs_genre: bool,
    ) -> Dict[str, Any]:
        raw_artist = (current_metadata.get("artist") or "").strip()
        artist = self._normalize_artist_for_lookup(raw_artist)

        if not artist or artist.lower().startswith("unknown"):
            return {}

        cache_key = f"artist::{artist.lower()}"
        cached = self._online_cache.get(cache_key)
        if cached is not None:
            return deepcopy(cached)

        enriched = await enrich_music_metadata_with_online_sources(
            file_path=file_path,
            existing_metadata={"artist": artist},
            logger=self.logger,
            lastfm_api_key=self.config.lastfm_api_key,
            api_delay_seconds=self.config.music_metadata_api_delay_seconds,
            max_retries=self.config.music_metadata_api_max_retries,
            fetch_lastfm=needs_genre,
        )

        self._online_cache[cache_key] = deepcopy(enriched)
        return enriched

    def _coerce_genre_list(self, metadata: Dict[str, Any]) -> List[str]:
        genres: List[str] = []

        value = metadata.get("genres")
        if isinstance(value, list):
            for item in value:
                text = str(item or "").strip()
                if text:
                    genres.append(text)

        primary = str(metadata.get("genre") or "").strip()
        if primary:
            genres.append(primary)

        return list(dict.fromkeys(genres))

    def _normalize_genre_values(self, values: Any) -> List[str]:
        normalized: List[str] = []
        seen_signatures: set[str] = set()
        if isinstance(values, (str, bytes)) or values is None:
            iterable = [values] if values is not None else []
        else:
            iterable = values

        for value in iterable:
            genre_name = self._normalize_genre_name(value)
            signature = self._canonical_genre_signature(genre_name)
            if genre_name and signature and signature not in seen_signatures:
                normalized.append(genre_name)
                seen_signatures.add(signature)
        return normalized

    def _merge_genre_lists(self, *lists: List[str]) -> List[str]:
        merged: List[str] = []
        for genre_list in lists:
            for item in genre_list:
                text = str(item or "").strip()
                if text and text not in merged:
                    merged.append(text)
        return merged

    def _normalized_genre_set(self, metadata: Dict[str, Any]) -> set[str]:
        normalized: set[str] = set()
        for item in self._coerce_genre_list(metadata):
            genre_name = self._normalize_genre_name(item)
            if genre_name:
                signature = self._canonical_genre_signature(genre_name)
                if signature:
                    normalized.add(signature)
        return normalized

    def _verify_and_repair_genre_persistence(
        self,
        file_path: Path,
        final_metadata: Dict[str, Any],
        online_metadata: Optional[Dict[str, Any]],
    ) -> bool:
        """Ensure on-disk genres match final metadata before DB persistence."""
        expected_genres = self._normalized_genre_set(final_metadata)
        if not expected_genres:
            return True

        persisted_metadata = self._read_audio_tags(file_path)
        persisted_genres = self._normalized_genre_set(persisted_metadata)
        if persisted_genres == expected_genres:
            return True

        self.logger.warning(
            "Genre persistence mismatch for %s (expected=%s, persisted=%s). Retrying with force overwrite.",
            file_path.name,
            sorted(expected_genres),
            sorted(persisted_genres),
        )

        retry_source_metadata = self._sanitize_polluted_genre_from_metadata(
            self._read_audio_tags(file_path),
            file_path,
        )
        retry_ok = self._update_audio_tags(
            file_path=file_path,
            original_metadata=retry_source_metadata,
            final_metadata=final_metadata,
            online_metadata=online_metadata,
            force_overwrite_fields={"genre", "genres"},
        )
        if not retry_ok:
            return False

        persisted_after_retry = self._normalized_genre_set(
            self._read_audio_tags(file_path)
        )
        if persisted_after_retry != expected_genres:
            self.logger.error(
                "Genre persistence mismatch remains for %s after retry (expected=%s, persisted=%s).",
                file_path.name,
                sorted(expected_genres),
                sorted(persisted_after_retry),
            )
            return False

        return True

    def _complement_genre_decision(self, metadata: Dict[str, Any]) -> tuple[bool, str]:
        if not getattr(self.config, "music_genre_complement_enabled", True):
            return False, "config_disabled"

        genres = self._coerce_genre_list(metadata)
        if not genres:
            return False, "no_existing_genres"

        max_existing = getattr(
            self.config,
            "music_genre_complement_max_existing_genres",
            1,
        )
        if len(genres) <= int(max_existing):
            return True, "under_existing_threshold"

        normalized = {genre.lower().strip() for genre in genres}
        if normalized.issubset(self.GENERIC_GENRE_HINTS):
            return True, "generic_only"

        return False, "already_specific"

    def _is_missing_genre_after_processing(self, metadata: Dict[str, Any]) -> bool:
        normalized_genres = self._normalize_genre_values(
            self._coerce_genre_list(metadata))
        return not bool(normalized_genres)

    def _enqueue_genre_enrichment_retry(self, entry: Dict[str, Any]) -> None:
        try:
            queue_path = self._genre_enrichment_retry_queue_path
            queue_path.parent.mkdir(parents=True, exist_ok=True)

            if queue_path.exists():
                payload = json.loads(queue_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    payload = {}
            else:
                payload = {}

            entries = payload.get("entries")
            if not isinstance(entries, list):
                entries = []

            source_path = str(entry.get("source_path") or "")
            replaced = False
            for index, current in enumerate(entries):
                if str(current.get("source_path") or "") == source_path:
                    entries[index] = entry
                    replaced = True
                    break

            if not replaced:
                entries.append(entry)

            payload["updated_at"] = datetime.now(
                timezone.utc).isoformat(timespec="seconds")
            payload["entries"] = entries
            payload["count"] = len(entries)

            queue_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            self.logger.warning("Failed to update genre retry queue: %s", exc)

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
        force_overwrite_fields: Optional[set[str]] = None,
        normalize_release_year_cleanup: bool = False,
    ) -> bool:
        """
        Update audio file tags with Navidrome-compatible metadata.

        Writes: title, artist, album_artist, album, genre, track_number,
                disc_number, year, compilation flag, and online identifiers.

        Supports: MP3 (ID3v2), FLAC/OGG/Opus (Vorbis), M4A, WMA.
        """
        try:
            self._last_audio_tag_write_had_changes = False
            ext = file_path.suffix.lower()
            changed_fields: Dict[str, Any] = {}
            force_overwrite_fields = force_overwrite_fields or set()

            explicit_genre_in_final = "genre" in final_metadata
            explicit_genres_in_final = "genres" in final_metadata

            online_genre = (online_metadata or {}).get("genre")
            if explicit_genre_in_final:
                genre_candidate = final_metadata.get("genre")
            elif not self._is_missing(online_genre):
                genre_candidate = online_genre
            else:
                genre_candidate = original_metadata.get("genre")

            online_genres = (online_metadata or {}).get("genres")
            if explicit_genres_in_final:
                genres_candidate = final_metadata.get("genres")
            elif not self._is_missing(online_genres):
                genres_candidate = online_genres
            else:
                genres_candidate = original_metadata.get("genres")

            candidate_map = {
                "genre": genre_candidate,
                "genres": genres_candidate,
                "musicbrainz_trackid": (online_metadata or {}).get("musicbrainz_trackid"),
                "musicbrainz_albumid": (online_metadata or {}).get("musicbrainz_albumid"),
                "isrc": (online_metadata or {}).get("isrc"),
                "title": (online_metadata or {}).get("title") or final_metadata.get("title"),
                "artist": (online_metadata or {}).get("artist") or final_metadata.get("artist"),
                "artists": final_metadata.get("artists") or original_metadata.get("artists"),
                "album": (online_metadata or {}).get("album") or final_metadata.get("album"),
                "year": (online_metadata or {}).get("year") or final_metadata.get("year"),
                "track_number": final_metadata.get("track_number"),
            }

            def _as_comp(value: Any) -> str:
                if isinstance(value, list):
                    return "|".join(str(v).strip() for v in value if str(v).strip()).lower()
                return str(value or "").strip().lower()

            def _as_text_preserve_case(value: Any) -> str:
                return " ".join(str(value or "").strip().split())

            for field, candidate in candidate_map.items():
                # Always sanitize genre values, even when tags already exist.
                if field == "genres":
                    orig_genres = original_metadata.get(field, [])

                    if self._is_missing(candidate):
                        if explicit_genres_in_final:
                            # Respect explicit cleanup when final metadata intentionally clears genres.
                            candidate = final_metadata.get("genres") or []
                        else:
                            candidate = orig_genres

                    if self._is_missing(candidate):
                        continue

                    candidate = self._normalize_genre_values(candidate)

                    if field in force_overwrite_fields:
                        if _as_comp(orig_genres) != _as_comp(candidate):
                            changed_fields[field] = candidate
                        continue

                    if isinstance(orig_genres, list):
                        from app.features.genre_guard import sanitize_genre_values
                        sanitized_orig, removed_orig = sanitize_genre_values(
                            file_path,
                            orig_genres,
                            track_cycle_stats=False,
                        )
                        sanitized_orig = self._normalize_genre_values(
                            sanitized_orig)

                        if removed_orig or _as_comp(sanitized_orig) != _as_comp(orig_genres):
                            changed_fields[field] = sanitized_orig
                        elif _as_comp(sanitized_orig) != _as_comp(candidate):
                            changed_fields[field] = candidate
                    else:
                        changed_fields[field] = candidate
                    continue

                if field == "genre":
                    orig_value = str(
                        original_metadata.get(field) or "").strip()
                    if self._is_missing(candidate):
                        if explicit_genre_in_final:
                            # Respect explicit cleanup when final metadata intentionally clears primary genre.
                            candidate = str(final_metadata.get("genre") or "")
                        else:
                            candidate = orig_value

                    if self._is_missing(candidate):
                        continue

                    candidate = self._normalize_genre_name(candidate)

                    if field in force_overwrite_fields:
                        if _as_comp(orig_value) != _as_comp(candidate):
                            changed_fields[field] = candidate
                        continue

                    from app.features.genre_guard import sanitize_genre_values
                    sanitized_candidate, _ = sanitize_genre_values(
                        file_path,
                        [candidate],
                        track_cycle_stats=False,
                    )
                    sanitized_candidate_value = self._normalize_genre_name(
                        sanitized_candidate[0] if sanitized_candidate else ""
                    )

                    sanitized_orig, removed_orig = sanitize_genre_values(
                        file_path,
                        [orig_value] if orig_value else [],
                        track_cycle_stats=False,
                    )
                    sanitized_orig_value = self._normalize_genre_name(
                        sanitized_orig[0] if sanitized_orig else ""
                    )

                    if removed_orig or sanitized_orig_value != orig_value:
                        changed_fields[field] = sanitized_candidate_value
                    elif sanitized_candidate_value != sanitized_orig_value:
                        changed_fields[field] = sanitized_candidate_value
                    continue

                if self._is_missing(candidate):
                    continue

                if field in force_overwrite_fields:
                    if field in {"album", "title", "artist", "album_artist"}:
                        if _as_text_preserve_case(original_metadata.get(field)) != _as_text_preserve_case(candidate):
                            changed_fields[field] = candidate
                    elif field == "track_number":
                        if self._normalize_track_number_for_compare(original_metadata.get(field)) != self._normalize_track_number_for_compare(candidate):
                            changed_fields[field] = candidate
                    elif _as_comp(original_metadata.get(field)) != _as_comp(candidate):
                        changed_fields[field] = candidate
                    continue

                if self._is_missing(original_metadata.get(field)):
                    changed_fields[field] = candidate

            primary_artist = str(final_metadata.get(
                "primary_artist") or "").strip()
            if primary_artist and not self._is_missing(primary_artist):
                current_album_artist_value = (
                    original_metadata.get(
                        "album_artist") or original_metadata.get("artist")
                )
                if self._is_missing(current_album_artist_value):
                    changed_fields["album_artist"] = primary_artist

            # If final metadata carries a multi-genre set, always prefer that
            # list as the persisted truth so text-only variants get normalized.
            final_genres = final_metadata.get("genres")
            if isinstance(final_genres, list):
                normalized_final_genres = self._normalize_genre_values(
                    final_genres)
                if normalized_final_genres:
                    original_genres_value = original_metadata.get("genres")
                    should_write_genres = False
                    if "genre" in changed_fields and "genres" not in changed_fields:
                        should_write_genres = True
                    elif _as_comp(original_genres_value) != _as_comp(normalized_final_genres):
                        should_write_genres = True

                    if should_write_genres:
                        changed_fields["genres"] = normalized_final_genres
                        changed_fields.pop("genre", None)

            if normalize_release_year_cleanup and ext in {".flac", ".ogg", ".opus"}:
                try:
                    from mutagen.flac import FLAC
                    audio = FLAC(file_path)
                    audio_tags = cast(Any, audio.tags)
                    if audio_tags is not None and "year" in audio_tags and "__cleanup_release_year__" not in changed_fields:
                        changed_fields["__cleanup_release_year__"] = True
                except Exception:
                    pass

            if not changed_fields:
                self.logger.debug(
                    "File already has normalized metadata or no updates needed: %s", file_path.name)
                return True

            if self.dry_run:
                self._last_audio_tag_write_had_changes = True
                self.logger.info(
                    "[DRY RUN] Would update %s with fields: %s",
                    file_path.name,
                    ", ".join(sorted(changed_fields.keys())),
                )
                return True

            if ext in {".flac", ".ogg", ".opus"}:
                from mutagen.flac import FLAC

                audio = FLAC(file_path)

                # Always sanitize existing on-disk genre tags.
                from app.features.genre_guard import sanitize_genre_values
                audio_tags = cast(Any, audio.tags)
                year_cleanup_requested = changed_fields.pop(
                    "__cleanup_release_year__", None) is not None
                year_cleanup_applied = False
                if year_cleanup_requested and audio_tags is not None and "year" in audio_tags:
                    try:
                        del audio_tags["year"]
                        year_cleanup_applied = True
                    except Exception:
                        pass

                # Read current on-disk genres.
                current_audio_genres = audio_tags.get(
                    'genre', []) if audio_tags is not None else []
                if current_audio_genres:
                    # Apply sanitizer on every write path.
                    sanitized, removed = sanitize_genre_values(
                        file_path,
                        current_audio_genres,
                        track_cycle_stats=False,
                    )
                    normalized_current_audio_genres = self._normalize_genre_values(
                        sanitized
                    )
                    needs_sanitizer_cleanup = sanitized != current_audio_genres
                    needs_normalization_cleanup = normalized_current_audio_genres != sanitized

                    # Update tags if values changed or invalid ones were removed.
                    if (
                        removed
                        or needs_sanitizer_cleanup
                        or needs_normalization_cleanup
                    ):
                        changed_fields['genres'] = normalized_current_audio_genres
                        if removed:
                            self.logger.info(
                                "Forcing genre cleanup for %s: removed %s invalid",
                                file_path.name,
                                len(removed),
                            )
                        else:
                            self.logger.info(
                                "Forcing genre normalization for %s: canonicalized existing genre values",
                                file_path.name,
                            )

                preferred_genres = self._normalize_genre_values(
                    final_metadata.get("genres")
                    if isinstance(final_metadata.get("genres"), list)
                    else changed_fields.get("genres")
                )

                # Write genres only as multi-value list, never as concatenated string.
                if preferred_genres:
                    # Ensure each entry is an independent genre value.
                    clean_genres = []
                    for v in preferred_genres:
                        genre_str = self._normalize_genre_name(v)
                        # Skip entries containing separators to prevent duplication.
                        if genre_str and ',' not in genre_str and ';' not in genre_str:
                            clean_genres.append(genre_str)

                    # Write native multi-value tag, or remove when empty.
                    if clean_genres:
                        audio["genre"] = clean_genres
                    elif audio_tags is not None and "genre" in audio_tags:
                        try:
                            del audio_tags["genre"]
                        except Exception:
                            pass

                    # Ensure a concatenated string value is not kept.
                    if audio_tags is not None and "genre" in audio_tags:
                        existing = audio_tags["genre"]
                        if isinstance(existing, str) and (',' in existing or ';' in existing):
                            # Remove concatenated value and keep only multi-value.
                            try:
                                del audio_tags["genre"]
                            except Exception:
                                pass

                elif "genres" in changed_fields or "genre" in changed_fields:
                    single_genre = self._normalize_genre_name(
                        changed_fields.get("genre"))
                    if single_genre and ',' not in single_genre and ';' not in single_genre:
                        audio["genre"] = [single_genre]
                    elif single_genre:
                        # Split and write as multi-value
                        separator = ';' if ';' in single_genre else ','
                        audio["genre"] = [p.strip()
                                          for p in single_genre.split(separator) if p.strip()]
                    elif audio_tags is not None and "genre" in audio_tags:
                        del audio_tags["genre"]
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
                if "artists" in changed_fields and isinstance(changed_fields["artists"], list) and changed_fields["artists"]:
                    audio["artist"] = [
                        str(v) for v in changed_fields["artists"] if str(v).strip()]
                elif "artist" in changed_fields:
                    audio["artist"] = [str(changed_fields["artist"])]
                if "album_artist" in changed_fields:
                    audio["albumartist"] = [
                        str(changed_fields["album_artist"])]
                if "album" in changed_fields:
                    audio["album"] = [str(changed_fields["album"])]
                if "year" in changed_fields:
                    audio["date"] = [str(changed_fields["year"])]
                if "track_number" in changed_fields:
                    audio["tracknumber"] = [
                        str(changed_fields["track_number"])]
                # Preserve disc number if exists
                if "disc_number" in original_metadata and original_metadata["disc_number"]:
                    audio["discnumber"] = [
                        str(original_metadata["disc_number"])]
                # Preserve compilation flag if exists
                if "compilation" in original_metadata and original_metadata["compilation"]:
                    audio["compilation"] = [
                        str(original_metadata["compilation"])]

                audio.save()
                self._last_audio_tag_write_had_changes = True
                logged_fields = sorted(changed_fields.keys())
                if year_cleanup_applied:
                    logged_fields.append("release_year_cleanup")
                self.logger.info("Updated tags (FLAC): %s | fields: %s",
                                 file_path.name, ", ".join(logged_fields))
                return True

            if ext == ".mp3":
                from mutagen.id3 import ID3, TALB, TDRC, TCON, TIT2, TPE1, TPE2, TSRC, TXXX, TPOS, TCMP, TRCK

                audio = ID3(file_path)

                # Always sanitize existing on-disk genre tags.
                from app.features.genre_guard import sanitize_genre_values

                current_audio_genres = []
                if "TCON" in audio:
                    current_audio_genres = audio["TCON"].text

                if current_audio_genres:
                    sanitized, removed = sanitize_genre_values(
                        file_path,
                        current_audio_genres,
                        track_cycle_stats=False,
                    )
                    normalized_current_audio_genres = self._normalize_genre_values(
                        sanitized
                    )
                    needs_sanitizer_cleanup = sanitized != current_audio_genres
                    needs_normalization_cleanup = normalized_current_audio_genres != sanitized
                    if (
                        removed
                        or needs_sanitizer_cleanup
                        or needs_normalization_cleanup
                    ):
                        changed_fields['genres'] = normalized_current_audio_genres
                        if removed:
                            self.logger.info(
                                "Forcing genre cleanup for %s: removed %s invalid",
                                file_path.name,
                                len(removed),
                            )
                        else:
                            self.logger.info(
                                "Forcing genre normalization for %s: canonicalized existing genre values",
                                file_path.name,
                            )

                preferred_genres = self._normalize_genre_values(
                    final_metadata.get("genres")
                    if isinstance(final_metadata.get("genres"), list)
                    else changed_fields.get("genres")
                )

                if preferred_genres:
                    audio["TCON"] = TCON(
                        encoding=3, text=[str(v) for v in preferred_genres if str(v).strip()]
                    )
                elif "genres" in changed_fields and isinstance(changed_fields["genres"], list):
                    if "TCON" in audio:
                        del audio["TCON"]
                elif "genre" in changed_fields:
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
                if "artists" in changed_fields and isinstance(changed_fields["artists"], list) and changed_fields["artists"]:
                    audio["TPE1"] = TPE1(
                        encoding=3, text=[str(v) for v in changed_fields["artists"] if str(v).strip()]
                    )
                elif "artist" in changed_fields:
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
                if "track_number" in changed_fields:
                    audio["TRCK"] = TRCK(
                        encoding=3, text=str(changed_fields["track_number"]))
                # Preserve disc number if exists
                if "disc_number" in original_metadata and original_metadata["disc_number"]:
                    audio["TPOS"] = TPOS(encoding=3, text=str(
                        original_metadata["disc_number"]))
                # Preserve compilation flag if exists
                if "compilation" in original_metadata and original_metadata["compilation"]:
                    audio["TCMP"] = TCMP(
                        encoding=3, text=original_metadata["compilation"])

                audio.save()
                self._last_audio_tag_write_had_changes = True
                self.logger.info("Updated tags (MP3): %s | fields: %s",
                                 file_path.name, ", ".join(sorted(changed_fields.keys())))
                return True

            if ext == ".m4a":
                from mutagen.mp4 import MP4

                audio = MP4(file_path)

                # Always sanitize existing on-disk genre tags.
                from app.features.genre_guard import sanitize_genre_values

                audio_tags = cast(Any, audio.tags)
                current_audio_genres = audio_tags.get(
                    '\xa9gen', []) if audio_tags is not None else []
                if current_audio_genres:
                    sanitized, removed = sanitize_genre_values(
                        file_path,
                        current_audio_genres,
                        track_cycle_stats=False,
                    )
                    normalized_current_audio_genres = self._normalize_genre_values(
                        sanitized
                    )
                    needs_sanitizer_cleanup = sanitized != current_audio_genres
                    needs_normalization_cleanup = normalized_current_audio_genres != sanitized
                    if (
                        removed
                        or needs_sanitizer_cleanup
                        or needs_normalization_cleanup
                    ):
                        changed_fields['genres'] = normalized_current_audio_genres
                        if removed:
                            self.logger.info(
                                "Forcing genre cleanup for %s: removed %s invalid",
                                file_path.name,
                                len(removed),
                            )
                        else:
                            self.logger.info(
                                "Forcing genre normalization for %s: canonicalized existing genre values",
                                file_path.name,
                            )

                preferred_genres = self._normalize_genre_values(
                    final_metadata.get("genres")
                    if isinstance(final_metadata.get("genres"), list)
                    else changed_fields.get("genres")
                )

                if preferred_genres:
                    audio["\xa9gen"] = [
                        str(v) for v in preferred_genres if str(v).strip()]
                elif "genres" in changed_fields or "genre" in changed_fields:
                    single_genre = str(
                        changed_fields.get("genre") or "").strip()
                    if single_genre:
                        audio["\xa9gen"] = [single_genre]
                    elif audio_tags is not None and "\xa9gen" in audio_tags:
                        del audio_tags["\xa9gen"]
                if "title" in changed_fields:
                    audio["\xa9nam"] = [str(changed_fields["title"])]
                if "artists" in changed_fields and isinstance(changed_fields["artists"], list) and changed_fields["artists"]:
                    audio["\xa9ART"] = [
                        str(v) for v in changed_fields["artists"] if str(v).strip()]
                elif "artist" in changed_fields:
                    audio["\xa9ART"] = [str(changed_fields["artist"])]
                if "album_artist" in changed_fields:
                    audio["aART"] = [str(changed_fields["album_artist"])]
                if "album" in changed_fields:
                    audio["\xa9alb"] = [str(changed_fields["album"])]
                if "year" in changed_fields:
                    audio["\xa9day"] = [str(changed_fields["year"])]
                if "track_number" in changed_fields:
                    track_text = str(
                        changed_fields["track_number"] or "").strip()
                    track_match = re.match(
                        r"^(\d+)(?:\s*/\s*(\d+))?$", track_text)
                    if track_match:
                        track_num = int(track_match.group(1))
                        total = int(track_match.group(
                            2)) if track_match.group(2) else 0
                        audio["trkn"] = [(track_num, total)]
                if "isrc" in changed_fields:
                    audio["ISRC"] = [str(changed_fields["isrc"])]

                audio.save()
                self._last_audio_tag_write_had_changes = True
                self.logger.info("Updated tags (M4A): %s | fields: %s",
                                 file_path.name, ", ".join(sorted(changed_fields.keys())))
                return True

            self.logger.info(
                "Tag update not implemented for format %s (%s)", ext, file_path.name)
            return True
        except Exception as exc:
            self._last_audio_tag_write_had_changes = False
            self.logger.error(
                f"Failed to update tags for {file_path.name}: {exc}")
            return False

    def clean_invalid_genres_in_file(
        self,
        file_path: Path,
        dry_run: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Remove invalid genres and normalize artist/genre naming in-place."""
        result = {
            "file": str(file_path),
            "processed": False,
            "updated": False,
            "removed_genres": [],
            "error": "",
        }

        if not file_path.exists() or not self.pode_processar(file_path):
            return result

        try:
            current = self._read_audio_tags(file_path)
            if not current:
                result["processed"] = True
                return result

            cleaned = self._sanitize_polluted_genre_from_metadata(
                current, file_path)
            cleaned = self._normalize_metadata_values(cleaned)

            raw_before = []
            if isinstance(current.get("genres"), list):
                raw_before.extend([str(v).strip()
                                  for v in current["genres"] if str(v).strip()])
            if str(current.get("genre") or "").strip():
                raw_before.append(str(current.get("genre")).strip())

            filtered_before, removed = sanitize_genre_values(
                file_path,
                raw_before,
                logger=self.logger,
                track_cycle_stats=False,
            )
            _ = filtered_before

            if dry_run is None:
                effective_dry_run = self.dry_run
            else:
                effective_dry_run = dry_run

            previous_dry_run = self.dry_run
            self.dry_run = effective_dry_run
            try:
                updated = self._update_audio_tags(
                    file_path=file_path,
                    original_metadata=current,
                    final_metadata=cleaned,
                    online_metadata=None,
                    force_overwrite_fields={
                        "genre", "genres", "artist", "artists", "album_artist"},
                )
            finally:
                self.dry_run = previous_dry_run

            result["processed"] = True
            result["updated"] = bool(
                updated and self._last_audio_tag_write_had_changes)
            result["removed_genres"] = removed
            return result
        except Exception as exc:
            result["processed"] = True
            result["error"] = str(exc)
            return result

    def clean_invalid_genres_in_directory(
        self,
        root_path: Path,
        dry_run: Optional[bool] = None,
    ) -> Dict[str, int]:
        """Batch-clean invalid genres in all supported audio files under root."""
        report = {
            "total_files": 0,
            "processed": 0,
            "updated": 0,
            "removed_genre_values": 0,
            "errors": 0,
        }

        if not root_path.exists() or not root_path.is_dir():
            return report

        audio_files = [
            p for p in root_path.rglob("*")
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS
        ]
        report["total_files"] = len(audio_files)

        for idx, file_path in enumerate(audio_files, start=1):
            if idx == 1 or idx % 100 == 0 or idx == len(audio_files):
                self.logger.info(
                    "Genre pre-clean progress: %d/%d",
                    idx,
                    len(audio_files),
                )

            outcome = self.clean_invalid_genres_in_file(
                file_path, dry_run=dry_run)
            if not outcome.get("processed"):
                continue

            report["processed"] += 1
            report["removed_genre_values"] += len(
                outcome.get("removed_genres", []))
            if outcome.get("updated"):
                report["updated"] += 1
            if outcome.get("error"):
                report["errors"] += 1

        return report

    def reprocess_db_tracks_with_invalid_genres(
        self,
        dry_run: Optional[bool] = None,
    ) -> Dict[str, int]:
        """Scan database music records for invalid genres and reprocess affected tracks."""
        from datetime import datetime
        from tinydb import Query

        def _log_recheck_stage(title: str) -> None:
            self.logger.info("")
            self.logger.info("%s", "-" * 80)
            self.logger.info("Music | DB RECHECK | %s", title)
            self.logger.info("%s", "-" * 80)

        if dry_run is None:
            effective_dry_run = self.dry_run
        else:
            effective_dry_run = dry_run

        report = {
            "music_records_scanned": 0,
            "tracks_flagged_invalid_genres": 0,
            "tracks_flagged_genre_normalization": 0,
            "db_metadata_updates": 0,
            "tracks_reprocessed": 0,
            "tracks_updated": 0,
            "removed_genre_values": 0,
            "file_errors": 0,
        }

        records = self.database.media_table.all()
        Media = Query()
        _log_recheck_stage("TRACK PASS START")

        for record in records:
            metadata = dict(record.get("metadata") or {})
            organized_path = Path(str(record.get("organized_path") or ""))
            if not self._is_music_record_for_recheck(metadata, organized_path):
                continue

            report["music_records_scanned"] += 1

            current_genres: List[str] = []
            genres_value = metadata.get("genres") or []
            if isinstance(genres_value, list):
                current_genres.extend(
                    [str(v).strip() for v in genres_value if str(v).strip()]
                )
            single_genre = str(metadata.get("genre") or "").strip()
            if single_genre:
                current_genres.append(single_genre)

            if not current_genres:
                continue

            record_path = Path(
                str(record.get("organized_path")
                    or record.get("original_path") or ".")
            )
            filtered, removed = sanitize_genre_values(
                record_path,
                current_genres,
                logger=self.logger,
                track_cycle_stats=False,
            )

            normalized_filtered = self._normalize_genre_values(filtered)
            current_normalized = self._normalize_genre_values(current_genres)
            needs_normalization = current_normalized != normalized_filtered

            if not removed and not needs_normalization:
                continue

            track_label = str(record.get("organized_path") or "")
            if track_label:
                track_label = Path(track_label).name
            else:
                track_label = Path(
                    str(record.get("original_path") or "unknown")).name

            _log_recheck_stage(
                f"TRACK START | file={track_label} | removed_invalid={len(removed)} | needs_normalization={int(needs_normalization)}"
            )

            if removed:
                report["tracks_flagged_invalid_genres"] += 1
            if needs_normalization:
                report["tracks_flagged_genre_normalization"] += 1
            report["removed_genre_values"] += len(removed)

            cleaned_metadata = dict(metadata)
            cleaned_metadata["genres"] = normalized_filtered
            cleaned_metadata["genre"] = normalized_filtered[0] if normalized_filtered else ""

            if cleaned_metadata != metadata:
                report["db_metadata_updates"] += 1
                if not effective_dry_run:
                    update_payload = {
                        "metadata": cleaned_metadata,
                        "last_checked": datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S"),
                    }

                    organized_path = str(record.get("organized_path") or "")
                    original_path = str(record.get("original_path") or "")
                    if organized_path:
                        self.database.media_table.update(
                            update_payload,
                            Media.organized_path == organized_path,
                        )
                    elif original_path:
                        self.database.media_table.update(
                            update_payload,
                            Media.original_path == original_path,
                        )

            organized_path = Path(str(record.get("organized_path") or ""))
            if not organized_path.exists() or not self.pode_processar(organized_path):
                report["file_errors"] += 1
                continue

            outcome = self.clean_invalid_genres_in_file(
                organized_path,
                dry_run=effective_dry_run,
            )

            if outcome.get("processed"):
                report["tracks_reprocessed"] += 1
            if outcome.get("updated"):
                report["tracks_updated"] += 1
            if outcome.get("error"):
                report["file_errors"] += 1

            _log_recheck_stage(
                f"TRACK END | file={track_label} | processed={int(bool(outcome.get('processed')))} | updated={int(bool(outcome.get('updated')))} | error={int(bool(outcome.get('error')))}"
            )

        _log_recheck_stage("TRACK PASS END")

        return report

    def reprocess_db_tracks_with_album_identity(
        self,
        dry_run: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Normalize album identity fields across organized music tracks."""
        from datetime import datetime
        from tinydb import Query

        if dry_run is None:
            effective_dry_run = self.dry_run
        else:
            effective_dry_run = dry_run

        report: Dict[str, Any] = {
            "music_records_scanned": 0,
            "album_groups_scanned": 0,
            "album_groups_with_variants": 0,
            "track_groups_with_inconsistencies": 0,
            "path_album_mismatches": 0,
            "tracks_updated": 0,
            "files_skipped": 0,
            "file_errors": 0,
            "groups": [],
        }

        records = self.database.media_table.all()
        Media = Query()
        grouped: Dict[tuple[str, str],
                      List[Dict[str, Any]]] = defaultdict(list)
        seen_organized_paths: set[str] = set()

        for record in records:
            metadata = dict(record.get("metadata") or {})
            organized_path = Path(str(record.get("organized_path") or ""))
            if not self._is_music_record_for_recheck(metadata, organized_path):
                continue

            organized_path = Path(str(record.get("organized_path") or ""))
            if not organized_path.exists() or not self.pode_processar(organized_path):
                report["files_skipped"] += 1
                continue

            # Same organized file can appear multiple times in DB (legacy duplicates).
            # Recheck each physical file only once to avoid repeated track rewrites.
            organized_path_key = str(organized_path)
            if organized_path_key in seen_organized_paths:
                report["files_skipped"] += 1
                continue
            seen_organized_paths.add(organized_path_key)

            current_metadata = self._read_audio_tags(organized_path)
            if not current_metadata:
                report["files_skipped"] += 1
                continue

            report["music_records_scanned"] += 1
            grouped[self._normalize_album_identity(current_metadata)].append(
                {
                    "record": record,
                    "metadata": current_metadata,
                    "path": organized_path,
                }
            )

        for group_key, items in grouped.items():
            report["album_groups_scanned"] += 1
            album_values = [
                str(item["metadata"].get("album") or "").strip()
                for item in items
                if str(item["metadata"].get("album") or "").strip()
            ]
            album_artist_values = [
                self._get_primary_artist(
                    str(
                        item["metadata"].get("album_artist")
                        or item["metadata"].get("artist")
                        or ""
                    )
                )
                for item in items
                if str(
                    item["metadata"].get("album_artist")
                    or item["metadata"].get("artist")
                    or ""
                ).strip()
            ]
            year_values = [
                year for year in (
                    self._extract_release_year(item["metadata"]) for item in items
                ) if year is not None
            ]

            canonical_album = self._prefer_album_variant(
                [self._normalize_album_name(value) for value in album_values]
            )
            canonical_album_artist = self._prefer_album_variant(
                album_artist_values)
            canonical_year = max(
                year_values,
                key=lambda value: (year_values.count(value), -value),
                default=None,
            )

            if not canonical_album:
                canonical_album = self._normalize_album_name(
                    album_values[0] if album_values else ""
                )
            if not canonical_album_artist:
                canonical_album_artist = self._get_primary_artist(
                    album_artist_values[0] if album_artist_values else ""
                )

            needs_normalization = (
                len(set(album_values)) > 1
                or len(set(album_artist_values)) > 1
                or len(set(year_values)) > 1
            )

            track_entries: List[Dict[str, Any]] = []
            for item in items:
                current_metadata = item["metadata"]
                file_path = item["path"]
                disc_num = self._parse_numeric_tag_value(
                    current_metadata.get("disc_number")) or 1
                track_num = self._parse_numeric_tag_value(
                    current_metadata.get("track_number"))
                filename_track = self._extract_track_from_filename(file_path)
                title_value = str(
                    current_metadata.get("title") or file_path.stem or "").strip().casefold()
                track_entries.append(
                    {
                        "item": item,
                        "disc": disc_num,
                        "track": track_num,
                        "filename_track": filename_track,
                        "title": title_value,
                    }
                )

            keyed_tracks = [
                (entry["disc"], entry["track"])
                for entry in track_entries
                if entry["track"] is not None
            ]
            has_missing_track = any(
                entry["track"] is None for entry in track_entries)
            has_duplicate_track = len(set(keyed_tracks)) != len(keyed_tracks)
            needs_track_rebuild = len(track_entries) > 1 and (
                has_missing_track or has_duplicate_track
            )

            track_targets: Dict[int, str] = {}
            if needs_track_rebuild:
                report["track_groups_with_inconsistencies"] += 1
                ordered_entries = sorted(
                    track_entries,
                    key=lambda entry: (
                        entry["disc"],
                        entry["filename_track"] if entry["filename_track"] is not None else 10_000,
                        entry["track"] if entry["track"] is not None else 10_000,
                        entry["title"],
                        entry["item"]["path"].name.casefold(),
                    ),
                )
                current_disc = None
                next_track = 0
                for entry in ordered_entries:
                    disc_num = int(entry["disc"])
                    if current_disc != disc_num:
                        current_disc = disc_num
                        next_track = 1
                    target_track = str(next_track)
                    track_targets[id(entry["item"])] = target_track
                    next_track += 1

            if needs_normalization:
                report["album_groups_with_variants"] += 1
                report["groups"].append(
                    {
                        "album": canonical_album,
                        "artist": canonical_album_artist,
                        "years": sorted(set(year_values)),
                        "album_variants": sorted(set(album_values)),
                        "album_artist_variants": sorted(set(album_artist_values)),
                        "track_inconsistency": bool(needs_track_rebuild),
                        "tracks": len(items),
                    }
                )

            for item in items:
                file_path: Path = item["path"]
                current_metadata = item["metadata"]
                final_metadata = dict(current_metadata)
                final_metadata["album"] = canonical_album
                final_metadata["album_artist"] = canonical_album_artist
                final_metadata["primary_artist"] = canonical_album_artist

                expected_album_from_path = self._infer_album_from_library_path(
                    file_path)
                # Apply path-based correction only when group is otherwise stable.
                # If this group already has album variants, prefer canonical group name.
                if expected_album_from_path and not needs_normalization:
                    current_album_norm = self._normalize_album_name(
                        str(current_metadata.get("album") or "")
                    )
                    if not current_album_norm or current_album_norm.casefold() != expected_album_from_path.casefold():
                        final_metadata["album"] = expected_album_from_path
                        report["path_album_mismatches"] += 1

                if canonical_year is not None:
                    final_metadata["year"] = canonical_year
                if needs_track_rebuild:
                    target_track_number = track_targets.get(id(item))
                    if target_track_number:
                        final_metadata["track_number"] = target_track_number

                needs_year_cleanup = self._has_legacy_year_tag(file_path)

                should_update = (
                    self._normalize_album_name(
                        str(current_metadata.get("album") or ""))
                    != self._normalize_album_name(
                        str(final_metadata.get("album") or ""))
                    or self._get_primary_artist(
                        str(
                            current_metadata.get("album_artist")
                            or current_metadata.get("artist")
                            or ""
                        )
                    ) != canonical_album_artist
                    or self._extract_release_year(current_metadata) != canonical_year
                    or (
                        needs_track_rebuild
                        and self._normalize_track_number_for_compare(current_metadata.get("track_number"))
                        != self._normalize_track_number_for_compare(final_metadata.get("track_number"))
                    )
                    or needs_year_cleanup
                )

                if not should_update:
                    continue

                if effective_dry_run:
                    report["tracks_updated"] += 1
                    continue

                updated = self._update_audio_tags(
                    file_path=file_path,
                    original_metadata=current_metadata,
                    final_metadata=final_metadata,
                    online_metadata=None,
                    force_overwrite_fields={
                        "album", "album_artist", "year", "track_number"},
                    normalize_release_year_cleanup=True,
                )
                if updated:
                    report["tracks_updated"] += 1
                    updated_metadata = dict(
                        item["record"].get("metadata") or {})
                    updated_metadata.update(current_metadata)
                    updated_metadata["album"] = canonical_album
                    updated_metadata["album_artist"] = canonical_album_artist
                    updated_metadata["primary_artist"] = canonical_album_artist
                    if canonical_year is not None:
                        updated_metadata["year"] = canonical_year
                    if needs_track_rebuild and str(final_metadata.get("track_number") or "").strip():
                        updated_metadata["track_number"] = str(
                            final_metadata.get("track_number")).strip()
                    update_payload = {
                        "metadata": updated_metadata,
                        "last_checked": datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S"),
                    }
                    record = item["record"]
                    organized_path = str(record.get("organized_path") or "")
                    original_path = str(record.get("original_path") or "")
                    if organized_path:
                        self.database.media_table.update(
                            update_payload,
                            Media.organized_path == organized_path,
                        )
                    elif original_path:
                        self.database.media_table.update(
                            update_payload,
                            Media.original_path == original_path,
                        )
                else:
                    report["file_errors"] += 1

        return report

    async def backfill_music_album_metadata(self, dry_run: bool = True) -> Dict[str, Any]:
        """Normalize album identity metadata across organized music tracks."""
        report = self.reprocess_db_tracks_with_album_identity(dry_run=dry_run)
        report["dry_run"] = dry_run
        return report

    def _build_music_organization_context(self, file_path: Path) -> Dict[str, Any]:
        """Build baseline metadata/destination context for one music file."""
        existing_meta = self._sanitize_polluted_genre_from_metadata(
            self._read_audio_tags(file_path),
            file_path,
        )
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

        return {
            "existing_meta": existing_meta,
            "filename_meta": filename_meta,
            "baseline_meta": baseline_meta,
            "baseline_dest": baseline_dest,
        }

    async def _resolve_enrichment_policy_with_retry(
        self,
        *,
        file_path: Path,
        existing_meta: Dict[str, Any],
        filename_meta: Dict[str, Any],
        baseline_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Resolve online enrichment policy (including retry queue behavior)."""
        online_meta: Dict[str, Any] = {}
        missing_before_online: List[str] = []
        should_complement_genres = False
        complement_reason = "not_evaluated"
        enrichment_status = "disabled"
        enrichment_error = ""

        if self.config.enrich_music_metadata_online:
            # Calculate against raw file tags; only true gaps should trigger lookups.
            missing_before_online = self._calculate_missing_fields(
                existing_meta)
            should_complement_genres, complement_reason = self._complement_genre_decision(
                existing_meta
            )
            if missing_before_online or should_complement_genres:
                enrichment_reason = ",".join(
                    missing_before_online) if missing_before_online else "genre"
                enrichment_status = "started"
                self.logger.info(
                    "Metadata enrichment start: %s | missing-targets=%s | complement-genres=%s | complement-reason=%s",
                    file_path.name,
                    enrichment_reason,
                    should_complement_genres,
                    complement_reason,
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
                            ) or should_complement_genres,
                        ),
                        timeout=self.config.music_metadata_api_timeout_seconds,
                    )
                    enrichment_status = "success" if online_meta else "empty_result"
                    self.logger.info(
                        "Metadata enrichment done: %s | status=%s | genre-in-result=%s",
                        file_path.name,
                        enrichment_status,
                        bool(self._coerce_genre_list(online_meta)),
                    )
                except asyncio.TimeoutError:
                    enrichment_status = "timeout"
                    enrichment_error = "timeout"
                    self.logger.warning(
                        "Metadata enrichment timed out for %s; continuing without online data",
                        file_path.name,
                    )
                except Exception as exc:
                    enrichment_status = "request_error"
                    enrichment_error = str(exc)
                    self.logger.warning(
                        "Metadata enrichment failed for %s; continuing without online data: %s",
                        file_path.name,
                        exc,
                    )
            else:
                enrichment_status = "skipped_no_gaps"
                self.logger.info(
                    "Metadata enrichment skipped (no gaps): %s",
                    file_path.name,
                )
            if not missing_before_online and should_complement_genres:
                self.logger.info(
                    "Metadata enrichment complement enabled for %s",
                    file_path.name,
                )
            if (
                not should_complement_genres
                and "genre" in set(missing_before_online)
            ):
                self.logger.info(
                    "Genre complement not requested for %s | reason=%s",
                    file_path.name,
                    complement_reason,
                )

        final_meta = self._determine_final_metadata(
            existing_tags_metadata=existing_meta,
            filename_metadata=filename_meta,
            file_path=file_path,
            online_metadata=online_meta,
            complement_genres=should_complement_genres,
        )

        genre_still_missing = self._is_missing_genre_after_processing(
            final_meta)
        should_retry_genre_enrichment = (
            "genre" in set(missing_before_online)
            and genre_still_missing
            and enrichment_status in {"timeout", "request_error", "empty_result"}
        )
        if should_retry_genre_enrichment:
            self.logger.info(
                "Retrying genre enrichment for %s | previous-status=%s",
                file_path.name,
                enrichment_status,
            )
            try:
                retry_online_meta = await asyncio.wait_for(
                    self._fetch_online_music_metadata(
                        file_path,
                        baseline_meta,
                        needs_genre=True,
                    ),
                    timeout=self.config.music_metadata_api_timeout_seconds,
                )
                if retry_online_meta:
                    retry_final_meta = self._determine_final_metadata(
                        existing_tags_metadata=existing_meta,
                        filename_metadata=filename_meta,
                        file_path=file_path,
                        online_metadata=retry_online_meta,
                        complement_genres=should_complement_genres,
                    )
                    if not self._is_missing_genre_after_processing(retry_final_meta):
                        final_meta = retry_final_meta
                        online_meta = retry_online_meta
                        enrichment_status = "retry_success"
                        genre_still_missing = False
                    else:
                        enrichment_status = "retry_empty_genre"
                else:
                    enrichment_status = "retry_empty_result"
            except asyncio.TimeoutError:
                enrichment_status = "retry_timeout"
                enrichment_error = "retry_timeout"
                self.logger.warning(
                    "Genre enrichment retry timed out for %s",
                    file_path.name,
                )
            except Exception as exc:
                enrichment_status = "retry_request_error"
                enrichment_error = str(exc)
                self.logger.warning(
                    "Genre enrichment retry failed for %s: %s",
                    file_path.name,
                    exc,
                )

        if "genre" in set(missing_before_online) and genre_still_missing:
            self.logger.warning(
                "Genre enrichment unresolved for %s | enrichment-status=%s | complement-genres=%s | complement-reason=%s",
                file_path.name,
                enrichment_status,
                should_complement_genres,
                complement_reason,
            )
            self._enqueue_genre_enrichment_retry(
                {
                    "queued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "source_path": str(file_path),
                    "intended_destination": str(self.get_destination_path(file_path, final_meta)),
                    "missing_targets": missing_before_online,
                    "enrichment_status": enrichment_status,
                    "enrichment_error": enrichment_error,
                    "complement_genres": should_complement_genres,
                    "complement_reason": complement_reason,
                }
            )

        return {
            "online_meta": online_meta,
            "missing_before_online": missing_before_online,
            "should_complement_genres": should_complement_genres,
            "complement_reason": complement_reason,
            "enrichment_status": enrichment_status,
            "enrichment_error": enrichment_error,
            "final_meta": final_meta,
        }

    def _persist_music_tags_with_verification(
        self,
        *,
        file_path: Path,
        existing_meta: Dict[str, Any],
        final_meta: Dict[str, Any],
        online_meta: Dict[str, Any],
    ) -> Optional[OrganizationResult]:
        """Persist tag updates and verify genre persistence when required."""
        tags_updated = self._update_audio_tags(
            file_path,
            existing_meta,
            final_meta,
            online_meta,
        )
        if not tags_updated:
            return OrganizationResult(
                success=False,
                error_message="Tag update failed; organization aborted before database write",
            )

        if not self.dry_run:
            genres_persisted = self._verify_and_repair_genre_persistence(
                file_path=file_path,
                final_metadata=final_meta,
                online_metadata=online_meta,
            )
            if not genres_persisted:
                return OrganizationResult(
                    success=False,
                    error_message="Genre persistence mismatch after retry; organization aborted before database write",
                )

        return None

    async def _run_music_organization_pipeline(
        self,
        *,
        file_path: Path,
        context: Dict[str, Any],
    ) -> OrganizationResult:
        """Run the music organization pipeline from prepared context."""
        existing_meta = context["existing_meta"]
        filename_meta = context["filename_meta"]
        baseline_meta = context["baseline_meta"]
        baseline_dest = context["baseline_dest"]

        early_skip = self._early_skip_if_conflict(
            file_path,
            baseline_dest,
            baseline_meta,
        )
        if early_skip:
            return early_skip

        enrichment = await self._resolve_enrichment_policy_with_retry(
            file_path=file_path,
            existing_meta=existing_meta,
            filename_meta=filename_meta,
            baseline_meta=baseline_meta,
        )
        final_meta = enrichment["final_meta"]
        online_meta = enrichment["online_meta"]

        final_dest = self.get_destination_path(file_path, final_meta)
        if final_dest != baseline_dest:
            early_skip = self._early_skip_if_conflict(
                file_path,
                final_dest,
                final_meta,
            )
            if early_skip:
                return early_skip

        persistence_error = self._persist_music_tags_with_verification(
            file_path=file_path,
            existing_meta=existing_meta,
            final_meta=final_meta,
            online_meta=online_meta,
        )
        if persistence_error is not None:
            return persistence_error

        return await self.organizar_file(file_path, final_dest, final_meta)

    async def organizar(self, file_path: Path) -> OrganizationResult:
        if self.database.is_file_organized(str(file_path)):
            return OrganizationResult(
                success=True,
                skipped=True,
                skip_reason="already_registered_in_database",
            )

        # Clean original file tags before destination/metadata decisions.
        self.clean_invalid_genres_in_file(file_path)

        context = self._build_music_organization_context(file_path)
        return await self._run_music_organization_pipeline(
            file_path=file_path,
            context=context,
        )

    def pode_processar(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in AUDIO_EXTS

    def obter_tipo_midia(self) -> MediaType:
        return MediaType.MUSIC

    def get_destination_path(self, file_path: Path, metadata: Dict[str, Any]) -> Path:
        artist_value = metadata.get("primary_artist") or metadata.get(
            "artist", "Unknown Artist")
        artist = self.sanitize_author(
            self._get_primary_artist(str(artist_value)))

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

    async def backfill_music_genres(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Backfill genre metadata for all organized music tracks.

        Uses improved online enrichment with MusicBrainz primary + Last.fm fallback.
        Skips files that already have genre set.

        Args:
            dry_run: If True, reports changes without applying them

        Returns:
            Report dictionary with statistics
        """
        from app.metadata.metadata import extract_audio_metadata

        report = {
            "total_tracks_processed": 0,
            "tracks_enriched_from_musicbrainz": 0,
            "tracks_enriched_from_lastfm": 0,
            "tracks_skipped_already_has_genre": 0,
            "tracks_with_no_genre_found": 0,
            "tracks_with_file_errors": 0,
            "cleaning_files_processed": 0,
            "cleaning_files_updated": 0,
            "cleaning_removed_genre_values": 0,
            "dry_run": dry_run,
            "enriched_tracks": [],
            "skipped_tracks": [],
            "error_tracks": [],
        }

        records = self.database.media_table.all()
        self.logger.info(
            "Backfill: Starting genre enrichment for %d organized tracks", len(records))

        for idx, record in enumerate(records):
            track_organized_path = record.get("organized_path")
            if not track_organized_path:
                continue

            file_path = Path(track_organized_path)
            if not file_path.exists():
                report["tracks_with_file_errors"] += 1
                report["error_tracks"].append({
                    "file": str(file_path),
                    "reason": "File not found"
                })
                continue

            if not self.pode_processar(file_path):
                continue

            report["total_tracks_processed"] += 1

            # Log progress every 50 tracks
            if (idx + 1) % 50 == 0:
                self.logger.info(
                    "Backfill progress: %d/%d tracks processed", idx + 1, len(records))

            try:
                # Always clean invalid genres on organized and original files first.
                paths_to_clean = [file_path]
                original_path_value = record.get("original_path")
                if original_path_value:
                    original_path = Path(str(original_path_value))
                    if original_path.exists() and original_path not in paths_to_clean:
                        paths_to_clean.append(original_path)

                for candidate_path in paths_to_clean:
                    outcome = self.clean_invalid_genres_in_file(
                        candidate_path, dry_run=dry_run)
                    if outcome.get("processed"):
                        report["cleaning_files_processed"] += 1
                        report["cleaning_removed_genre_values"] += len(
                            outcome.get("removed_genres", []))
                    if outcome.get("updated"):
                        report["cleaning_files_updated"] += 1
                    if outcome.get("error"):
                        report["tracks_with_file_errors"] += 1
                        report["error_tracks"].append({
                            "file": str(candidate_path),
                            "reason": f"genre_clean_error: {outcome.get('error')}",
                        })

                # Extract current metadata from file tags
                existing_meta = self._sanitize_polluted_genre_from_metadata(
                    extract_audio_metadata(file_path, self.logger),
                    file_path,
                )

                # Legacy fix: if existing genre matches original download folder
                # name, treat it as missing and re-enrich.
                original_path_value = record.get("original_path")
                if original_path_value:
                    original_path = Path(str(original_path_value))
                    if self._is_folder_name_genre_match(original_path, existing_meta.get("genre")):
                        self.logger.info(
                            "Backfill: clearing polluted folder-name genre for %s: %s",
                            file_path.name,
                            existing_meta.get("genre"),
                        )
                        existing_meta["genre"] = ""
                        if isinstance(existing_meta.get("genres"), list):
                            existing_meta["genres"] = []

                # If file already has genre, skip it
                if not self._is_missing(existing_meta.get("genre")):
                    report["tracks_skipped_already_has_genre"] += 1
                    report["skipped_tracks"].append({
                        "file": file_path.name,
                        "genre": existing_meta.get("genre")
                    })
                    continue

                # Enrich with online sources
                try:
                    online_meta = await asyncio.wait_for(
                        enrich_music_metadata_with_online_sources(
                            file_path=file_path,
                            existing_metadata=existing_meta,
                            logger=self.logger,
                            lastfm_api_key=self.config.lastfm_api_key,
                            min_confidence=85,
                            api_delay_seconds=self.config.music_metadata_api_delay_seconds,
                            max_retries=self.config.music_metadata_api_max_retries,
                            fetch_lastfm=True,
                            request_timeout_seconds=12.0,
                        ),
                        timeout=15.0
                    )
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "Backfill: Metadata enrichment timed out for %s", file_path.name)
                    online_meta = {}

                # Check if we got a genre from enrichment
                if self._is_missing(online_meta.get("genre")):
                    report["tracks_with_no_genre_found"] += 1
                    continue

                # Determine source of genre
                enrichment_source = str(
                    online_meta.get("genre_source") or "lastfm")
                genre_value = online_meta.get("genre")

                # Prepare final metadata
                final_meta = self._determine_final_metadata(
                    existing_tags_metadata=existing_meta,
                    filename_metadata={},
                    file_path=file_path,
                    online_metadata=online_meta,
                )

                if not dry_run:
                    # Apply tags
                    updated = self._update_audio_tags(
                        file_path, existing_meta, final_meta, online_meta)
                    if not updated:
                        report["tracks_with_file_errors"] += 1
                        report["error_tracks"].append({
                            "file": file_path.name,
                            "reason": "tag_update_failed",
                        })
                        continue

                report["enriched_tracks"].append({
                    "file": file_path.name,
                    "genre": genre_value,
                    "source": enrichment_source,
                    "dry_run": dry_run,
                })

                if enrichment_source == "musicbrainz":
                    report["tracks_enriched_from_musicbrainz"] += 1
                else:
                    report["tracks_enriched_from_lastfm"] += 1

            except Exception as e:
                report["tracks_with_file_errors"] += 1
                report["error_tracks"].append({
                    "file": file_path.name,
                    "reason": str(e)
                })
                self.logger.error(
                    "Backfill: Error processing %s: %s", file_path.name, e)

        report["total_enriched"] = (
            report["tracks_enriched_from_musicbrainz"] +
            report["tracks_enriched_from_lastfm"]
        )

        self.logger.info(
            "Backfill completed: total=%d processed=%d | "
            "musicbrainz=%d lastfm=%d skipped=%d no_genre=%d errors=%d",
            len(records),
            report["total_tracks_processed"],
            report["tracks_enriched_from_musicbrainz"],
            report["tracks_enriched_from_lastfm"],
            report["tracks_skipped_already_has_genre"],
            report["tracks_with_no_genre_found"],
            report["tracks_with_file_errors"],
        )

        return report


class MusicSidecarOrganizerBase(BaseOrganizer):
    """Shared helpers for music sidecar organizers (lyrics/artwork)."""

    AUDIO_EXTS = AUDIO_EXTS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.library_path = self.config.library_path_music
        self._available_audio_paths: Optional[Dict[str, Path]] = None

    def _iter_music_download_roots(self) -> List[Path]:
        roots: List[Path] = []
        if self.config.download_path_music:
            roots.append(Path(self.config.download_path_music))
        return roots

    def _build_available_audio_index(self) -> Dict[str, Path]:
        """Build index of all available audio files across download roots."""
        if self._available_audio_paths is not None:
            return self._available_audio_paths

        index: Dict[str, Path] = {}
        for download_path in self._iter_music_download_roots():
            if not download_path.exists():
                continue
            for ext in self.AUDIO_EXTS:
                for audio_file in download_path.rglob(f"*{ext}"):
                    if not audio_file.is_file():
                        continue
                    key = audio_file.stem.lower().strip()
                    if key and key not in index:
                        index[key] = audio_file

        self._available_audio_paths = index
        return index

    def _find_audio_pairs(self, sidecar_file: Path, *, include_fuzzy: bool = False) -> List[Path]:
        """Find matching audio files for sidecar files."""
        pairs: List[Path] = []
        sidecar_stem = sidecar_file.stem.lower().strip()

        # First: same-folder matches
        for ext in self.AUDIO_EXTS:
            same_folder_match = sidecar_file.with_suffix(ext)
            if same_folder_match.exists():
                pairs.append(same_folder_match)

        # Second: exact stem match in global index
        if not pairs and sidecar_stem:
            audio_index = self._build_available_audio_index()
            if sidecar_stem in audio_index:
                pairs.append(audio_index[sidecar_stem])

        # Third: optional fuzzy matching for cases where filenames drift.
        if include_fuzzy and not pairs and sidecar_stem:
            audio_index = self._build_available_audio_index()
            for audio_key, audio_path in audio_index.items():
                if sidecar_stem in audio_key or audio_key in sidecar_stem:
                    if " - " in sidecar_stem and " - " in audio_key:
                        sidecar_parts = sidecar_stem.split(" - ", 1)
                        audio_parts = audio_key.split(" - ", 1)
                        if sidecar_parts[0].strip() == audio_parts[0].strip():
                            pairs.append(audio_path)
                            break

        return pairs

    def _dest_from_existing_audio_record_for_sidecar(
        self,
        sidecar_file: Path,
        build_dest_from_audio: Callable[[Path, Path], Path],
        *,
        include_fuzzy: bool = False,
    ) -> Optional[Path]:
        for audio_file in self._find_audio_pairs(sidecar_file, include_fuzzy=include_fuzzy):
            record = self.database.get_record_by_original_path(str(audio_file))
            if not record:
                continue

            organized_audio = Path(record.get("organized_path", ""))
            if not organized_audio:
                continue

            return build_dest_from_audio(organized_audio, sidecar_file)

        return None


class LyricsOrganizer(MusicSidecarOrganizerBase):
    """Lyrics organizer for sidecar `.lrc` files."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reuse music destination logic for unmatched DB cases.
        self.music_helper = MusicOrganizer(*args, **kwargs)

    def pode_processar(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".lrc"

    def obter_tipo_midia(self) -> MediaType:
        return MediaType.LYRICS

    def _dest_from_existing_audio_record(self, lyrics_file: Path) -> Optional[Path]:
        return self._dest_from_existing_audio_record_for_sidecar(
            lyrics_file,
            lambda organized_audio, sidecar_file: organized_audio.with_suffix(
                sidecar_file.suffix),
            include_fuzzy=True,
        )

    def _dest_from_audio_metadata(self, lyrics_file: Path) -> Optional[Path]:
        for audio_file in self._find_audio_pairs(lyrics_file, include_fuzzy=True):
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
        # Keep original filename for unmatched lyrics under dedicated folder.
        return self.library_path / "_lyrics_unmatched" / lyrics_file.name

    async def organizar(self, file_path: Path) -> OrganizationResult:
        if self.database.is_file_organized(str(file_path)):
            return OrganizationResult(
                success=True,
                skipped=True,
                skip_reason="already_registered_in_database",
            )

        paired_audio = self._find_audio_pairs(file_path, include_fuzzy=True)

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


class ArtworkOrganizer(MusicSidecarOrganizerBase):
    """Artwork organizer for sidecar cover images in music downloads."""

    IMAGE_EXTS = IMAGE_EXTS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def pode_processar(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.IMAGE_EXTS

    def obter_tipo_midia(self) -> MediaType:
        return MediaType.ARTWORK

    def _dest_from_existing_audio_record(self, image_file: Path) -> Optional[Path]:
        return self._dest_from_existing_audio_record_for_sidecar(
            image_file,
            lambda organized_audio, sidecar_file: organized_audio.parent / sidecar_file.name,
            include_fuzzy=False,
        )

    def _fallback_dest(self, image_file: Path) -> Path:
        return self.library_path / "_artwork_unmatched" / image_file.name

    async def organizar(self, file_path: Path) -> OrganizationResult:
        if self.database.is_file_organized(str(file_path)):
            return OrganizationResult(
                success=True,
                skipped=True,
                skip_reason="already_registered_in_database",
            )

        paired_audio = self._find_audio_pairs(file_path, include_fuzzy=False)
        dest_path = (
            self._dest_from_existing_audio_record(file_path)
            or self._fallback_dest(file_path)
        )

        metadata: Dict[str, Any] = {
            "media_type": "artwork",
            "media_subtype": "cover_image",
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
                headers={
                    "User-Agent": os.getenv(
                        "MUSIC_METADATA_USER_AGENT",
                        "media-organizer/1.0",
                    )
                },
            )
            with urllib.request.urlopen(
                request,
                timeout=self.config.music_metadata_api_timeout_seconds
            ) as response:
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

    def _parse_comicinfo_xml_payload(self, raw: bytes) -> Dict[str, Any]:
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

    def _read_comicinfo_xml(self, file_path: Path) -> Dict[str, Any]:
        """Read ComicInfo.xml from a CBZ(ZIP) archive.

        Kavita uses ComicInfo.xml(v2.1 schema) as the canonical metadata source
        for comics and manga. This method extracts all relevant fields.
        """
        ext = file_path.suffix.lower()
        if ext not in {".cbz", ".cbr"}:
            return {}

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
                        return self._parse_comicinfo_xml_payload(f.read())
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
                return self._parse_comicinfo_xml_payload(content.stdout)
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
            raw = existing.read_bytes()
            return self._parse_comicinfo_xml_payload(raw)
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
                "[DRY RUN] Would generate sidecar .comicinfo.xml for %s -> %s",
                file_path.name,
                sidecar_path.name,
            )
            return True

        try:
            sidecar_path.write_text(xml_content, encoding="utf-8")
            self.logger.info(
                "Generated sidecar .comicinfo.xml for %s -> %s",
                file_path.name,
                sidecar_path.name,
            )
            return True
        except Exception as exc:
            self.logger.warning(
                "Could not write sidecar .comicinfo.xml for %s: %s",
                file_path.name,
                exc,
            )
            return False

    def _sync_comic_sidecar_to_destination(self, source_path: Path, dest_path: Path) -> None:
        """Ensure sidecar metadata follows comics into the destination folder."""
        source_candidates = [
            source_path.parent / f"{source_path.stem}.comicinfo.xml",
            source_path.parent / ".comicinfo.xml",
        ]
        source_sidecar = next(
            (p for p in source_candidates if p.exists() and p.is_file()),
            None,
        )
        if source_sidecar is None:
            return

        # If destination archive already has embedded ComicInfo, sidecar is unnecessary.
        if self._read_comicinfo_xml(dest_path):
            return

        dest_sidecar = dest_path.parent / f"{dest_path.stem}.comicinfo.xml"
        try:
            if source_sidecar.resolve() == dest_sidecar.resolve():
                return
        except Exception:
            pass

        if self.dry_run:
            self.logger.info(
                "[DRY RUN] Would sync sidecar %s -> %s",
                source_sidecar,
                dest_sidecar,
            )
            return

        try:
            dest_sidecar.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source_sidecar), str(dest_sidecar))
            self.logger.info(
                "Synced comic sidecar %s -> %s",
                source_sidecar.name,
                dest_sidecar.name,
            )
        except Exception as exc:
            self.logger.warning(
                "Could not sync comic sidecar to destination for %s: %s",
                source_path.name,
                exc,
            )

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
            if getattr(self.config, "comic_download_covers", False):
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
                self.logger.info(
                    "Embedded ComicInfo.xml inside archive %s",
                    file_path.name,
                )
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
                    "Cannot embed ComicInfo.xml inside CBR %s: no writable tool (rar/7z update); generating sidecar .comicinfo.xml",
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
                    self.logger.info(
                        "Could not embed ComicInfo.xml inside archive %s; generating sidecar .comicinfo.xml | reason=%s",
                        file_path.name,
                        (run.stderr.decode("utf-8", errors="replace")
                         if run.stderr else "tool failed"),
                    )
                    return self._write_comicinfo_sidecar(file_path, xml_content)

                self.logger.info(
                    "Embedded ComicInfo.xml inside archive %s",
                    file_path.name,
                )
                return True
        except Exception as exc:
            if self._write_comicinfo_sidecar(file_path, xml_content):
                self.logger.info(
                    "Could not embed ComicInfo.xml inside archive %s; generating sidecar .comicinfo.xml | reason=%s",
                    file_path.name,
                    exc,
                )
                return True
            else:
                self.logger.warning(
                    "Could not write ComicInfo.xml to %s: %s",
                    file_path.name,
                    exc,
                )
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
        if ext == ".pdf":
            parts = [part.lower() for part in file_path.parts]
            for idx in range(len(parts) - 1):
                if parts[idx] == "downloads" and parts[idx + 1] == "comics":
                    return "comic"
        if ext in {".cbz", ".cbr", ".cb7", ".cbt"}:
            return "comic"
        return "book"

    def _extract_book_metadata(self, file_path: Path) -> Dict[str, Any]:
        parsed = parse_book_filename_fields(file_path.stem)
        metadata: Dict[str, Any] = {
            "title": parsed.get("title") or file_path.stem,
            "author": parsed.get("author") or "Unknown Author",
            "authors": parsed.get("authors") or [],
            "year": parsed.get("year"),
            "series": parsed.get("series"),
            "series_index": parsed.get("series_index"),
            "media_type": "book",
            "media_subtype": "book",
            "filename_schema_valid": bool(parsed.get("is_valid")),
            "filename_schema_error": str(parsed.get("error") or ""),
        }
        return metadata

    def _extract_comic_metadata(self, file_path: Path) -> Dict[str, Any]:
        parsed = parse_comic_filename_fields(file_path.stem)
        base: Dict[str, Any] = {
            "title": parsed.get("title") or "Unknown Title",
            "series": parsed.get("series"),
            "issue_number": parsed.get("issue_number"),
            "publisher": "Unknown",
            "year": parsed.get("year"),
            "media_type": "comic",
            "media_subtype": "comic",
            "filename_schema_valid": bool(parsed.get("is_valid")),
            "filename_schema_error": str(parsed.get("error") or ""),
        }

        return base

    def get_book_destination_path(self, file_path: Path, metadata: Dict[str, Any]) -> Path:
        author = self.sanitize_author(metadata.get("author", "Unknown Author"))
        # Keep all books under a stable author folder; avoid creating one folder per file.
        return self.library_path / author / file_path.name

    def get_comic_destination_path(self, file_path: Path, metadata: Dict[str, Any]) -> Path:
        title = self.sanitize_title(
            str(metadata.get("title") or "Unknown Title"))
        series_value = str(metadata.get("series") or "").strip()
        grouping_series = self.sanitize_title(
            normalize_comic_series_title(series_value or title)
        )
        issue = str(metadata.get("issue_number") or "").strip()
        year = metadata.get("year")

        if issue and isinstance(year, int):
            if series_value:
                file_name = f"{title} ({year}) - {series_value} #{issue}{file_path.suffix}"
            else:
                file_name = f"{title} ({year}) - #{issue}{file_path.suffix}"
        else:
            file_name = file_path.name

        return self.library_path / grouping_series / file_name

    async def organizar(self, file_path: Path) -> OrganizationResult:
        if self.database.is_file_organized(str(file_path)):
            return OrganizationResult(
                success=True,
                skipped=True,
                skip_reason="already_registered_in_database",
            )

        detected_type = self._detect_book_type(file_path)
        final_type = self.book_type if self.book_type != "book" else detected_type

        if final_type == "comic":
            metadata = self._extract_comic_metadata(file_path)
            if not metadata.get("filename_schema_valid"):
                return OrganizationResult(
                    success=True,
                    skipped=True,
                    skip_reason=str(metadata.get(
                        "filename_schema_error") or "comic_schema_invalid"),
                    metadata=metadata,
                )
            dest_path = self.get_comic_destination_path(file_path, metadata)
            early_skip = self._early_skip_if_conflict(
                file_path, dest_path, metadata)
            if early_skip:
                return early_skip
            self._write_comicinfo_xml(file_path, metadata)
            result = await self.organizar_file(file_path, dest_path, metadata)
            return result
        else:
            metadata = self._extract_book_metadata(file_path)
            if not metadata.get("filename_schema_valid"):
                return OrganizationResult(
                    success=True,
                    skipped=True,
                    skip_reason=str(metadata.get(
                        "filename_schema_error") or "book_schema_invalid"),
                    metadata=metadata,
                )

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
            return file_path.suffix.lower() in (COMIC_EXTS | {".pdf"})
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
                skip_reason="already_matches_target_name",
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
