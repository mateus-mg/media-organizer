"""Music quality monitoring utilities."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.features.genre_guard import build_folder_candidates, detect_suspicious_reason


def _normalize(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _split_genre_tokens(value: Any) -> List[str]:
    text = str(value or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in re.split(r",|;", text) if p.strip()]
    return parts or [text]


class MusicQualityMonitor:
    """Generate quality metrics for organized music metadata."""

    def __init__(
        self,
        data_dir: Path,
        organization_path: Optional[Path] = None,
        link_registry_path: Optional[Path] = None,
        expect_artist_in_filename: Optional[bool] = None,
    ):
        self.data_dir = Path(data_dir)
        self.organization_path = Path(
            organization_path) if organization_path else self.data_dir / "organization.json"
        self.link_registry_path = Path(
            link_registry_path) if link_registry_path else self.data_dir / "link_registry.json"
        if expect_artist_in_filename is None:
            expect_artist_in_filename = os.getenv(
                "QUALITY_MONITOR_EXPECT_ARTIST_IN_FILENAME",
                "false",
            ).lower() == "true"
        self.expect_artist_in_filename = bool(expect_artist_in_filename)

    def _collect_name_tag_issues(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        metadata = record.get("metadata", {}) if isinstance(
            record.get("metadata"), dict) else {}
        organized_path = str(record.get("organized_path", "")).strip()
        if not organized_path:
            return []

        artist = _normalize(
            metadata.get("primary_artist") or metadata.get("artist") or "")
        file_name = Path(organized_path).name
        stem = Path(file_name).stem

        # Remove optional numeric track prefix from filename before matching.
        normalized_stem = _normalize(re.sub(r"^\s*\d{1,3}\s*-\s*", "", stem))

        issues: List[Dict[str, Any]] = []
        if self.expect_artist_in_filename and artist and artist not in normalized_stem:
            issues.append(
                {
                    "organized_path": organized_path,
                    "issue": "artist_not_in_filename",
                    "artist": artist,
                    "file_name": file_name,
                }
            )
        return issues

    def _load_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists() or not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _iter_media_records(self, payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        media = payload.get("media", {})
        if isinstance(media, dict):
            return [item for item in media.values() if isinstance(item, dict)]
        if isinstance(media, list):
            return [item for item in media if isinstance(item, dict)]
        return []

    def _is_music_record(self, record: Dict[str, Any]) -> bool:
        metadata = record.get("metadata", {})
        media_type = ""
        if isinstance(metadata, dict):
            media_type = str(metadata.get("media_type", "")).strip().lower()
        return media_type == "music"

    def _extract_genres(self, record: Dict[str, Any]) -> List[str]:
        metadata = record.get("metadata", {})
        if not isinstance(metadata, dict):
            return []

        raw: List[str] = []
        genres_value = metadata.get("genres")
        if isinstance(genres_value, list):
            for item in genres_value:
                raw.extend(_split_genre_tokens(item))

        raw.extend(_split_genre_tokens(metadata.get("genre")))

        cleaned: List[str] = []
        for value in raw:
            text = str(value or "").strip()
            if text:
                cleaned.append(text)
        return list(dict.fromkeys(cleaned))

    def _quality_score(self, record: Dict[str, Any], genres: List[str]) -> int:
        metadata = record.get("metadata", {}) if isinstance(
            record.get("metadata"), dict) else {}
        score = 0
        score += 25 if str(metadata.get("title", "")).strip() else 0
        score += 25 if str(metadata.get("artist", "")).strip() else 0
        score += 25 if str(metadata.get("album", "")).strip() else 0
        score += 25 if genres else 0
        return score

    def _registry_music_count(self) -> int:
        payload = self._load_json(self.link_registry_path)
        return sum(1 for record in self._iter_media_records(payload) if self._is_music_record(record))

    def generate_report(self, top_n: int = 10) -> Dict[str, Any]:
        payload = self._load_json(self.organization_path)
        music_records = [record for record in self._iter_media_records(
            payload) if self._is_music_record(record)]

        total_tracks = len(music_records)
        tracks_with_genre = 0
        tracks_missing_genre = 0
        multi_genre_tracks = 0
        playlist_like_tokens = 0
        genre_equal_folder = 0

        genre_counter: Counter[str] = Counter()
        quality_scores: List[int] = []
        name_tag_issues: List[Dict[str, Any]] = []

        for record in music_records:
            genres = self._extract_genres(record)
            if genres:
                tracks_with_genre += 1
            else:
                tracks_missing_genre += 1

            if len(genres) > 1:
                multi_genre_tracks += 1

            for token in genres:
                genre_counter[token] += 1
                if detect_suspicious_reason(token) == "playlist_or_editorial_tag":
                    playlist_like_tokens += 1

            organized_path = str(record.get("organized_path", "")).strip()
            if organized_path and genres:
                folder_candidates = build_folder_candidates(
                    Path(organized_path))
                normalized_genres = {_normalize(value) for value in genres}
                if normalized_genres.intersection(folder_candidates):
                    genre_equal_folder += 1

            quality_scores.append(self._quality_score(record, genres))
            name_tag_issues.extend(self._collect_name_tag_issues(record))

        genre_completeness = (tracks_with_genre /
                              total_tracks * 100.0) if total_tracks else 0.0
        avg_quality = (sum(quality_scores) / len(quality_scores)
                       ) if quality_scores else 0.0

        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "source_files": {
                "organization": str(self.organization_path),
                "link_registry": str(self.link_registry_path),
            },
            "metrics": {
                "total_tracks": total_tracks,
                "tracks_with_genre": tracks_with_genre,
                "tracks_missing_genre": tracks_missing_genre,
                "genre_completeness": round(genre_completeness, 2),
                "multi_genre_tracks": multi_genre_tracks,
                "playlist_like_tokens": playlist_like_tokens,
                "genre_equal_folder": genre_equal_folder,
                "name_tag_issues_count": len(name_tag_issues),
                "avg_tag_quality_score": round(avg_quality, 2),
                "registry_music_records": self._registry_music_count(),
            },
            "top_genres": genre_counter.most_common(max(1, top_n)),
            "name_tag_issues_sample": name_tag_issues[:50],
        }

    def save_report(self, report: Dict[str, Any], output_path: Optional[Path] = None) -> Path:
        if output_path is None:
            stamp = datetime.now().strftime("%Y-%m-%d")
            output_path = self.data_dir / f"quality_report_{stamp}.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path

    def generate_genre_quality_report(self) -> Dict[str, Any]:
        """Generate detailed genre quality analysis report.

        This report provides:
        - Genre distribution analysis
        - Invalid genre detection
        - Whitelist coverage
        - Recommendations for improvement
        """
        from app.features.genre_guard.core import (
            load_genre_exceptions,
            load_musical_keywords,
            load_invalid_catalog,
            load_suspect_catalog,
            _looks_like_musical_genre,
        )

        payload = self._load_json(self.organization_path)
        music_records = [
            record for record in self._iter_media_records(payload)
            if self._is_music_record(record)
        ]

        # Collect all genres
        all_genres: List[str] = []
        genres_by_record: Dict[str, List[str]] = {}

        for record in music_records:
            organized_path = str(record.get("organized_path", ""))
            genres = self._extract_genres(record)
            all_genres.extend(genres)
            if organized_path and genres:
                genres_by_record[organized_path] = genres

        # Analyze genres
        unique_genres = list(set(all_genres))
        genre_counts = Counter(all_genres)

        # Categorize genres
        valid_genres = []
        invalid_genres = []
        suspicious_genres = []
        whitelisted_genres = []

        invalid_catalog = load_invalid_catalog()
        invalid_exact = {_normalize(v)
                         for v in invalid_catalog.get("exact", [])}
        suspect_catalog = load_suspect_catalog()
        suspect_items = set(suspect_catalog.get("items", {}).keys())

        for genre in unique_genres:
            normalized = _normalize(genre)
            is_whitelisted = normalized in load_genre_exceptions()
            is_invalid = normalized in invalid_exact
            is_suspect = normalized in suspect_items
            is_musical = _looks_like_musical_genre(genre)
            has_keyword = any(
                kw in normalized for kw in load_musical_keywords())

            if is_whitelisted:
                whitelisted_genres.append(genre)
                valid_genres.append(genre)
            elif is_invalid:
                invalid_genres.append(genre)
            elif is_suspect:
                suspicious_genres.append(genre)
            elif is_musical or has_keyword:
                valid_genres.append(genre)
            else:
                # Unknown - needs review
                suspicious_genres.append(genre)

        # Calculate statistics
        total_genre_occurrences = sum(genre_counts.values())
        valid_occurrences = sum(genre_counts[g] for g in valid_genres)
        invalid_occurrences = sum(genre_counts[g] for g in invalid_genres)

        # Top genres by occurrence
        top_genres = genre_counts.most_common(20)

        # Genres that might be false positives in invalid list
        potential_false_positives = []
        for genre in invalid_genres:
            normalized = _normalize(genre)
            if _looks_like_musical_genre(genre):
                potential_false_positives.append({
                    "genre": genre,
                    "occurrences": genre_counts[genre],
                    "is_musical": True,
                })

        # Sort by occurrences
        potential_false_positives.sort(
            key=lambda x: x["occurrences"], reverse=True)

        # Genre completeness by artist
        artist_genres: Dict[str, Dict[str, int]] = {}
        for record in music_records:
            metadata = record.get("metadata", {})
            if not isinstance(metadata, dict):
                continue

            artist = str(metadata.get("primary_artist", "")
                         or metadata.get("artist", "Unknown")).strip()
            if not artist:
                continue

            if artist not in artist_genres:
                artist_genres[artist] = {"with_genre": 0, "missing_genre": 0}

            genres = self._extract_genres(record)
            if genres:
                artist_genres[artist]["with_genre"] += 1
            else:
                artist_genres[artist]["missing_genre"] += 1

        # Artists with lowest genre completeness
        artist_completeness = []
        for artist, counts in artist_genres.items():
            total = counts["with_genre"] + counts["missing_genre"]
            try:
                min_tracks_threshold = max(
                    1, int(os.getenv("QUALITY_MONITOR_MIN_TRACKS_THRESHOLD", "3")))
            except ValueError:
                min_tracks_threshold = 3
            if total >= min_tracks_threshold:
                completeness = (counts["with_genre"] /
                                total * 100) if total > 0 else 0
                artist_completeness.append({
                    "artist": artist,
                    "total_tracks": total,
                    "genre_completeness": round(completeness, 1),
                    "missing_count": counts["missing_genre"],
                })

        artist_completeness.sort(key=lambda x: x["genre_completeness"])

        # Build report
        report = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "summary": {
                "total_tracks_analyzed": len(music_records),
                "unique_genres_found": len(unique_genres),
                "total_genre_occurrences": total_genre_occurrences,
                "valid_genres_count": len(valid_genres),
                "invalid_genres_count": len(invalid_genres),
                "suspicious_genres_count": len(suspicious_genres),
                "whitelisted_genres_count": len(whitelisted_genres),
            },
            "coverage": {
                "valid_occurrences": valid_occurrences,
                "invalid_occurrences": invalid_occurrences,
                "valid_percentage": round((valid_occurrences / total_genre_occurrences * 100) if total_genre_occurrences else 0, 2),
                "invalid_percentage": round((invalid_occurrences / total_genre_occurrences * 100) if total_genre_occurrences else 0, 2),
            },
            "top_genres": top_genres,
            "potential_false_positives": potential_false_positives[:20],
            "artists_lowest_completeness": artist_completeness[:20],
            "catalog_status": {
                "invalid_catalog_size": len(invalid_catalog.get("exact", [])),
                "suspect_catalog_size": len(suspect_catalog.get("items", {})),
                "genre_exceptions_size": len(load_genre_exceptions()),
                "musical_keywords_size": len(load_musical_keywords()),
            },
            "recommendations": [],
        }

        # Generate recommendations
        recommendations = []

        if potential_false_positives:
            recommendations.append({
                "priority": "HIGH",
                "issue": f"{len(potential_false_positives)} valid genres may be present in the invalid list",
                "action": "Execute: python scripts/audit_removed_genres.py --review-queue",
            })

        if len(suspicious_genres) > len(unique_genres) * 0.1:
            recommendations.append({
                "priority": "MEDIUM",
                "issue": f"{len(suspicious_genres)} suspicious genres detected (>10%)",
                "action": "Review genres in data/suspect_music_genres.json",
            })

        if artist_completeness and artist_completeness[0]["genre_completeness"] < 50:
            recommendations.append({
                "priority": "LOW",
                "issue": f"Artist '{artist_completeness[0]['artist']}' has only {artist_completeness[0]['genre_completeness']}% genre completeness",
                "action": "Consider metadata enrichment via MusicBrainz/Last.fm",
            })

        report["recommendations"] = recommendations

        return report

    def save_genre_quality_report(self, report: Optional[Dict[str, Any]] = None, output_path: Optional[Path] = None) -> Path:
        """Save genre quality report to file."""
        if report is None:
            report = self.generate_genre_quality_report()

        if output_path is None:
            stamp = datetime.now().strftime("%Y-%m-%d")
            output_path = self.data_dir / f"genre_quality_report_{stamp}.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger = logging.getLogger(__name__)
        logger.info(f"Genre quality report saved to: {output_path}")
        return output_path
