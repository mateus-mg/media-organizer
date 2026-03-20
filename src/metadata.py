"""
Metadata module for Media Organization System

Consolidated module containing:
- Audio metadata extraction (ID3 tags)
- Online metadata fetchers (OpenLibrary, MusicBrainz)
- Metadata parsers for various file types

Usage:
    from src.metadata import (
        extract_audio_metadata,
        enrich_book_metadata_with_online_sources,
        enrich_music_metadata_with_online_sources,
        MetadataParser
    )
"""
import asyncio
import aiohttp
import logging
import re
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from difflib import SequenceMatcher

from src.value_utils import is_missing_value


# ============================================================================
# SECTION 1: AUDIO METADATA
# ============================================================================

def extract_audio_metadata(file_path: Path, logger=None) -> Dict:
    """
    Extract Navidrome-compatible audio metadata from file tags.

    Supports MP3 (ID3v2), FLAC, OGG, Opus, M4A, and WMA.
    Extracts all critical tags for proper Navidrome organization:
    - Title, Artist, Album, Album Artist (CRITICAL for Navidrome)
    - Track/Disc numbers in proper format
    - Multiple artists and genres
    - Genre, Year, Compilation flag, ISRC, MusicBrainz IDs
    - Original/Release dates

    Args:
        file_path: Path to audio file
        logger: Logger instance

    Returns:
        Dictionary with extracted metadata (all values lowercase keys)
    """
    logger = logger or logging.getLogger(__name__)
    metadata = {}

    try:
        ext = file_path.suffix.lower()

        if ext == '.mp3':
            from mutagen.id3 import ID3
            from mutagen.mp3 import MP3

            audio = MP3(file_path)
            if audio.tags:
                def get_id3_value(frame_id: str, index=0) -> str:
                    val = audio.tags.get(frame_id)
                    if val:
                        if isinstance(val, list):
                            return str(val[index] if index < len(val) else '')
                        return str(val)
                    return ''

                def get_id3_list(frame_id: str) -> List[str]:
                    val = audio.tags.get(frame_id)
                    if val:
                        if isinstance(val, list):
                            return [str(v).strip() for v in val if str(v).strip()]
                        return [str(val).strip()]
                    return []

                metadata['title'] = get_id3_value('TIT2')
                metadata['artist'] = get_id3_value('TPE1')
                metadata['artists'] = get_id3_list('TPE1')
                metadata['album'] = get_id3_value('TALB')
                metadata['album_artist'] = get_id3_value('TPE2')
                metadata['genre'] = get_id3_value('TCON')
                metadata['genres'] = get_id3_list('TCON')
                metadata['track_number'] = get_id3_value('TRCK')
                metadata['disc_number'] = get_id3_value('TPOS')
                metadata['year'] = get_id3_value('TDRC')
                metadata['date'] = get_id3_value('TDRC')
                metadata['isrc'] = get_id3_value('TSRC')

                metadata['compilation'] = '1' if get_id3_value(
                    'TCMP') else None

                mb_track_id = audio.tags.get('TXXX:MusicBrainz Track Id')
                if mb_track_id:
                    metadata['musicbrainz_trackid'] = str(
                        mb_track_id.text[0] if hasattr(mb_track_id, 'text') else mb_track_id)

        elif ext in {'.flac', '.ogg', '.opus'}:
            from mutagen.flac import FLAC

            audio = FLAC(file_path)

            def get_vorbis_value(key: str, index=0) -> str:
                val = audio.get(key, [])
                if val and index < len(val):
                    return str(val[index]).strip()
                return ''

            def get_vorbis_list(key: str) -> List[str]:
                val = audio.get(key, [])
                return [str(v).strip() for v in val if str(v).strip()]

            metadata['title'] = get_vorbis_value('title')
            metadata['artist'] = get_vorbis_value('artist')
            metadata['artists'] = get_vorbis_list('artist')
            metadata['album'] = get_vorbis_value('album')
            metadata['album_artist'] = get_vorbis_value('albumartist')
            metadata['genre'] = get_vorbis_value('genre')
            metadata['genres'] = get_vorbis_list('genre')
            metadata['track_number'] = get_vorbis_value('tracknumber')
            metadata['disc_number'] = get_vorbis_value('discnumber')
            metadata['year'] = get_vorbis_value('date')
            metadata['date'] = get_vorbis_value('date')
            metadata['isrc'] = get_vorbis_value('isrc')
            metadata['compilation'] = get_vorbis_value('compilation')
            metadata['musicbrainz_trackid'] = get_vorbis_value(
                'musicbrainz_trackid')
            metadata['originaldate'] = get_vorbis_value('originaldate')
            metadata['releasedate'] = get_vorbis_value('releasedate')

        elif ext == '.m4a':
            from mutagen.mp4 import MP4

            audio = MP4(file_path)

            def get_mp4_value(atom: str, index=0) -> str:
                val = audio.tags.get(atom, [])
                if val and index < len(val):
                    return str(val[index]).strip()
                return ''

            def get_mp4_list(atom: str) -> List[str]:
                val = audio.tags.get(atom, [])
                return [str(v).strip() for v in val if str(v).strip()]

            metadata['title'] = get_mp4_value('\xa9nam')
            metadata['artist'] = get_mp4_value('\xa9ART')
            metadata['artists'] = get_mp4_list('\xa9ART')
            metadata['album'] = get_mp4_value('\xa9alb')
            metadata['album_artist'] = get_mp4_value('aART')
            metadata['genre'] = get_mp4_value('\xa9gen')
            metadata['genres'] = get_mp4_list('\xa9gen')

            trkn = audio.tags.get('trkn', [(0, 0)])
            if trkn and trkn[0]:
                track, total = trkn[0]
                if total:
                    metadata['track_number'] = f"{track}/{total}"
                else:
                    metadata['track_number'] = str(track)

            disc = audio.tags.get('disk', [(0, 0)])
            if disc and disc[0]:
                disc_num, disc_total = disc[0]
                if disc_total:
                    metadata['disc_number'] = f"{disc_num}/{disc_total}"
                else:
                    metadata['disc_number'] = str(disc_num)

            metadata['year'] = get_mp4_value('\xa9day')
            metadata['isrc'] = get_mp4_value('ISRC')

        elif ext == '.wma':
            from mutagen.asf import ASF

            audio = ASF(file_path)

            def get_asf_value(key: str, index=0) -> str:
                val = audio.get(key, [])
                if val and index < len(val):
                    return str(val[index]).strip()
                return ''

            def get_asf_list(key: str) -> List[str]:
                val = audio.get(key, [])
                return [str(v).strip() for v in val if str(v).strip()]

            metadata['title'] = get_asf_value('Title')
            metadata['artist'] = get_asf_value('Author')
            metadata['artists'] = get_asf_list('Author')
            metadata['album'] = get_asf_value('WM/AlbumTitle')
            metadata['album_artist'] = get_asf_value('WM/AlbumArtist')
            metadata['genre'] = get_asf_value('WM/Genre')
            metadata['genres'] = get_asf_list('WM/Genre')
            metadata['track_number'] = get_asf_value('WM/TrackNumber')
            metadata['disc_number'] = get_asf_value('WM/SetPartNumber')
            metadata['year'] = get_asf_value('WM/Year')
            metadata['isrc'] = get_asf_value('WM/ISRC')

        return metadata
    except Exception as e:
        logger.error(f"Error extracting audio metadata from {file_path}: {e}")
        return {}


# ============================================================================
# SECTION 2: ONLINE METADATA ENRICHMENT
# ============================================================================

@dataclass
class MetadataResult:
    """Result of metadata fetch operation"""
    success: bool
    metadata: Dict[str, Any]
    source: str
    error: Optional[str] = None


async def enrich_book_metadata_with_online_sources(
    file_path: Path,
    existing_metadata: Dict,
    logger=None,
    use_google_books: bool = True,
    google_books_min_match_score: int = 80,
    google_books_api_key: str = "",
    include_cover_url: bool = False,
) -> Dict:
    """
    Enrich book metadata from OpenLibrary.

    Args:
        file_path: Path to book file
        existing_metadata: Existing metadata dict
        logger: Logger instance

    Returns:
        Updated metadata dict
    """
    logger = logger or logging.getLogger(__name__)

    def _is_missing(value: Any) -> bool:
        return is_missing_value(
            value,
            unknown_values={"unknown", "unknown author"},
            treat_empty_collections=True,
        )

    def _first_non_empty(values: List[Any]) -> Optional[str]:
        for value in values or []:
            text = str(value).strip()
            if text:
                return text
        return None

    def _normalize_language(value: str) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        # OpenLibrary may return values like "/languages/eng".
        if "/" in text:
            text = text.split("/")[-1].strip()
        return text or None

    def _is_portuguese_language(value: Any) -> bool:
        lang = _normalize_language(str(value or ""))
        if not lang:
            return False
        normalized = lang.strip().lower().replace("_", "-")
        return normalized in {"por", "pt", "pt-br", "pt-pt"}

    def _extract_doc_languages(doc: Dict[str, Any]) -> List[str]:
        raw_values = doc.get("language") or []
        languages: List[str] = []
        for raw in raw_values:
            normalized = _normalize_language(str(raw))
            if normalized:
                languages.append(normalized)
        return languages

    def _extract_year(value: Any) -> Optional[int]:
        if value is None:
            return None
        match = re.search(r"(\d{4})", str(value))
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def _set_if_missing(target: Dict[str, Any], key: str, value: Any) -> None:
        if _is_missing(target.get(key)) and not _is_missing(value):
            target[key] = value

    def _normalize_search_text(value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _author_surname(value: str) -> str:
        normalized = _normalize_search_text(value)
        parts = normalized.split()
        return parts[-1] if parts else ""

    def _strip_collection_suffix(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return text
        text = re.sub(
            r"\s*\((?:volume\s+unico|edicao\s+completa|colecao|box)[^)]*\)\s*$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\s*[-–—]\s*(?:edicao\s+completa|volume\s+unico|colecao.*)$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return text.strip()

    def _clean_book_title_for_query(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        # Remove series/volume suffixes commonly present in filenames.
        text = re.sub(r"\s*\[[^\]]+\]\s*$", "", text).strip()
        text = re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", text).strip()
        text = _strip_collection_suffix(text)
        text = re.sub(r"\s+", " ", text).strip(" -_\t")
        return text

    def _pick_primary_author(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        # Keep only first author for inauthor queries.
        parts = [p.strip() for p in re.split(
            r",|;|&|\band\b|\be\b", text, flags=re.IGNORECASE)]
        for part in parts:
            if part:
                return part
        return text

    def _score_google_candidate(
        candidate: Dict[str, Any],
        target_title: str,
        target_author: str,
    ) -> float:
        volume_info = candidate.get("volumeInfo") or {}
        candidate_title = _normalize_search_text(
            volume_info.get("title") or "")
        title_ratio = SequenceMatcher(
            None,
            _normalize_search_text(target_title),
            candidate_title,
        ).ratio()

        candidate_authors = volume_info.get("authors") or []
        candidate_authors_norm = [
            _normalize_search_text(v) for v in candidate_authors]
        surname = _author_surname(target_author)
        author_hit = 0.0
        if candidate_authors_norm:
            if any(surname and surname in auth for auth in candidate_authors_norm):
                author_hit = 1.0
            elif any(
                _normalize_search_text(target_author) in auth
                or auth in _normalize_search_text(target_author)
                for auth in candidate_authors_norm
            ):
                author_hit = 0.8

        return (title_ratio * 70.0) + (author_hit * 30.0)

    def _extract_google_year(volume_info: Dict[str, Any]) -> Optional[int]:
        raw = volume_info.get("publishedDate")
        if _is_missing(raw):
            return None
        match = re.search(r"(\d{4})", str(raw))
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _extract_google_isbn(volume_info: Dict[str, Any]) -> Optional[str]:
        identifiers = volume_info.get("industryIdentifiers") or []
        if not isinstance(identifiers, list):
            return None

        by_type: Dict[str, str] = {}
        for item in identifiers:
            if not isinstance(item, dict):
                continue
            id_type = str(item.get("type") or "").strip().upper()
            identifier = str(item.get("identifier") or "").strip()
            if id_type and identifier:
                by_type[id_type] = identifier

        return (
            by_type.get("ISBN_13")
            or by_type.get("ISBN_10")
            or next(iter(by_type.values()), None)
        )

    def _extract_google_rating(volume_info: Dict[str, Any]) -> Optional[float]:
        raw = volume_info.get("averageRating")
        if _is_missing(raw):
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _extract_google_page_count(volume_info: Dict[str, Any]) -> Optional[int]:
        raw = volume_info.get("pageCount")
        if _is_missing(raw):
            return None
        try:
            pages = int(raw)
            return pages if pages > 0 else None
        except (TypeError, ValueError):
            return None

    def _normalize_cover_url(url: str) -> Optional[str]:
        text = str(url or "").strip()
        if not text:
            return None
        if text.startswith("http://"):
            return "https://" + text[len("http://"):]
        return text

    def _needs_openlibrary_fallback(metadata: Dict[str, Any]) -> bool:
        fallback_fields = (
            "author",
            "authors",
            "year",
            "language",
            "publisher",
            "description",
            "isbn",
            "series",
            "genre",
        )
        return any(_is_missing(metadata.get(field)) for field in fallback_fields)

    try:
        title = str(existing_metadata.get("title") or "").strip()
        author = str(existing_metadata.get("author") or "").strip()

        if not title:
            return existing_metadata

        async with aiohttp.ClientSession() as session:
            if use_google_books:
                cleaned_title = _clean_book_title_for_query(title)
                base_title = _strip_collection_suffix(cleaned_title)
                author_for_query = _pick_primary_author(author)

                title_variants = [v for v in [
                    title, cleaned_title, base_title] if str(v).strip()]
                title_variants = list(dict.fromkeys(title_variants))

                query_variants: List[str] = []
                for title_variant in title_variants:
                    title_variant = str(title_variant).strip()
                    if not title_variant:
                        continue
                    if author_for_query:
                        query_variants.extend(
                            [
                                f"intitle:{title_variant} inauthor:{author_for_query}",
                                f'{title_variant} {author_for_query}',
                            ]
                        )
                    query_variants.extend(
                        [f"intitle:{title_variant}", title_variant])

                # Preserve order and remove duplicates.
                query_variants = list(dict.fromkeys(q.strip()
                                      for q in query_variants if q.strip()))

                best_candidate: Optional[Dict[str, Any]] = None
                best_score = -1.0
                google_requests_count = 0
                google_items_count = 0
                google_api_error: Optional[str] = None
                google_api_status: Optional[int] = None
                quota_exhausted = False

                for query in query_variants:
                    if quota_exhausted:
                        break

                    # Prefer Portuguese, then fallback to any language.
                    for lang in ("pt", None):
                        params = {
                            "q": query,
                            "printType": "books",
                            "maxResults": "15",
                            "orderBy": "relevance",
                        }
                        if lang:
                            params["langRestrict"] = lang
                        if google_books_api_key:
                            params["key"] = google_books_api_key

                        google_url = (
                            "https://www.googleapis.com/books/v1/volumes?"
                            + urllib.parse.urlencode(params)
                        )
                        google_requests_count += 1

                        async with session.get(google_url) as google_response:
                            google_api_status = google_response.status

                            try:
                                payload = await google_response.json(content_type=None)
                            except Exception:
                                payload = {}

                            if google_response.status != 200:
                                error_obj = payload.get("error") if isinstance(
                                    payload, dict) else None
                                google_api_error = (
                                    (error_obj or {}).get("message")
                                    or f"HTTP {google_response.status}"
                                )
                                reason_blob = str(error_obj or "").lower()
                                if (
                                    google_response.status in {429, 403}
                                    or "ratelimitexceeded" in reason_blob
                                    or "dailylimitexceeded" in reason_blob
                                    or "quota" in str(google_api_error).lower()
                                ):
                                    quota_exhausted = True
                                continue

                            if isinstance(payload, dict) and payload.get("error"):
                                error_obj = payload.get("error") or {}
                                google_api_error = str(error_obj.get(
                                    "message") or "google_books_error")
                                reason_blob = str(error_obj).lower()
                                if (
                                    "ratelimitexceeded" in reason_blob
                                    or "dailylimitexceeded" in reason_blob
                                    or "quota" in google_api_error.lower()
                                ):
                                    quota_exhausted = True
                                continue

                            items = payload.get("items") or [] if isinstance(
                                payload, dict) else []
                            if not items:
                                continue

                            google_items_count += len(items)
                            for item in items:
                                score = _score_google_candidate(
                                    item, cleaned_title or title, author_for_query or author)
                                if score > best_score:
                                    best_score = score
                                    best_candidate = item

                    if best_score >= 99.0:
                        break

                if best_candidate and best_score >= float(google_books_min_match_score):
                    volume_info = best_candidate.get("volumeInfo") or {}
                    categories = [
                        str(item).strip()
                        for item in (volume_info.get("categories") or [])
                        if str(item).strip()
                    ]
                    google_authors = [
                        str(item).strip()
                        for item in (volume_info.get("authors") or [])
                        if str(item).strip()
                    ]

                    _set_if_missing(existing_metadata, "title",
                                    volume_info.get("title"))
                    _set_if_missing(existing_metadata, "subtitle",
                                    volume_info.get("subtitle"))
                    if google_authors:
                        _set_if_missing(existing_metadata,
                                        "author", google_authors[0])
                        _set_if_missing(existing_metadata,
                                        "authors", google_authors)

                    _set_if_missing(existing_metadata, "year",
                                    _extract_google_year(volume_info))
                    _set_if_missing(existing_metadata, "language",
                                    volume_info.get("language"))
                    _set_if_missing(existing_metadata, "publisher",
                                    volume_info.get("publisher"))
                    _set_if_missing(existing_metadata, "description",
                                    volume_info.get("description"))
                    _set_if_missing(existing_metadata, "isbn",
                                    _extract_google_isbn(volume_info))
                    _set_if_missing(existing_metadata, "rating",
                                    _extract_google_rating(volume_info))
                    _set_if_missing(existing_metadata, "page_count",
                                    _extract_google_page_count(volume_info))
                    _set_if_missing(existing_metadata, "subjects", categories)
                    if categories:
                        _set_if_missing(existing_metadata,
                                        "genre", categories[0])

                    _set_if_missing(existing_metadata,
                                    "google_books_id", best_candidate.get("id"))
                    _set_if_missing(
                        existing_metadata, "google_books_info_link", volume_info.get("infoLink"))
                    _set_if_missing(
                        existing_metadata, "google_books_preview_link", volume_info.get("previewLink"))

                    if include_cover_url:
                        image_links = volume_info.get("imageLinks") or {}
                        cover_url = _normalize_cover_url(
                            image_links.get("thumbnail")
                            or image_links.get("smallThumbnail")
                            or image_links.get("small")
                        )
                        _set_if_missing(existing_metadata,
                                        "cover_image_url", cover_url)

                    logger.info(
                        "Enriched from Google Books: %s (score=%.2f)",
                        file_path.name,
                        best_score,
                    )
                elif google_api_error:
                    if quota_exhausted:
                        logger.warning(
                            "Google Books quota/rate limit reached for %s (status=%s). "
                            "Configure GOOGLE_BOOKS_API_KEY to use your own quota. Last error: %s",
                            file_path.name,
                            google_api_status,
                            google_api_error,
                        )
                    else:
                        logger.warning(
                            "Google Books request failed for %s (status=%s): %s",
                            file_path.name,
                            google_api_status,
                            google_api_error,
                        )
                elif use_google_books:
                    logger.info(
                        "No reliable Google Books match for %s (best_score=%.2f, requests=%s, items=%s)",
                        file_path.name,
                        best_score,
                        google_requests_count,
                        google_items_count,
                    )

            # OpenLibrary acts as fallback after Google Books, filling only remaining gaps.
            if _needs_openlibrary_fallback(existing_metadata):
                title_for_openlibrary = str(
                    existing_metadata.get("title") or title).strip()
                author_for_openlibrary = str(
                    existing_metadata.get("author") or author).strip()

                encoded_title = urllib.parse.quote_plus(title_for_openlibrary)
                encoded_author = urllib.parse.quote_plus(author_for_openlibrary)
                openlibrary_url = (
                    "https://openlibrary.org/search.json"
                    f"?title={encoded_title}&author={encoded_author}&limit=25"
                )

                async with session.get(openlibrary_url) as response:
                    if response.status != 200:
                        logger.warning(
                            "OpenLibrary search failed for %s (status=%s)",
                            file_path.name,
                            response.status,
                        )
                    else:
                        data = await response.json()
                        docs = data.get("docs") or []
                        if docs:
                            portuguese_docs = []
                            for doc_candidate in docs:
                                languages = _extract_doc_languages(doc_candidate)
                                if any(_is_portuguese_language(lang) for lang in languages):
                                    portuguese_docs.append(doc_candidate)

                            if not portuguese_docs:
                                logger.info(
                                    "No Portuguese online metadata found for %s",
                                    file_path.name,
                                )
                            else:
                                doc = portuguese_docs[0]

                                isbn = _first_non_empty(doc.get("isbn") or [])
                                publisher = _first_non_empty(
                                    doc.get("publisher") or [])
                                language_candidates = _extract_doc_languages(doc)
                                language = _first_non_empty(
                                    [lang for lang in language_candidates if _is_portuguese_language(
                                        lang)]
                                )
                                year = _extract_year(
                                    doc.get("first_publish_year"))
                                series = _first_non_empty(doc.get("series") or [])

                                _set_if_missing(existing_metadata, "isbn", isbn)
                                _set_if_missing(existing_metadata,
                                                "publisher", publisher)
                                _set_if_missing(existing_metadata,
                                                "language", language)
                                _set_if_missing(existing_metadata, "year", year)
                                _set_if_missing(existing_metadata,
                                                "series", series)

                                logger.info(
                                    "Enriched from OpenLibrary: %s", file_path.name)

    except Exception as exc:
        logger.warning("Book enrichment failed for %s: %s",
                       file_path.name, exc)

    return existing_metadata


async def enrich_music_metadata_with_online_sources(
    file_path: Path,
    existing_metadata: Dict,
    logger=None,
    lastfm_api_key: str = "",
    min_confidence: int = 85,
    api_delay_seconds: float = 1.0,
    fetch_lastfm: bool = True,
    request_timeout_seconds: float = 12.0,
) -> Dict:
    """
    Enrich music metadata from MusicBrainz and Last.fm.

    This function only returns enrichment candidates. Callers should decide
    whether to apply values, ideally only for missing fields.

    Args:
        file_path: Path to music file
        existing_metadata: Existing metadata dict
        logger: Logger instance

    Returns:
        Updated metadata dict
    """
    logger = logger or logging.getLogger(__name__)

    try:
        artist = (existing_metadata.get('artist') or '').strip()
        title = (
            existing_metadata.get('title')
            or existing_metadata.get('track_name')
            or ''
        ).strip()

        if not artist or not title:
            return existing_metadata

        headers = {
            # MusicBrainz asks for a descriptive User-Agent.
            "User-Agent": "media-organizer/1.0 (local; metadata-enrichment)",
        }

        timeout = aiohttp.ClientTimeout(
            total=request_timeout_seconds,
            connect=min(5.0, request_timeout_seconds),
            sock_connect=min(5.0, request_timeout_seconds),
            sock_read=request_timeout_seconds,
        )

        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            # MusicBrainz search with artist + recording filters for safer matches.
            mb_query = f'artist:"{artist}" AND recording:"{title}"'
            encoded_query = urllib.parse.quote_plus(mb_query)
            mb_url = (
                "https://musicbrainz.org/ws/2/recording/"
                f"?query={encoded_query}&fmt=json&limit=5"
            )

            logger.info("Metadata lookup (MusicBrainz) for: %s",
                        file_path.name)

            async with session.get(mb_url) as response:
                if response.status == 200:
                    data = await response.json()
                    recordings = data.get('recordings') or []
                    if recordings:
                        top = recordings[0]
                        score = int(top.get('score', 0))

                        if score >= min_confidence:
                            existing_metadata['musicbrainz_trackid'] = top.get(
                                'id')

                            mb_title = top.get('title')
                            if mb_title:
                                existing_metadata['title'] = mb_title

                            artist_credits = top.get('artist-credit') or []
                            if artist_credits:
                                ac = artist_credits[0]
                                mb_artist = (
                                    (ac.get('artist') or {}).get('name')
                                    or ac.get('name')
                                )
                                if mb_artist:
                                    existing_metadata['artist'] = mb_artist

                            releases = top.get('releases') or []
                            if releases:
                                first_release = releases[0]
                                mb_album = first_release.get('title')
                                if mb_album:
                                    existing_metadata['album'] = mb_album
                                mb_date = first_release.get('date', '')
                                if mb_date and len(mb_date) >= 4:
                                    year_str = mb_date[:4]
                                    if year_str.isdigit():
                                        existing_metadata['year'] = int(
                                            year_str)

                            isrcs = top.get('isrcs') or []
                            if isrcs:
                                existing_metadata['isrc'] = isrcs[0]

                            tags = top.get('tags') or []
                            if tags and tags[0].get('name'):
                                existing_metadata['genre'] = tags[0]['name'].title(
                                )

                            logger.info(
                                "Enriched from MusicBrainz: %s (score=%s)",
                                file_path.name,
                                score,
                            )
                        else:
                            logger.info(
                                "Skipped low-confidence MusicBrainz match: %s (score=%s)",
                                file_path.name,
                                score,
                            )
                else:
                    logger.warning(
                        "MusicBrainz request failed for %s (status=%s)",
                        file_path.name,
                        response.status,
                    )

            # Respect API rate limits between external calls.
            await asyncio.sleep(max(api_delay_seconds, 0.0))

            if lastfm_api_key and fetch_lastfm:
                logger.info("Metadata lookup (Last.fm) for: %s",
                            file_path.name)

                lf_params = urllib.parse.urlencode(
                    {
                        'method': 'track.getInfo',
                        'api_key': lastfm_api_key,
                        'artist': artist,
                        'track': title,
                        'format': 'json',
                    }
                )
                lf_url = f"https://ws.audioscrobbler.com/2.0/?{lf_params}"

                async with session.get(lf_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        track_data = data.get('track') or {}
                        tag_data = ((track_data.get('toptags')
                                    or {}).get('tag') or [])

                        if tag_data and isinstance(tag_data, list):
                            first_tag = tag_data[0]
                            name = first_tag.get('name') if isinstance(
                                first_tag, dict) else None
                            if name:
                                existing_metadata['genre'] = str(name).title()

                        # Last.fm as fallback for title / artist / album.
                        if 'title' not in existing_metadata:
                            lf_title = track_data.get('name')
                            if lf_title:
                                existing_metadata['title'] = lf_title
                        if 'artist' not in existing_metadata:
                            lf_artist = (track_data.get(
                                'artist') or {}).get('name')
                            if lf_artist:
                                existing_metadata['artist'] = lf_artist
                        if 'album' not in existing_metadata:
                            lf_album = (track_data.get('album')
                                        or {}).get('title')
                            if lf_album:
                                existing_metadata['album'] = lf_album
                    else:
                        logger.warning(
                            "Last.fm request failed for %s (status=%s)",
                            file_path.name,
                            response.status,
                        )

                await asyncio.sleep(max(api_delay_seconds, 0.0))
    except asyncio.TimeoutError:
        logger.warning(
            "Metadata lookup timeout for %s after %.1fs",
            file_path.name,
            request_timeout_seconds,
        )
    except Exception as e:
        logger.warning(f"MusicBrainz enrichment failed: {e}")

    return existing_metadata


async def enrich_comic_metadata_with_online_sources(
    file_path: Path,
    existing_metadata: Dict,
    logger=None
) -> Dict:
    """
    Enrich comic metadata from ComicVine

    Args:
        file_path: Path to comic file
        existing_metadata: Existing metadata dict
        logger: Logger instance

    Returns:
        Updated metadata dict
    """
    logger = logger or logging.getLogger(__name__)

    # ComicVine requires API key, so this is a placeholder
    # Implementation would depend on having a valid API key

    return existing_metadata


# ============================================================================
# SECTION 3: METADATA PARSERS
# ============================================================================

class MetadataParser:
    """
    Generic metadata parser for various file types.

    Provides unified interface for extracting metadata from:
    - Audio files (ID3 tags)
    - Books (filename patterns)
    - Comics (filename patterns)
    """

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def parse(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse metadata from file

        Args:
            file_path: Path to file

        Returns:
            Dictionary with extracted metadata
        """
        ext = file_path.suffix.lower()

        if ext in {'.mp3', '.flac', '.m4a', '.ogg'}:
            return extract_audio_metadata(file_path, self.logger)

        # Add more parsers as needed
        return {}

    def parse_book_filename(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse book filename for metadata

        Args:
            file_path: Path to book file

        Returns:
            Dictionary with extracted metadata
        """
        import re

        filename = file_path.stem
        metadata = {}

        # Try pattern: "Author - Title (Year)"
        match = re.match(r'^(.+?)\s*-\s*(.+?)\s*\((\d{4})\)', filename)
        if match:
            raw_author = match.group(1).strip()
            authors = [a.strip() for a in raw_author.split(',') if a.strip()]
            metadata['authors'] = authors
            metadata['author'] = authors[0] if authors else raw_author
            metadata['title'] = match.group(2).strip()
            metadata['year'] = int(match.group(3))
        else:
            # Just extract year if present
            year_match = re.search(r'\((\d{4})\)', filename)
            if year_match:
                metadata['year'] = int(year_match.group(1))

        return metadata
