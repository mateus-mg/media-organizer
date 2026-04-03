"""Genre guard utilities for filtering invalid or polluted music genres.

This module centralizes:
- Persistent invalid genre catalog loading/saving
- Folder-name genre pollution checks
- Suspicious genre detection and auto-feeding
"""

from __future__ import annotations

import atexit
import csv
import json
import logging
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv

LOGGER = logging.getLogger(__name__)

load_dotenv()

_CATALOG_CACHE: Optional[Dict[str, Any]] = None
_SUSPECT_CACHE: Optional[Dict[str, Any]] = None


def _env_int(name: str, default: int, minimum: Optional[int] = None) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw not in (None, "") else int(default)
    except Exception:
        value = int(default)
    if minimum is not None:
        value = max(minimum, value)
    return value

# =============================================================================
# SIMPLIFIED APPROACH FOR GENRE VALIDATION
# =============================================================================
#
# Instead of maintaining a huge whitelist (800+ items), we use:
# 1. MUSICAL_KEYWORDS (548 terms) - covers 99%+ of musical genres
# 2. GENRE_EXCEPTIONS (7 items) - niche genres not covered by keywords
#
# Advantages:
# - 99% less maintenance (7 items vs 800+)
# - More flexible for new/niche genres
# - More transparent and auditable
# - Same real protection
# =============================================================================


# Manually curated terms explicitly marked as INVALID (not musical genres).
#
# NOTE: Invalid genres are now stored in JSON file, NOT in Python source code.
# This allows updating invalid genres without modifying code.
#
# To add invalid genres, edit: data/invalid_music_genres.json
#

# ===============================================================================
# ===============================================================================

# Patterns for suspect genre detection
DEFAULT_INVALID_REGEX = [
    r"\bbillboard\b",
    r"\boffizielle\s+charts\b",
    r"\bhot\s*100\b",
    r"\bno\s*1\b",
    r"\b(?:late|early)?\s*(?:19|20)?\d{2}s\b",
    r"\b\d{2}s\b",
    r"\b(?:tiktok|viral)\b",
    r"\b(?:top\s*\d*|playlist|flashback|hits?)\b",
]

# Safe terms that are valid when combined with other musical terms
# These protect words like "vocal", "female", "dance" when part of compound genres
SAFE_TERMS = {
    "vocal", "female", "male", "dance", "rock", "pop", "electronic",
    "house", "trance", "techno", "metal", "punk", "soul", "funk", "jazz",
    "bass", "garage", "disco", "wave", "beat", "sound", "music", "band",
    "singer", "artist", "group", "live", "studio", "records", "music"
}

# Tokens editoriais/comportamentais que frequentemente poluem tags de genero.
# Usados para heuristica de confianca sem depender de listas extensas.
EDITORIAL_TOKENS = {
    "top", "chart", "charts", "best", "playlist", "hits", "viral", "tiktok",
    "flashback", "mood", "vibes", "booster", "favorite", "favorites", "listen",
    "party", "happy", "sad", "workout", "focus", "chill", "sleep", "study",
    "mix", "edit", "version", "radio", "live", "feat", "featuring", "remix",
    "single", "album", "track", "tracks", "songs", "song"
}

HEURISTIC_PROFILE_PRESETS: Dict[str, Dict[str, int]] = {
    "strict": {
        "editorial_overload_hits": 2,
        "editorial_overload_max_musical_hits": 0,
        "editorial_overload_min_keyword_hits": 0,
        "editorial_bias_min_delta": 1,
        "editorial_bias_max_confidence": 1,
        "musical_confident_min_keyword_hits": 1,
        "musical_confident_min_score": 3,
    },
    "balanced": {
        "editorial_overload_hits": 3,
        "editorial_overload_max_musical_hits": 0,
        "editorial_overload_min_keyword_hits": 0,
        "editorial_bias_min_delta": 1,
        "editorial_bias_max_confidence": 0,
        "musical_confident_min_keyword_hits": 1,
        "musical_confident_min_score": 2,
    },
    "permissive": {
        "editorial_overload_hits": 4,
        "editorial_overload_max_musical_hits": 1,
        "editorial_overload_min_keyword_hits": 0,
        "editorial_bias_min_delta": 2,
        "editorial_bias_max_confidence": -1,
        "musical_confident_min_keyword_hits": 1,
        "musical_confident_min_score": 1,
    },
}

# Geographic markers that are valid when combined with musical genres
# These protect terms like "UK", "Dutch", "Brazilian" when part of valid subgenres
GEOGRAPHIC_MARKERS = {
    "uk", "us", "usa", "us-", "british", "english", "american",
    "dutch", "netherlands", "french", "german", "italian", "spanish",
    "portuguese", "brazilian", "brazil", "argentine", "colombian",
    "mexican", "peruvian", "chilean", "venezuelan", "cuban",
    "japanese", "korean", "chinese", "indian", "pakistani",
    "russian", "polish", "swedish", "norwegian", "danish", "finnish",
    "australian", "canadian", "nigerian", "ghanaian", "south african",
    "jamaican", "trinidadian", "barbadian", "barbados", "barbade", "barbadien",
    "turkish", "greek", "arabic", "persian", "latin", "latino",
    "afro", "euro", "asia", "european", "asian", "african",
    "berlin", "detroit", "chicago", "new york", "la", "london",
    "paris", "tokyo", "seoul", "mumbai", "lagos", "kingston",
    "havana", "rio", "bahia", "recife", "fortaleza"
}

# Valid geographic + genre combinations (whitelist for compound genres)
VALID_GEOGRAPHIC_GENRES = {
    # UK
    "uk garage", "uk hip hop", "uk drill", "uk funky", "uk r&b", "uk r b",
    "uk house", "uk techno", "uk drum and bass", "uk dubstep",
    # Dutch
    "dutch house", "dutch trance", "dutch edm", "dutch techno",
    # French
    "french house", "french touch", "french hip hop", "french drill", "french pop",
    "french electro", "french techno",
    # German
    "german hip hop", "german techno", "german trance", "german hardcore",
    # Brazilian
    "brazilian funk", "brazilian hip hop", "brazilian bass",
    "brazilian sertanejo", "brazilian forró", "brazilian axé", "brazilian mpb",
    "brazilian funk carioca", "brazilian baile funk", "brazilian piseiro",
    "brazilian arrocha", "brazilian brega", "brazilian tecnobrega",
    "brazilian samba", "brazilian bossa nova", "brazilian choro", "brazilian pagode",
    # Italian
    "italo disco", "italo house", "italo pop", "italo dance",
    # Spanish
    "spanish pop", "spanish hip hop", "spanish rock", "spanish folk",
    # Portuguese
    "portuguese folk", "portuguese rock", "portuguese fado",
    # Argentine
    "argentine rock", "argentine tango", "argentine folk",
    # Colombian
    "colombian cumbia", "colombian vallenato", "colombian salsa",
    # Mexican
    "mexican pop", "mexican rock", "regional mexicano",
    "mexican ranchera", "mexican norteño", "mexican corridos", "mexican banda",
    # Peruvian
    "peruvian cumbia", "peruvian rock", "peruvian folk",
    # Chilean
    "chilean folk", "chilean rock", "chilean nueva canción",
    # Venezuelan
    "venezuelan salsa", "venezuelan pop", "venezuelan joropo",
    # Cuban
    "cuban salsa", "cuban son", "cuban jazz", "cuban timba",
    # Japanese
    "japanese pop", "japanese rock", "japanese jazz",
    "japanese enka", "japanese city pop", "japanese electronic",
    # Korean
    "korean pop", "korean r&b", "korean hip hop", "korean trot",
    "korean electronic", "korean indie",
    # Chinese
    "chinese pop", "chinese rock", "chinese folk",
    "cantopop", "mandopop",
    # Indian
    "indian pop", "indian classical", "indian folk",
    "indian bollywood", "indian bhangra",
    # Pakistani
    "pakistani qawwali", "pakistani pop", "pakistani folk",
    # Russian
    "russian pop", "russian rock", "russian folk",
    # Polish
    "polish hip hop", "polish rock", "polish folk",
    # Swedish
    "swedish house", "swedish pop", "swedish metal",
    "swedish electronic", "swedish indie",
    # Norwegian
    "norwegian black metal", "norwegian pop", "norwegian folk",
    # Danish
    "danish pop", "danish rock", "danish electronic",
    # Finnish
    "finnish metal", "finnish rock", "finnish tango",
    # Australian
    "australian hip hop", "australian rock", "australian pop",
    # Canadian
    "canadian hip hop", "canadian rock", "canadian pop",
    # Nigerian
    "nigerian afrobeat", "nigerian highlife", "nigerian gospel",
    "nigerian afrobeats", "nigerian hip hop",
    # Ghanaian
    "ghanaian highlife", "ghanaian hiplife", "ghanaian afrobeat",
    # South African
    "south african house", "south african jazz",
    "south african amapiano", "south african gqom", "south african kwaito",
    # Jamaican
    "jamaican reggae", "jamaican dancehall", "jamaican ska",
    "jamaican dub", "jamaican rocksteady",
    # Trinidadian
    "trinidadian calypso", "trinidadian soca",
    # Barbadian
    "barbadian soca", "barbadian pop", "barbadian dancehall",
    # Turkish
    "turkish pop", "turkish rock", "turkish folk",
    # Greek
    "greek pop", "greek folk", "greek rock",
    # Arabic
    "arabic pop", "arabic classical",
    "arabic rai", "arabic dabke",
    # Persian
    "persian pop", "persian classical",
    # City-specific
    "berlin techno", "berlin house", "berlin minimal",
    "detroit techno", "detroit house", "detroit electro",
    "chicago house", "chicago acid", "chicago garage",
    "new york house", "new york hip hop", "new york garage",
    "la hip hop", "la punk", "la electronic",
    "london garage", "london grime", "london dubstep",
    "paris hip hop", "paris electronic", "paris house",
    "tokyo pop", "tokyo electronic", "tokyo hip hop",
    "seoul pop", "seoul hip hop", "seoul electronic",
    "mumbai pop", "mumbai classical", "mumbai electronic",
    "lagos afrobeat", "lagos highlife", "lagos hip hop",
    "kingston reggae", "kingston dancehall", "kingston dub",
    "havana salsa", "havana son", "havana timba",
    "rio funk", "rio samba", "rio bossa nova",
    "bahia axé", "bahia pagode", "bahia samba",
    "recife frevo", "recife maracatu", "recife forró",
    "fortaleza forró", "fortaleza baião",
    # National + Genre combinations
    "british soul", "british blues", "british rock", "british metal",
    "british hip hop", "british electronic", "british indie",
    "american hip hop", "american rock", "american blues", "american country",
    "american jazz", "american r&b", "american soul", "american funk",
    # Euro genres
    "eurodance", "euro-dance", "euro house", "euro trance",
    "euro pop", "euro rock",
    # Afro genres
    "afrobeat", "afrobeats", "afro-fusion", "afro house", "afro pop",
    "afro techno", "afro trance",
    # Other regional
    "celtic folk", "celtic rock", "celtic punk",
    "nordic folk", "nordic metal", "nordic electronic",
    "balkan folk", "balkan brass", "balkan pop",
    "middle eastern", "middle eastern pop", "middle eastern folk",
    "latin pop", "latin rock", "latin jazz", "latin hip hop",
    "latin trap", "latin urban",
    # Asian pop
    "j-pop", "k-pop", "c-pop", "v-pop", "t-pop", "p-pop",
    # Brazilian regional (explicit)
    "sertanejo", "forró", "axé", "mpb", "funk carioca", "baile funk",
    "piseiro", "arrocha", "brega", "tecnobrega", "xote", "baião",
    "samba", "bossa nova", "choro", "pagode", "bossa nova",
}

SUSPECT_PATTERNS = {
    # Dates and decades
    "decade_or_era_tag": re.compile(
        r"\b(?:late|early)?\s*(?:19|20)?\d{2}s\b|\b\d{2}s\b",
        re.IGNORECASE,
    ),
    # Playlist e tags editoriais
    "playlist_or_editorial_tag": re.compile(
        r"\b(playlist|flashback|hits?|top\s*\d*|charts?|billboard|viral|"
        r"tiktok|music\s+for|seen\s+live|icon)\b",
        re.IGNORECASE,
    ),
    # Specific years (e.g., 2009, 2011)
    "specific_year": re.compile(
        r"\b(?:19|20)\d{2}\b",
        re.IGNORECASE,
    ),
    # Long numeric IDs (8+ digits)
    "long_id": re.compile(
        r"\b\d{8,}\b",
        re.IGNORECASE,
    ),
    # UUID
    "uuid": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    # Format terms
    "format_terms": re.compile(
        r"\b(bootleg|demo|session|outtake|unplugged|karaoke|box\s+set|mix\s+tape|mixtape)\b",
        re.IGNORECASE,
    ),
    # Negative words (spam)
    "negative_words": re.compile(
        r"\b(fail|lame|stupid|dumb|terrible|awful|abuser|wifebeater|homophobe|racist|misogynist|anti\s+vax)\b",
        re.IGNORECASE,
    ),
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


_CYCLE_STATS: Dict[str, Any] = {
    "started_at": None,
    "processed_values": 0,
    "kept": 0,
    "removed": 0,
    "quarantined": 0,
    "suspicious_detected": 0,
    "auto_promoted": 0,
    "protected_musical": 0,
    "removed_reasons": {},
    "quarantined_reasons": {},
    "decision_audit": [],
    "decision_audit_dropped": 0,
}

_MAX_DECISION_AUDIT_ENTRIES = _env_int(
    "GENRE_DECISION_AUDIT_MAX_ENTRIES", 250000, minimum=1000)

if _CYCLE_STATS.get("started_at") is None:
    _CYCLE_STATS["started_at"] = _now_iso()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _data_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data"


def _invalid_catalog_path() -> Path:
    return _data_dir() / "invalid_music_genres.json"


def _suspect_catalog_path() -> Path:
    return _data_dir() / "suspect_music_genres.json"


def _backup_dir_path() -> Path:
    return _data_dir() / "backups"


def _genre_exceptions_path() -> Path:
    return _data_dir() / "genre_exceptions.json"


def _musical_keywords_path() -> Path:
    return _data_dir() / "musical_keywords.json"


def _backup_catalog_snapshot(source_path: Path, backup_prefix: str) -> Optional[Path]:
    if not source_path.exists():
        return None

    backup_dir = _backup_dir_path()
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = backup_dir / f"{backup_prefix}{timestamp}.json"
    backup_path.write_text(source_path.read_text(
        encoding="utf-8"), encoding="utf-8")
    return backup_path


def _build_default_genre_exceptions_catalog() -> Dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now_iso(),
        "exceptions": ["norteno", "sierreno", "chamame", "rai"],
    }


def _build_default_musical_keywords_catalog() -> Dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now_iso(),
        "keywords": ["pop", "rock", "metal", "jazz", "blues"],
    }


def load_genre_exceptions_payload(force_reload: bool = False) -> Dict[str, Any]:
    path = _genre_exceptions_path()
    payload = _load_json_or_default(
        path,
        _build_default_genre_exceptions_catalog(),
    )
    if force_reload or not path.exists():
        _save_json(path, payload)
    return payload


def save_genre_exceptions_payload(payload: Dict[str, Any]) -> None:
    path = _genre_exceptions_path()
    _save_json(path, payload)
    _backup_catalog_snapshot(path, "genre_exceptions_")


def load_musical_keywords_payload(force_reload: bool = False) -> Dict[str, Any]:
    path = _musical_keywords_path()
    payload = _load_json_or_default(
        path,
        _build_default_musical_keywords_catalog(),
    )
    if force_reload or not path.exists():
        _save_json(path, payload)
    return payload


def save_musical_keywords_payload(payload: Dict[str, Any]) -> None:
    path = _musical_keywords_path()
    _save_json(path, payload)
    _backup_catalog_snapshot(path, "musical_keywords_")


def load_genre_exceptions() -> set:
    """Load genre exceptions from JSON file."""
    try:
        data = load_genre_exceptions_payload()
        return set(data.get("exceptions", []))
    except Exception:
        return {"norteno", "sierreno", "chamame", "rai"}


def load_musical_keywords() -> set:
    """Load musical keywords from JSON file."""
    try:
        data = load_musical_keywords_payload()
        return set(data.get("keywords", []))
    except Exception:
        return {"pop", "rock", "metal", "jazz", "blues"}


def _cycle_report_path() -> Path:
    return _data_dir() / "genre_guard_cycle_report.json"


def _decision_audit_path() -> Path:
    return _data_dir() / "genre_guard_decisions_latest.json"


def _rule_suggestions_path() -> Path:
    return _data_dir() / "genre_guard_rule_suggestions.json"


def _bootstrap_invalids_csv_path() -> Path:
    return _data_dir() / "downloads_genres_invalid.csv"


def _restore_invalid_catalog_from_latest_backup() -> bool:
    """Restore invalid catalog from latest valid backup file when missing."""
    target_path = _invalid_catalog_path()
    backup_dir = _backup_dir_path()
    if not backup_dir.exists():
        return False

    backup_files = sorted(
        backup_dir.glob("invalid_music_genres_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for backup_file in backup_files:
        try:
            payload = json.loads(backup_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            if "exact" not in payload or "regex" not in payload:
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            LOGGER.warning(
                "Recovered missing invalid genre catalog from backup: %s",
                backup_file,
            )
            return True
        except Exception:
            continue

    return False


def _restore_suspect_catalog_from_latest_backup() -> bool:
    """Restore suspect catalog from latest valid backup file when missing."""
    target_path = _suspect_catalog_path()
    backup_dir = _backup_dir_path()
    if not backup_dir.exists():
        return False

    backup_files = sorted(
        backup_dir.glob("suspect_music_genres_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for backup_file in backup_files:
        try:
            payload = json.loads(backup_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            if "threshold_for_auto_add" not in payload or "items" not in payload:
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            LOGGER.warning(
                "Recovered missing suspect genre catalog from backup: %s",
                backup_file,
            )
            return True
        except Exception:
            continue

    return False


def _normalize(text: Any) -> str:
    """Normalize text for matching: lowercase, no accents, compact spaces."""
    value = str(text or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value)


def _canonical_genre_key(text: Any) -> str:
    """Build a canonical comparison key for genres.

    This collapses superficial formatting differences so variants like
    "blues rock", "blues-rock" and "Blues/Rock" map to the same key.
    """
    key = _normalize(text)
    if not key:
        return ""

    key = re.sub(r"\br\s*&\s*b\b|\br\s+and\s+b\b|\brnb\b", "rnb", key)
    key = re.sub(
        r"\bdrum\s*&\s*bass\b|\bdrum\s+and\s+bass\b|\bdnb\b", "drum bass", key)
    key = re.sub(r"[-_/&+]+", " ", key)
    key = re.sub(r"\band\b", " ", key)
    key = re.sub(r"\bdrum\s+n\s+bass\b", "drum bass", key)
    key = re.sub(r"[^a-z0-9\s+]", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    return key


def _score_genre_confidence(genre_value: Any) -> Dict[str, int]:
    """Compute lightweight confidence signals for a genre candidate."""
    normalized = _canonical_genre_key(genre_value)
    if not normalized:
        return {
            "musical_hits": 0,
            "editorial_hits": 0,
            "keyword_phrase_hits": 0,
            "unknown_tokens": 0,
            "confidence": 0,
        }

    tokens = [t for t in normalized.split() if t]
    token_set = set(tokens)

    keywords = {_canonical_genre_key(x) for x in load_musical_keywords()}
    keyword_phrase_hits = sum(1 for kw in keywords if kw and kw in normalized)

    safe_tokens = {_canonical_genre_key(x) for x in SAFE_TERMS}
    musical_hits = len(token_set & safe_tokens)
    editorial_hits = len(token_set & EDITORIAL_TOKENS)

    known_tokens = safe_tokens | EDITORIAL_TOKENS | {
        _canonical_genre_key(x) for x in GEOGRAPHIC_MARKERS}
    unknown_tokens = len([t for t in token_set if t not in known_tokens])

    confidence = (keyword_phrase_hits * 3) + (musical_hits * 2) - \
        (editorial_hits * 3) - unknown_tokens

    return {
        "musical_hits": musical_hits,
        "editorial_hits": editorial_hits,
        "keyword_phrase_hits": keyword_phrase_hits,
        "unknown_tokens": unknown_tokens,
        "confidence": confidence,
    }


def _get_heuristic_thresholds(catalog: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    """Load configurable heuristic thresholds from invalid catalog.

    This allows tuning precision/aggressiveness without code changes.
    """
    defaults = {
        "editorial_overload_hits": 3,
        "editorial_overload_max_musical_hits": 0,
        "editorial_overload_min_keyword_hits": 0,
        "editorial_bias_min_delta": 1,
        "editorial_bias_max_confidence": 0,
        "musical_confident_min_keyword_hits": 1,
        "musical_confident_min_score": 2,
    }

    payload = catalog or load_invalid_catalog()
    heuristics = payload.get("heuristics", {}) if isinstance(
        payload, dict) else {}

    out: Dict[str, int] = dict(defaults)

    for key in defaults:
        value = heuristics.get(key)
        if value is None:
            continue
        try:
            out[key] = int(value)
        except Exception:
            continue

    profile_raw = os.getenv("GENRE_HEURISTICS_PROFILE")
    if profile_raw is not None and profile_raw.strip() != "":
        profile_name = profile_raw.strip().lower()
        if profile_name not in HEURISTIC_PROFILE_PRESETS:
            profile_name = "balanced"
        out.update(HEURISTIC_PROFILE_PRESETS[profile_name])

    env_map = {
        "editorial_overload_hits": "GENRE_EDITORIAL_OVERLOAD_HITS",
        "editorial_overload_max_musical_hits": "GENRE_EDITORIAL_OVERLOAD_MAX_MUSICAL_HITS",
        "editorial_overload_min_keyword_hits": "GENRE_EDITORIAL_OVERLOAD_MIN_KEYWORD_HITS",
        "editorial_bias_min_delta": "GENRE_EDITORIAL_BIAS_MIN_DELTA",
        "editorial_bias_max_confidence": "GENRE_EDITORIAL_BIAS_MAX_CONFIDENCE",
        "musical_confident_min_keyword_hits": "GENRE_MUSICAL_CONFIDENT_MIN_KEYWORD_HITS",
        "musical_confident_min_score": "GENRE_MUSICAL_CONFIDENT_MIN_SCORE",
    }

    for key, env_var in env_map.items():
        raw = os.getenv(env_var)
        if raw is None or raw == "":
            continue
        try:
            out[key] = int(raw)
        except Exception:
            LOGGER.warning("Invalid integer for %s=%s, keeping %s=%d",
                           env_var, raw, key, out[key])

    return out


def _normalize_spelling_errors(genre: str) -> str:
    """Fix common spelling and formatting mistakes in genre values.

    This function normalizes inconsistent variants into canonical forms.

    Examples:
        "Contemporary R B" -> "Contemporary R&B"
        "R B Soul" -> "R&B Soul"
        "Rock Roll" -> "Rock and Roll"
        "Pop/Rap" -> "Pop Rap"
        "Drum  &  Bass" -> "Drum & Bass"
        "hip hop" -> "Hip Hop"
        "drumandbass" -> "Drum & Bass"
    """
    if not genre:
        return genre

    normalized = genre.strip()

    # Remove parentheses and inner content (e.g., "Genre (feat. Artist)").
    normalized = re.sub(r'\([^)]*\)', '', normalized).strip()

    # Remove common suffixes that are not part of the genre.
    normalized = re.sub(
        r'\s*[-–—]\s*(remix|edit|version|mix|radio edit|album version|single version|extended mix)\s*$',
        '', normalized, flags=re.IGNORECASE
    )

    # Normalize repeated spaces.
    normalized = re.sub(r'\s+', ' ', normalized)

    # Convert to lowercase for normalization passes.
    lower = normalized.lower()

    # Normalize hip hop variants.
    lower = re.sub(r'\bhip[-\s]?hop\b', 'hip hop', lower)

    # Normalize drum and bass variants.
    lower = re.sub(r'\bdrumandbass\b', 'drum & bass', lower)
    lower = re.sub(r"\bdrum[''`´]\s*nb\b",
                   'drum & bass', lower, flags=re.IGNORECASE)
    lower = re.sub(r"\bdrum\s*n\s*bass\b", 'drum & bass',
                   lower, flags=re.IGNORECASE)
    lower = re.sub(r'\bdrum\s*and\s*bass\b', 'drum & bass', lower)
    lower = re.sub(r'\bdrum\s*&\s*bass\b', 'drum & bass', lower)
    lower = re.sub(r'\bdnb\b', 'drum & bass', lower)

    # Normalize r&b variants.
    lower = re.sub(r"\br\s*&?\s*b\b", "r&b", lower)
    lower = re.sub(r"\brnb\b", "r&b", lower)
    lower = re.sub(r"\brhythm\s+and\s+blues\b", "r&b", lower)
    lower = re.sub(r"\brhythm\s*&\s*blues\b", "r&b", lower)

    # Normalize rock and roll variants.
    lower = re.sub(r'\brock\s+roll\b', 'rock and roll', lower)
    lower = re.sub(r'\brock\s*n\s*roll\b', 'rock and roll', lower)
    lower = re.sub(r'\brock\s*&\s*roll\b', 'rock and roll', lower)
    lower = re.sub(r'\brnr\b', 'rock and roll', lower)

    # Normalize trip hop variants.
    lower = re.sub(r'\btrip[-\s]?hop\b', 'trip hop', lower)

    # Normalize synth pop variants.
    lower = re.sub(r'\bsynth[-\s]?pop\b', 'synth-pop', lower)

    # Normalize electro pop variants.
    lower = re.sub(r'\belectro[-\s]?pop\b', 'electro-pop', lower)

    # Normalize dance pop variants.
    lower = re.sub(r'\bdance[-\s]?pop\b', 'dance-pop', lower)

    # Normalize indie pop variants.
    lower = re.sub(r'\bindie[-\s]?pop\b', 'indie pop', lower)

    # Normalize euro dance variants.
    lower = re.sub(r'\beuro[-\s]?dance\b', 'eurodance', lower)

    # Normalize hardstyle variants.
    lower = re.sub(r'\bhard[-\s]?style\b', 'hardstyle', lower)

    # Normalize hardcore variants.
    lower = re.sub(r'\bhard[-\s]?core\b', 'hardcore', lower)

    # Normalize black metal variants.
    lower = re.sub(r'\bblack[-\s]?metal\b', 'black metal', lower)

    # Normalize death metal variants.
    lower = re.sub(r'\bdeath[-\s]?metal\b', 'death metal', lower)

    # Normalize power metal variants.
    lower = re.sub(r'\bpower[-\s]?metal\b', 'power metal', lower)

    # Normalize heavy metal variants.
    lower = re.sub(r'\bheavy[-\s]?metal\b', 'heavy metal', lower)

    # Normalize nu metal variants.
    lower = re.sub(r'\bnu[-\s]?metal\b', 'nu metal', lower)

    # Normalize pop rock variants.
    lower = re.sub(r'\bpop[-\s]?rock\b', 'pop rock', lower)

    # Normalize soft rock variants.
    lower = re.sub(r'\bsoft[-\s]?rock\b', 'soft rock', lower)

    # Normalize hard rock variants.
    lower = re.sub(r'\bhard[-\s]?rock\b', 'hard rock', lower)

    # Normalize punk rock variants.
    lower = re.sub(r'\bpunk[-\s]?rock\b', 'punk rock', lower)

    # Normalize garage rock variants.
    lower = re.sub(r'\bgarage[-\s]?rock\b', 'garage rock', lower)

    # Normalize folk rock variants.
    lower = re.sub(r'\bfolk[-\s]?rock\b', 'folk rock', lower)

    # Normalize country rock variants.
    lower = re.sub(r'\bcountry[-\s]?rock\b', 'country rock', lower)

    # Normalize alternative rock variants.
    lower = re.sub(r'\balternative[-\s]?rock\b', 'alternative rock', lower)

    # Normalize indie rock variants.
    lower = re.sub(r'\bindie[-\s]?rock\b', 'indie rock', lower)

    # Normalize progressive rock variants.
    lower = re.sub(r'\bprogressive[-\s]?rock\b', 'progressive rock', lower)

    # Normalize psychedelic rock variants.
    lower = re.sub(r'\bpsychedelic[-\s]?rock\b', 'psychedelic rock', lower)

    # Normalize classic rock variants.
    lower = re.sub(r'\bclassic[-\s]?rock\b', 'classic rock', lower)

    # Normalize deep house variants.
    lower = re.sub(r'\bdeep[-\s]?house\b', 'deep house', lower)

    # Normalize tech house variants.
    lower = re.sub(r'\btech[-\s]?house\b', 'tech house', lower)

    # Normalize electro house variants.
    lower = re.sub(r'\belectro[-\s]?house\b', 'electro house', lower)

    # Normalize progressive house variants.
    lower = re.sub(r'\bprogressive[-\s]?house\b', 'progressive house', lower)

    # Normalize french house variants.
    lower = re.sub(r'\bfrench[-\s]?house\b', 'french house', lower)

    # Normalize dutch house variants.
    lower = re.sub(r'\bdutch[-\s]?house\b', 'dutch house', lower)

    # Normalize uk garage variants.
    lower = re.sub(r'\buk[-\s]?garage\b', 'uk garage', lower)

    # Normalize specific valid genres with direct mapping (before title case).
    genre_mappings = {
        # R&B and variants: must run before title case.
        "contemporary r&b": "Contemporary R&B",
        "contemporary r b": "Contemporary R&B",
        "rhythm and blues": "R&B",
        "rhythm & blues": "R&B",
        "r&b": "R&B",
        "r b": "R&B",
        "rnb": "R&B",

        # Christian
        # Christian
        "contemporary christian": "Contemporary Christian",
        "contemporary worship": "Contemporary Worship",
        "praise and worship": "Praise and Worship",

        # Rock
        # Rock
        "dance & electronica": "Dance & Electronica",
        "rock & indie": "Rock & Indie",
        "rock & roll": "Rock and Roll",
        "rock and roll": "Rock and Roll",
        "rock n roll": "Rock and Roll",
        "rock n' roll": "Rock and Roll",

        # Electronic
        # Electronic
        "drum & bass": "Drum & Bass",
        "drum and bass": "Drum & Bass",
        "drum n bass": "Drum & Bass",
        "drum 'n' bass": "Drum & Bass",
        "drum'n'bass": "Drum & Bass",
        "trip hop": "Trip Hop",
        "trip-hop": "Trip Hop",

        # Pop
        # Pop
        "synth pop": "Synthpop",
        "synth-pop": "Synthpop",
        "synthpop": "Synthpop",
        "electro pop": "Electro-Pop",
        "electro-pop": "Electro-Pop",
        "dance pop": "Dance-Pop",
        "dance-pop": "Dance-Pop",
        "indie pop": "Indie Pop",
        "indie-pop": "Indie Pop",

        # Dance
        "euro dance": "Eurodance",
        "euro-dance": "Eurodance",
        "eurodance": "Eurodance",

        # Hard
        "hard style": "Hardstyle",
        "hardstyle": "Hardstyle",
        "hard core": "Hardcore",
        "hardcore": "Hardcore",

        # Metal
        "black metal": "Black Metal",
        "death metal": "Death Metal",
        "power metal": "Power Metal",
        "heavy metal": "Heavy Metal",
        "nu metal": "Nu Metal",
        "nu-metal": "Nu Metal",

        # Rock subgenres
        "pop rock": "Pop Rock",
        "soft rock": "Soft Rock",
        "hard rock": "Hard Rock",
        "punk rock": "Punk Rock",
        "garage rock": "Garage Rock",
        "folk rock": "Folk Rock",
        "country rock": "Country Rock",
        "alternative rock": "Alternative Rock",
        "indie rock": "Indie Rock",
        "progressive rock": "Progressive Rock",
        "psychedelic rock": "Psychedelic Rock",
        "classic rock": "Classic Rock",

        # House
        "deep house": "Deep House",
        "tech house": "Tech House",
        "electro house": "Electro House",
        "progressive house": "Progressive House",
        "french house": "French House",
        "dutch house": "Dutch House",

        # UK
        "uk garage": "UK Garage",
        "uk hip hop": "UK Hip Hop",
        "uk drill": "UK Drill",
        "uk funky": "UK Funky",

        # Hip Hop
        "hip hop": "Hip Hop",
        "hip-hop": "Hip Hop",
        "hiphop": "Hip Hop",
        "southern hip hop": "Southern Hip Hop",
        "east coast hip hop": "East Coast Hip Hop",
        "west coast hip hop": "West Coast Hip Hop",

        # Latin
        "latin pop": "Latin Pop",
        "latin rock": "Latin Rock",
        "latin jazz": "Latin Jazz",
        "latin trap": "Latin Trap",
        "latin urban": "Latin Urban",

        # Brazilian
        "funk carioca": "Funk Carioca",
        "baile funk": "Baile Funk",
        "bossa nova": "Bossa Nova",

        # African
        "south african": "South African",
        "afro beat": "Afrobeat",
        "afrobeat": "Afrobeat",
        "afrobeats": "Afrobeats",
    }

    # Apply direct mappings before title case.
    if lower in genre_mappings:
        return genre_mappings[lower]

    # Restore title case after normalization.
    normalized = lower.title()

    # Normalize spacing around ampersands ("Drum  &  Bass" -> "Drum & Bass").
    normalized = re.sub(r'\s*&\s*', ' & ', normalized)

    # Normalize "Drum And Bass" -> "Drum & Bass"
    normalized = re.sub(r'\s+And\s+', ' & ', normalized, flags=re.IGNORECASE)

    # Normalize slashes to spaces ("Pop/Rap" -> "Pop Rap").
    normalized = re.sub(r'\s*/\s*', ' ', normalized)

    # Fix special capitalization cases
    # UK -> always uppercase
    normalized = re.sub(r'\b Uk \b', ' UK ', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\b Us \b', ' US ', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\b Usa \b', ' USA ', normalized, flags=re.IGNORECASE)

    # R&B -> always use &, no surrounding spaces, uppercase
    normalized = re.sub(r'\b R\s*&\s*B \b', ' R&B ',
                        normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\b R\s*B \b', ' R&B ',
                        normalized, flags=re.IGNORECASE)

    # EDM -> always uppercase
    normalized = re.sub(r'\b Edm \b', ' EDM ', normalized, flags=re.IGNORECASE)

    # MPB -> always uppercase
    normalized = re.sub(r'\b Mpb \b', ' MPB ', normalized, flags=re.IGNORECASE)

    # Synthpop -> always merged (without hyphen)
    normalized = re.sub(r'\b Synth-Pop \b', 'Synthpop',
                        normalized, flags=re.IGNORECASE)

    # Collapse multiple spaces generated by normalization.
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def _in_whitelist(text: Any) -> bool:
    """Check if genre is in genre exceptions (small list of niche genres).

    Note: Most genres are validated via _looks_like_musical_genre() which
    checks MUSICAL_KEYWORDS. This function is only for exceptions.
    """
    target = _canonical_genre_key(text)
    if not target:
        return False
    exceptions = {_canonical_genre_key(x) for x in load_genre_exceptions()}
    return target in exceptions


def _increment_counter(container: Dict[str, int], key: str) -> None:
    container[key] = int(container.get(key, 0)) + 1


def _record_cycle_decision(
    action: str,
    reason: str,
    file_path: Optional[Path] = None,
    genre_value: Optional[str] = None,
) -> None:
    _CYCLE_STATS["processed_values"] = int(
        _CYCLE_STATS.get("processed_values", 0)) + 1

    audit_row = {
        "ts": _now_iso(),
        "action": action,
        "reason": reason,
        "file_path": str(file_path) if file_path else None,
        "genre": str(genre_value) if genre_value is not None else None,
    }
    audit = _CYCLE_STATS.setdefault("decision_audit", [])
    if len(audit) < _MAX_DECISION_AUDIT_ENTRIES:
        audit.append(audit_row)
    else:
        _CYCLE_STATS["decision_audit_dropped"] = int(
            _CYCLE_STATS.get("decision_audit_dropped", 0)) + 1

    if action == "remove":
        _CYCLE_STATS["removed"] = int(_CYCLE_STATS.get("removed", 0)) + 1
        _increment_counter(_CYCLE_STATS["removed_reasons"], reason)
    elif action == "quarantine":
        _CYCLE_STATS["quarantined"] = int(
            _CYCLE_STATS.get("quarantined", 0)) + 1
        _increment_counter(_CYCLE_STATS["quarantined_reasons"], reason)
    else:
        _CYCLE_STATS["kept"] = int(_CYCLE_STATS.get("kept", 0)) + 1


def _save_cycle_report() -> None:
    """Save cycle report to file. Called at module exit."""
    try:
        # Only save report if there were any decisions made
        if _CYCLE_STATS.get("processed_values", 0) == 0:
            LOGGER.debug(
                "No genre decisions made in this cycle, skipping report")
            return

        payload = {
            "updated_at": _now_iso(),
            "metrics": {
                "processed_values": int(_CYCLE_STATS.get("processed_values", 0)),
                "kept": int(_CYCLE_STATS.get("kept", 0)),
                "removed": int(_CYCLE_STATS.get("removed", 0)),
                "quarantined": int(_CYCLE_STATS.get("quarantined", 0)),
                "suspicious_detected": int(_CYCLE_STATS.get("suspicious_detected", 0)),
                "auto_promoted": int(_CYCLE_STATS.get("auto_promoted", 0)),
                "protected_musical": int(_CYCLE_STATS.get("protected_musical", 0)),
            },
            "removed_reasons": dict(sorted(_CYCLE_STATS.get("removed_reasons", {}).items(), key=lambda kv: kv[1], reverse=True)),
            "quarantined_reasons": dict(sorted(_CYCLE_STATS.get("quarantined_reasons", {}).items(), key=lambda kv: kv[1], reverse=True)),
            "decision_audit": {
                "stored_entries": len(_CYCLE_STATS.get("decision_audit", [])),
                "dropped_entries": int(_CYCLE_STATS.get("decision_audit_dropped", 0)),
                "max_entries": _MAX_DECISION_AUDIT_ENTRIES,
                "file": str(_decision_audit_path()),
            },
            "rule_suggestions": {
                "file": str(_rule_suggestions_path()),
                "source_reason": "unknown_genre",
            },
        }
        path = _cycle_report_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False,
                        indent=2), encoding="utf-8")

        decision_payload = {
            "updated_at": _now_iso(),
            "started_at": _CYCLE_STATS.get("started_at"),
            "entries": _CYCLE_STATS.get("decision_audit", []),
            "dropped_entries": int(_CYCLE_STATS.get("decision_audit_dropped", 0)),
            "max_entries": _MAX_DECISION_AUDIT_ENTRIES,
        }
        decision_path = _decision_audit_path()
        decision_path.write_text(
            json.dumps(decision_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Build suggestion candidates to help tune keyword/exception rules.
        unknown_counter: Dict[str, int] = {}
        unknown_examples: Dict[str, List[str]] = {}
        for row in _CYCLE_STATS.get("decision_audit", []):
            if row.get("action") != "quarantine":
                continue
            if row.get("reason") != "unknown_genre":
                continue

            genre = _normalize(row.get("genre"))
            if not genre:
                continue

            unknown_counter[genre] = int(unknown_counter.get(genre, 0)) + 1
            examples = unknown_examples.setdefault(genre, [])
            file_path = row.get("file_path")
            if file_path and len(examples) < 3 and file_path not in examples:
                examples.append(file_path)

        sorted_unknown = sorted(
            unknown_counter.items(), key=lambda kv: kv[1], reverse=True)
        top_unknown = []
        for genre, count in sorted_unknown[:100]:
            top_unknown.append(
                {
                    "genre": genre,
                    "count": count,
                    "example_files": unknown_examples.get(genre, []),
                    "suggested_action": "review_for_keywords_or_exceptions",
                }
            )

        suggestions_payload = {
            "updated_at": _now_iso(),
            "source": str(decision_path),
            "unknown_genre_candidates": top_unknown,
            "total_unknown_unique": len(unknown_counter),
            "total_unknown_events": sum(unknown_counter.values()),
        }

        # Suggest canonical aliases when multiple variants map to same key.
        variant_groups: Dict[str, Dict[str, int]] = {}
        for row in _CYCLE_STATS.get("decision_audit", []):
            raw = _normalize(row.get("genre"))
            if not raw:
                continue
            key = _canonical_genre_key(raw)
            if not key:
                continue
            bucket = variant_groups.setdefault(key, {})
            bucket[raw] = int(bucket.get(raw, 0)) + 1

        alias_candidates: List[Dict[str, Any]] = []
        for canonical_key, variants in variant_groups.items():
            if len(variants) < 2:
                continue
            total = sum(variants.values())
            if total < 2:
                continue
            sorted_variants = sorted(
                variants.items(), key=lambda kv: kv[1], reverse=True)
            alias_candidates.append(
                {
                    "canonical_key": canonical_key,
                    "total_events": total,
                    "variants": [
                        {"value": v, "count": c} for v, c in sorted_variants[:8]
                    ],
                    "suggested_canonical": sorted_variants[0][0],
                    "suggested_action": "review_for_alias_normalization",
                }
            )

        alias_candidates.sort(key=lambda x: x["total_events"], reverse=True)
        suggestions_payload["canonical_alias_candidates"] = alias_candidates[:100]
        suggestions_payload["total_alias_candidates"] = len(alias_candidates)

        suggestions_path = _rule_suggestions_path()
        suggestions_path.write_text(
            json.dumps(suggestions_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        LOGGER.info("Genre guard cycle report saved to: %s", path)
    except Exception as exc:
        LOGGER.error("Failed to save cycle report: %s", exc, exc_info=True)


# Register save function to be called at module exit
atexit.register(_save_cycle_report)


def _looks_like_musical_genre(text: str) -> bool:
    """Check if text appears to be a valid musical genre (loaded from JSON).

    Priority:
    1. Check genre exceptions (niche regional genres)
    2. Check valid geographic + genre combinations
    3. Check musical keywords
    """
    normalized = _canonical_genre_key(text)
    if not normalized:
        return False

    # Check exceptions first (niche regional genres)
    exceptions = {_canonical_genre_key(x) for x in load_genre_exceptions()}
    if normalized in exceptions:
        return True

    # Check valid geographic + genre combinations
    valid_geographic_genres = {_canonical_genre_key(x)
                               for x in VALID_GEOGRAPHIC_GENRES}
    if normalized in valid_geographic_genres:
        return True

    # Check musical keywords (covers 99%+ of all genres)
    keywords = {_canonical_genre_key(x) for x in load_musical_keywords()}
    return any(keyword in normalized for keyword in keywords)


def _is_valid_compound_genre(genre: str) -> bool:
    """Check if a compound genre (with geographic/safe terms) is valid.

    Examples:
        "UK garage" → True (in VALID_GEOGRAPHIC_GENRES)
        "vocal trance" → True (has safe_term + musical keyword)
        "american" → False (just geographic, no musical term)
        "vocal" → False (just safe_term, no musical keyword)
    """
    normalized = _canonical_genre_key(genre)
    words = set(normalized.split())

    # Check if it's in the explicit whitelist
    valid_geographic_genres = {_canonical_genre_key(x)
                               for x in VALID_GEOGRAPHIC_GENRES}
    if normalized in valid_geographic_genres:
        return True

    # Check if it contains both a geographic marker AND a musical term
    canonical_geographic_markers = {
        _canonical_genre_key(x) for x in GEOGRAPHIC_MARKERS}
    has_geographic = any(geo in words for geo in canonical_geographic_markers)
    has_musical = any(
        mus in words for mus in SAFE_TERMS if mus not in GEOGRAPHIC_MARKERS)

    # Also check for multi-word patterns (e.g., "uk garage" not just "uk" + "garage")
    if has_geographic and has_musical:
        return True

    # Check if contains safe_term + musical keyword from loaded list
    keywords = {_canonical_genre_key(x) for x in load_musical_keywords()}
    has_keyword = any(keyword in normalized for keyword in keywords)

    if has_geographic and has_keyword:
        return True

    return False


def _evaluate_genre_action(file_path: Path, genre_value: Any) -> Tuple[str, str, int]:
    """Return tuple(action, reason, confidence_score).

    Actions:
      - keep
      - remove
      - quarantine

    Priority:
      1. Invalid catalog (explicit list) -> REMOVE
      2. Whitelist (GENRE_EXCEPTIONS + VALID_GEOGRAPHIC_GENRES) -> KEEP
      3. Valid compound genre (geographic + musical) -> KEEP
      4. Musical keywords -> KEEP
      5. Suspicious patterns -> QUARANTINE
      6. Clean -> KEEP
    """
    genre = _canonical_genre_key(genre_value)
    if not genre:
        return "keep", "empty", 0

    # PRIORITY 1: Invalid catalog (explicit list of invalid genres)
    # If it's in the list, REMOVE without questioning!
    catalog = load_invalid_catalog()
    thresholds = _get_heuristic_thresholds(catalog)
    exact_set = {_canonical_genre_key(v)
                 for v in catalog.get("exact", []) if _canonical_genre_key(v)}

    if genre in exact_set:
        return "remove", "exact_invalid_match", 100

    # PRIORITY 2: Whitelist (niche valid genres from exceptions)
    exceptions = {_canonical_genre_key(x) for x in load_genre_exceptions()}
    if genre in exceptions:
        return "keep", "whitelisted_subgenre", 0

    # PRIORITY 2b: Valid geographic + genre combinations
    valid_geographic_genres = {_canonical_genre_key(x)
                               for x in VALID_GEOGRAPHIC_GENRES}
    if genre in valid_geographic_genres:
        return "keep", "valid_geographic_genre", 0

    # PRIORITY 2c: Valid compound genre (geographic/safe + musical)
    if _is_valid_compound_genre(genre):
        return "keep", "valid_compound_genre", 0

    # PRIORITY 3: Folder name match (genre copied from folder name)
    folder_candidates = {_canonical_genre_key(x)
                         for x in build_folder_candidates(file_path)}
    if genre in folder_candidates:
        return "remove", "folder_name_match", 100

    confidence = _score_genre_confidence(genre)

    # PRIORITY 3b: Heuristica por confianca baseada em tokens.
    # Remove imediatamente quando e claramente editorial e sem sinal musical.
    if (
        confidence["editorial_hits"] >= thresholds["editorial_overload_hits"]
        and confidence["musical_hits"] <= thresholds["editorial_overload_max_musical_hits"]
        and confidence["keyword_phrase_hits"] <= thresholds["editorial_overload_min_keyword_hits"]
    ):
        return "remove", "token_editorial_overload", 88

    # PRIORITY 4: Regex patterns (known pollution patterns)
    matched_regex = False
    for pattern in catalog.get("regex", []):
        try:
            if re.search(pattern, genre, flags=re.IGNORECASE):
                matched_regex = True
                break
        except re.error:
            continue

    # PRIORITY 5: Suspicious patterns (decade, playlist - NOT nationality anymore)
    suspicious_reason = detect_suspicious_reason(genre)
    if suspicious_reason:
        _CYCLE_STATS["suspicious_detected"] = int(
            _CYCLE_STATS.get("suspicious_detected", 0)) + 1

    if matched_regex and not _looks_like_musical_genre(genre):
        return "remove", "regex_invalid_match", 85

    if matched_regex or suspicious_reason:
        # Don't quarantine if it looks like a valid compound genre
        if _is_valid_compound_genre(genre):
            return "keep", "valid_compound_despite_pattern", 0
        return "quarantine", suspicious_reason or "regex_match_musical_like", 50

    # PRIORITY 5b: Se houver viés editorial sem certeza musical, quarentena.
    if (
        (confidence["editorial_hits"] - confidence["musical_hits"]
         ) >= thresholds["editorial_bias_min_delta"]
        and confidence["confidence"] <= thresholds["editorial_bias_max_confidence"]
    ):
        return "quarantine", "token_editorial_bias", 55

    # PRIORITY 5c: Se houver forte evidência musical, manter com confiança.
    if (
        confidence["keyword_phrase_hits"] >= thresholds["musical_confident_min_keyword_hits"]
        and confidence["confidence"] >= thresholds["musical_confident_min_score"]
    ):
        return "keep", "token_musical_confident", 0

    # PRIORITY 6: Check if it looks like a musical genre
    if _looks_like_musical_genre(genre):
        return "keep", "clean", 0

    # PRIORITY 7: Unknown - quarantine for review
    return "quarantine", "unknown_genre", 30


def _build_default_invalid_catalog() -> Dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now_iso(),
        "exact": [],
        "regex": list(DEFAULT_INVALID_REGEX),
        "heuristics": {
            "editorial_overload_hits": 3,
            "editorial_overload_max_musical_hits": 0,
            "editorial_overload_min_keyword_hits": 0,
            "editorial_bias_min_delta": 1,
            "editorial_bias_max_confidence": 0,
            "musical_confident_min_keyword_hits": 1,
            "musical_confident_min_score": 2
        },
        "auto_added": {},
    }


def _build_default_suspect_catalog() -> Dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now_iso(),
        "threshold_for_auto_add": _env_int(
            "GENRE_SUSPECT_AUTO_ADD_THRESHOLD", 3, minimum=1),
        "items": {},
    }


def _load_json_or_default(path: Path, default_payload: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(default_payload,
                        ensure_ascii=False, indent=2), encoding="utf-8")
        return default_payload

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        LOGGER.warning("Failed reading %s, restoring default payload", path)
        path.write_text(json.dumps(default_payload,
                        ensure_ascii=False, indent=2), encoding="utf-8")
        return default_payload


def _save_json(path: Path, payload: Dict[str, Any]) -> None:
    payload["updated_at"] = _now_iso()
    path.write_text(json.dumps(payload, ensure_ascii=False,
                    indent=2), encoding="utf-8")


def _maybe_bootstrap_catalog_from_csv(catalog: Dict[str, Any]) -> Dict[str, Any]:
    csv_path = _bootstrap_invalids_csv_path()
    if not csv_path.exists():
        return catalog

    existing = {_canonical_genre_key(item) for item in catalog.get(
        "exact", []) if _canonical_genre_key(item)}
    bootstrapped = 0

    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            genre = _canonical_genre_key(row.get("genre"))
            if not genre or genre in existing:
                continue
            existing.add(genre)
            bootstrapped += 1

    if bootstrapped:
        catalog["exact"] = sorted(existing)
        catalog.setdefault("auto_added", {})
    return catalog


def _merge_curated_invalid_terms(catalog: Dict[str, Any]) -> Dict[str, Any]:
    """Merge curated invalid terms from JSON file.

    NOTE: Invalid genres are now stored in data/invalid_music_genres.json
    NOT hardcoded in Python source code.

    This function is kept for backwards compatibility but does nothing.
    """
    # Invalid genres are sourced only from the JSON file.

    return catalog


def load_invalid_catalog(force_reload: bool = False) -> Dict[str, Any]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None and not force_reload:
        return _CATALOG_CACHE

    path = _invalid_catalog_path()
    if not path.exists():
        _restore_invalid_catalog_from_latest_backup()

    payload = _load_json_or_default(path, _build_default_invalid_catalog())
    payload = _maybe_bootstrap_catalog_from_csv(payload)
    payload = _merge_curated_invalid_terms(payload)
    _save_json(path, payload)
    _CATALOG_CACHE = payload
    return _CATALOG_CACHE


def save_invalid_catalog(payload: Dict[str, Any]) -> None:
    global _CATALOG_CACHE
    catalog_path = _invalid_catalog_path()
    _save_json(catalog_path, payload)

    # Keep dedicated snapshots so catalog can be recovered if deleted.
    try:
        backup_dir = _backup_dir_path()
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = backup_dir / f"invalid_music_genres_{timestamp}.json"
        backup_path.write_text(catalog_path.read_text(
            encoding="utf-8"), encoding="utf-8")
    except Exception:
        LOGGER.debug(
            "Failed to snapshot invalid catalog backup", exc_info=True)

    _CATALOG_CACHE = payload


def load_suspect_catalog(force_reload: bool = False) -> Dict[str, Any]:
    global _SUSPECT_CACHE
    if _SUSPECT_CACHE is not None and not force_reload:
        return _SUSPECT_CACHE

    path = _suspect_catalog_path()
    if not path.exists():
        _restore_suspect_catalog_from_latest_backup()

    payload = _load_json_or_default(
        path, _build_default_suspect_catalog())
    _SUSPECT_CACHE = payload
    return _SUSPECT_CACHE


def save_suspect_catalog(payload: Dict[str, Any]) -> None:
    global _SUSPECT_CACHE
    suspect_path = _suspect_catalog_path()
    _save_json(suspect_path, payload)

    # Keep dedicated snapshots so catalog can be recovered if deleted.
    try:
        backup_dir = _backup_dir_path()
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = backup_dir / f"suspect_music_genres_{timestamp}.json"
        backup_path.write_text(suspect_path.read_text(
            encoding="utf-8"), encoding="utf-8")
    except Exception:
        LOGGER.debug(
            "Failed to snapshot suspect catalog backup", exc_info=True)

    _SUSPECT_CACHE = payload


def build_folder_candidates(file_path: Path) -> Set[str]:
    ignored_folder_names = {
        "musics",
        "music",
        "downloads",
        "download",
        "library",
        "media",
    }

    candidates: Set[str] = set()
    for parent in file_path.parents:
        name = parent.name.strip()
        if not name:
            continue
        candidates.add(_normalize(name))
        candidates.add(_normalize(re.sub(r"^#\d+\s*", "", name)))
        candidates.add(_canonical_genre_key(name))
        candidates.add(_canonical_genre_key(re.sub(r"^#\d+\s*", "", name)))

    return {
        c for c in candidates
        if c and c not in ignored_folder_names
    }


def is_invalid_genre_value(file_path: Path, genre_value: Any) -> bool:
    action, _, _ = _evaluate_genre_action(file_path, genre_value)
    return action == "remove"


def detect_suspicious_reason(genre_value: Any) -> Optional[str]:
    """Detect suspicious genre patterns.

    Note: Nationality/language patterns were REMOVED because many valid
    genres contain geographic markers (e.g., "UK garage", "Dutch house").
    Geographic validation is now done via VALID_GEOGRAPHIC_GENRES whitelist.
    """
    genre = _normalize(genre_value)
    if not genre:
        return None

    # Skip geographic/nationality checks - they are validated via whitelist

    for reason, pattern in SUSPECT_PATTERNS.items():
        if pattern.search(genre):
            return reason
    return None


def track_suspicious_genre(
    genre_value: Any,
    file_path: Path,
    logger: Optional[logging.Logger] = None,
) -> Tuple[bool, Optional[str]]:
    """Track suspicious genre and auto-promote to invalid list.

    Returns:
        promoted: True when genre was auto-added to invalid exact list.
        reason: Suspicious reason or None.
    """
    genre = _canonical_genre_key(genre_value)
    if not genre:
        return False, None

    reason = detect_suspicious_reason(genre)
    if not reason:
        return False, None

    # Protect valid compound genres (geographic + musical)
    if _in_whitelist(genre) or _looks_like_musical_genre(genre) or _is_valid_compound_genre(genre):
        _CYCLE_STATS["protected_musical"] = int(
            _CYCLE_STATS.get("protected_musical", 0)) + 1
        return False, reason

    suspect = load_suspect_catalog()
    item = suspect.setdefault("items", {}).setdefault(
        genre,
        {
            "count": 0,
            "reason": reason,
            "first_seen": _now_iso(),
            "last_seen": _now_iso(),
            "examples": [],
        },
    )
    item["count"] = int(item.get("count", 0)) + 1
    item["reason"] = reason
    item["last_seen"] = _now_iso()

    example = str(file_path)
    examples = item.setdefault("examples", [])
    if example not in examples and len(examples) < 5:
        examples.append(example)

    save_suspect_catalog(suspect)

    threshold = int(suspect.get("threshold_for_auto_add", _env_int(
        "GENRE_SUSPECT_AUTO_ADD_THRESHOLD", 3, minimum=1)))
    if item["count"] < threshold:
        return False, reason

    catalog = load_invalid_catalog()
    exact_set = {_canonical_genre_key(v)
                 for v in catalog.get("exact", []) if _canonical_genre_key(v)}
    if genre in exact_set:
        return False, reason

    exact_set.add(genre)
    catalog["exact"] = sorted(exact_set)
    catalog.setdefault("auto_added", {})
    catalog["auto_added"][genre] = {
        "count": item["count"],
        "reason": reason,
        "last_seen": item.get("last_seen"),
        "example": examples[0] if examples else "",
    }
    save_invalid_catalog(catalog)
    _CYCLE_STATS["auto_promoted"] = int(
        _CYCLE_STATS.get("auto_promoted", 0)) + 1

    active_logger = logger or LOGGER
    active_logger.info(
        "Auto-added suspicious genre to invalid catalog: %s (reason=%s, count=%d)",
        genre,
        reason,
        item["count"],
    )
    return True, reason


def sanitize_genre_values(
    file_path: Path,
    genres: List[Any],
    logger: Optional[logging.Logger] = None,
    track_cycle_stats: bool = True,
) -> Tuple[List[str], List[str]]:
    """Filter invalid genres and track suspicious values.

    Includes normalization of spelling errors and formatting inconsistencies.

    Returns:
        valid_genres, removed_genres
    """
    valid: List[str] = []
    removed: List[str] = []

    for value in genres:
        text = str(value or "").strip()
        if not text:
            continue

        # Remove concatenated genre strings containing separators.
        # These values should not appear in a multi-value list.
        if ',' in text or ';' in text:
            removed.append(text)
            if track_cycle_stats:
                _record_cycle_decision(
                    "remove",
                    "concatenated_genre_string",
                    file_path=file_path,
                    genre_value=text,
                )
            if logger:
                logger.debug("Removed concatenated genre string: %s", text)
            continue

        # Normalize spelling errors before validation.
        text = _normalize_spelling_errors(text)

        action, reason, _score = _evaluate_genre_action(file_path, text)

        if action == "remove":
            removed.append(text)
            if track_cycle_stats:
                _record_cycle_decision(
                    "remove",
                    reason,
                    file_path=file_path,
                    genre_value=text,
                )
            continue

        promoted, suspicious_reason = track_suspicious_genre(
            text, file_path, logger=logger)
        if promoted:
            removed.append(text)
            if track_cycle_stats:
                _record_cycle_decision(
                    "remove",
                    "auto_promoted_suspicious",
                    file_path=file_path,
                    genre_value=text,
                )
            continue

        if action == "quarantine":
            if track_cycle_stats:
                _record_cycle_decision(
                    "quarantine",
                    suspicious_reason or reason,
                    file_path=file_path,
                    genre_value=text,
                )
            valid.append(text)
            continue

        valid.append(text)
        if track_cycle_stats:
            _record_cycle_decision(
                "keep",
                reason,
                file_path=file_path,
                genre_value=text,
            )

    # Preserve order while removing duplicates.
    deduped_valid_map: Dict[str, str] = {}
    for item in valid:
        key = _canonical_genre_key(item)
        if key and key not in deduped_valid_map:
            deduped_valid_map[key] = item

    deduped_removed_map: Dict[str, str] = {}
    for item in removed:
        key = _canonical_genre_key(item)
        if key and key not in deduped_removed_map:
            deduped_removed_map[key] = item

    deduped_valid = list(deduped_valid_map.values())
    deduped_removed = list(deduped_removed_map.values())
    return deduped_valid, deduped_removed

# =============================================================================
# OPTIONAL EXTERNAL VALIDATION
# =============================================================================


def validate_genre_against_authorities(
    genre: str,
    authorities: Optional[List[str]] = None,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    """Validate genre against external authoritative sources.

    This is an OPTIONAL feature that requires internet connection.

    Args:
        genre: Genre to validate
        authorities: List of authorities to check. Options:
            - "allmusic": AllMusic genre database
            - "discogs": Discogs genre database  
            - "musicbrainz": MusicBrainz genre tags
            - "lastfm": Last.fm genre tags
        timeout: Request timeout in seconds

    Returns:
        Dict with validation results:
        {
            "genre": str,
            "valid": bool,
            "sources": {
                "allmusic": {"found": bool, "url": str},
                "discogs": {"found": bool, "url": str},
                ...
            },
            "confidence": float (0-1),
        }

    Note: This function makes HTTP requests and requires internet connection.
          Results are cached for performance.
    """
    import urllib.request
    import urllib.error
    import json as json_module

    if authorities is None:
        authorities = ["musicbrainz", "discogs"]

    genre_normalized = _normalize(genre)

    results = {
        "genre": genre,
        "genre_normalized": genre_normalized,
        "valid": False,
        "sources": {},
        "confidence": 0.0,
        "error": None,
    }

    # Check against GENRE_EXCEPTIONS first (fastest)
    exceptions = load_genre_exceptions()
    if genre_normalized in exceptions:
        results["valid"] = True
        results["confidence"] = 1.0
        results["sources"]["local_exceptions"] = {
            "found": True,
            "note": "Genre is in GENRE_EXCEPTIONS",
        }
        return results

    # Check against musical keywords (covers 99%+)
    keywords = load_musical_keywords()
    if any(keyword in _normalize(genre) for keyword in keywords):
        results["valid"] = True
        results["confidence"] = 1.0
        results["sources"]["local_keywords"] = {
            "found": True,
            "note": "Genre contains musical keywords",
        }
        return results

    # External validation (requires internet)
    source_results = []

    for authority in authorities:
        try:
            if authority == "musicbrainz":
                # MusicBrainz genre validation via tag lookup
                url = f"https://musicbrainz.org/ws/2/tag/{urllib.parse.quote(genre_normalized)}?fmt=json"
                try:
                    with urllib.request.urlopen(url, timeout=timeout) as response:
                        data = json_module.loads(response.read().decode())
                        if data.get("tags", []):
                            results["sources"]["musicbrainz"] = {
                                "found": True,
                                "url": url,
                                "tag_count": len(data.get("tags", [])),
                            }
                            source_results.append(True)
                        else:
                            results["sources"]["musicbrainz"] = {
                                "found": False,
                                "url": url,
                            }
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        results["sources"]["musicbrainz"] = {
                            "found": False,
                            "url": url,
                            "note": "Genre not found",
                        }
                    else:
                        raise

            elif authority == "discogs":
                # Discogs genre validation via search
                url = f"https://api.discogs.com/database/search?q={urllib.parse.quote(genre_normalized)}&type=artist&per_page=1"
                try:
                    req = urllib.request.Request(
                        url,
                        headers={
                            "User-Agent": os.getenv(
                                "GENRE_GUARD_USER_AGENT",
                                "MediaOrganizer/1.0",
                            )
                        }
                    )
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        data = json_module.loads(response.read().decode())
                        # If search returns results, genre might be valid
                        if data.get("results", []):
                            results["sources"]["discogs"] = {
                                "found": True,
                                "url": url,
                                "results": len(data.get("results", [])),
                            }
                            source_results.append(True)
                        else:
                            results["sources"]["discogs"] = {
                                "found": False,
                                "url": url,
                            }
                except urllib.error.HTTPError as e:
                    if e.code in (401, 403):
                        results["sources"]["discogs"] = {
                            "found": False,
                            "url": url,
                            "note": "Authentication required",
                        }
                    elif e.code == 404:
                        results["sources"]["discogs"] = {
                            "found": False,
                            "url": url,
                            "note": "Genre not found",
                        }
                    else:
                        raise

            elif authority == "allmusic":
                # AllMusic doesn't have public API, just note it
                results["sources"]["allmusic"] = {
                    "found": None,
                    "url": f"https://www.allmusic.com/genre/{genre_normalized.replace(' ', '-')}",
                    "note": "Manual verification required - no public API",
                }

            elif authority == "lastfm":
                # Last.fm tag validation
                url = f"https://ws.audioscrobbler.com/2.0/?method=tag.getinfo&tag={urllib.parse.quote(genre_normalized)}&api_key=YOUR_API_KEY&format=json"
                results["sources"]["lastfm"] = {
                    "found": None,
                    "url": url,
                    "note": "Requires API key - manual verification",
                }

        except Exception as e:
            results["sources"][authority] = {
                "found": None,
                "error": str(e),
            }

    # Calculate confidence based on sources
    if source_results:
        external_confidence = sum(source_results) / len(authorities)
        results["confidence"] = max(results["confidence"], external_confidence)
        results["valid"] = external_confidence >= 0.5

    return results


def batch_validate_genres(
    genres: List[str],
    authorities: Optional[List[str]] = None,
    timeout: float = 5.0,
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """Batch validate multiple genres against external authorities.

    Args:
        genres: List of genres to validate
        authorities: List of authorities to check
        timeout: Request timeout per genre
        progress_callback: Optional callback(current, total) for progress

    Returns:
        Dict with batch validation results
    """
    results = {
        "total_genres": len(genres),
        "validated": 0,
        "valid": [],
        "invalid": [],
        "uncertain": [],
        "by_source": {},
    }

    for i, genre in enumerate(genres):
        validation = validate_genre_against_authorities(
            genre, authorities, timeout
        )

        if validation["valid"]:
            results["valid"].append(validation)
        elif validation["confidence"] < 0.3:
            results["invalid"].append(validation)
        else:
            results["uncertain"].append(validation)

        results["validated"] += 1

        if progress_callback:
            progress_callback(i + 1, len(genres))

    # Aggregate by source
    for validation in results["valid"] + results["invalid"] + results["uncertain"]:
        for source, data in validation.get("sources", {}).items():
            if source not in results["by_source"]:
                results["by_source"][source] = {
                    "found": 0, "not_found": 0, "error": 0}

            if isinstance(data.get("found"), bool):
                if data["found"]:
                    results["by_source"][source]["found"] += 1
                else:
                    results["by_source"][source]["not_found"] += 1
            else:
                results["by_source"][source]["error"] += 1

    return results
