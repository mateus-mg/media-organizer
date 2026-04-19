"""Helper utilities for Media Organization System."""

from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any, Callable
import hashlib
import re
import logging


# Constants for file validation
INCOMPLETE_EXTENSIONS = {'.part', '.tmp',
                         '.!qB', '.crdownload', '.download', '.aria2'}
JUNK_NAMES = {
    'BLUDV.MP4', 'BLUDV.TV.MP4', 'BLUDV.COM.MP4',
    '1XBET.MP4', '1XBET.COM.MP4',
    'SAMPLE.MP4', 'SAMPLE.MKV', 'SAMPLE.AVI',
    'TRAILER.MP4', 'TRAILER.MKV'
}
JUNK_PATTERNS = ['BLUDV', '1XBET', 'SAMPLE',
                 'WWW.', '_PROMO_', 'DINHEIRO_LIVRE', 'ACESSE']


def is_incomplete_file(file_path: Path) -> bool:
    """Return True when file looks incomplete or invalid for processing."""
    if file_path.suffix.lower() in INCOMPLETE_EXTENSIONS:
        return True

    try:
        if file_path.stat().st_size == 0:
            return True
    except OSError:
        return True

    return False


def is_junk_file(file_path: Path) -> bool:
    """Return True when filename matches known junk/promotional patterns."""
    filename = file_path.name.upper()

    if filename in JUNK_NAMES:
        return True

    for pattern in JUNK_PATTERNS:
        if pattern in filename:
            try:
                if file_path.stat().st_size < 100 * 1024 * 1024:
                    return True
            except OSError:
                return False

    return False


def calculate_file_hash(file_path: Path, algorithm: str = "md5", chunk_size: int = 1024 * 1024) -> str:
    """
    Calculate file hash

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256)
        chunk_size: Size of chunks to read

    Returns:
        Hex digest of hash
    """
    if algorithm == "md5":
        digest = hashlib.md5()
    elif algorithm == "sha1":
        digest = hashlib.sha1()
    elif algorithm == "sha256":
        digest = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    with open(file_path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def calculate_partial_hash(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """
    Calculate partial hash for quick file comparison

    Args:
        file_path: Path to file
        chunk_size: Size of chunk to hash

    Returns:
        Hex digest of partial hash
    """
    digest = hashlib.md5()

    try:
        file_size = file_path.stat().st_size
        chunks_to_read = min(3, (file_size // chunk_size) + 1)

        with open(file_path, "rb") as handle:
            for _ in range(chunks_to_read):
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return ""

    return digest.hexdigest()


def normalize_title(title: str) -> str:
    """
    Normalize title for consistent comparison

    Args:
        title: Original title

    Returns:
        Normalized title
    """
    if not title:
        return ""

    # Remove special characters
    for char in '<>:"/\\|?*':
        title = title.replace(char, "")

    # Normalize spaces
    title = re.sub(r'\s+', ' ', title).strip()

    return title


def normalize_comic_series_title(series: str) -> str:
    """Normalize comic series variants to keep related arcs in the same folder."""
    value = normalize_title(series or "")
    if not value:
        return ""

    # Group common arc suffixes under the base series folder.
    value = re.sub(r"\s*[-–—:]\s*(?:pr[oó]logo|ep[ií]logo)\b.*$",
                   "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*(?:[-–—:]\s*)?(?:[oô]mega|omega)\s*$",
                   "", value, flags=re.IGNORECASE)

    value = re.sub(r"\s+", " ", value).strip(" -–—:_")
    return value or normalize_title(series)


def parse_book_filename_fields(filename: str) -> Dict[str, Any]:
    """Parse canonical book filename fields.

    Accepted schemas:
    - Author - Title (Year)
    - Author - Title [Series;Index] (Year)
    - Title (Year)
    """
    stem = str(filename or "").strip()
    result: Dict[str, Any] = {
        "is_valid": False,
        "author": "Unknown Author",
        "authors": [],
        "title": "",
        "year": None,
        "series": None,
        "series_index": None,
        "error": "book_schema_invalid",
    }

    if not stem:
        result["error"] = "book_schema_empty_filename"
        return result

    year_match = re.search(r"\((?P<year>19\d{2}|20\d{2})\)\s*$", stem)
    if not year_match:
        result["error"] = "book_schema_missing_year"
        return result

    result["year"] = int(year_match.group("year"))
    core = stem[:year_match.start()].strip()

    if not core:
        result["error"] = "book_schema_missing_title"
        return result

    series_match = re.search(r"\s\[(?P<series_block>[^\[\]]+)\]\s*$", core)
    if series_match:
        series_block = series_match.group("series_block").strip()
        parts = [part.strip() for part in series_block.split(";", 1)]
        if parts and parts[0]:
            result["series"] = normalize_title(parts[0])
        if len(parts) == 2 and parts[1]:
            raw_index = parts[1]
            try:
                result["series_index"] = float(raw_index)
            except ValueError:
                result["series_index"] = raw_index
        core = core[:series_match.start()].strip()

    if not core:
        result["error"] = "book_schema_missing_title"
        return result

    if " - " in core:
        raw_author, raw_title = core.split(" - ", 1)
        authors = [part.strip()
                   for part in raw_author.split(",") if part.strip()]
        title = normalize_title(raw_title)
        if not title:
            result["error"] = "book_schema_missing_title"
            return result

        result["authors"] = authors
        result["author"] = authors[0] if authors else raw_author.strip(
        ) or "Unknown Author"
        result["title"] = title
    else:
        title = normalize_title(core)
        if not title:
            result["error"] = "book_schema_missing_title"
            return result
        result["title"] = title

    result["is_valid"] = True
    result["error"] = ""
    return result


def parse_comic_filename_fields(filename: str) -> Dict[str, Any]:
    """Parse canonical comic filename fields.

    Canonical schema:
    Title (Year) - Series (optional) #Issue
    """
    stem = str(filename or "").strip()
    result: Dict[str, Any] = {
        "is_valid": False,
        "title": "",
        "series": None,
        "year": None,
        "issue_number": None,
        "error": "comic_schema_invalid",
    }

    if not stem:
        result["error"] = "comic_schema_empty_filename"
        return result

    header_match = re.match(
        r"^(?P<title>.+?)\s*\((?P<year>19\d{2}|20\d{2})\)\s*(?P<tail>.*)$",
        stem,
    )
    if not header_match:
        result["error"] = "comic_schema_missing_title_or_year"
        return result

    title = normalize_title(header_match.group("title"))
    if not title:
        result["error"] = "comic_schema_missing_title_or_year"
        return result

    tail = str(header_match.group("tail") or "").strip()
    if not tail:
        result["error"] = "comic_schema_missing_issue"
        return result

    if tail.startswith("-"):
        tail = tail[1:].strip()

    issue_match = re.search(
        r"#(?P<issue>[0-9]+(?:\.[0-9]+)?[A-Za-z]?)\s*$", tail)
    if not issue_match:
        result["error"] = "comic_schema_missing_issue"
        return result

    series_raw = tail[:issue_match.start()].strip()
    series = normalize_comic_series_title(series_raw) if series_raw else None

    result["title"] = title
    result["series"] = series or None
    result["year"] = int(header_match.group("year"))
    result["issue_number"] = issue_match.group("issue")
    result["is_valid"] = True
    result["error"] = ""
    return result


def normalize_comic_filename(filename: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[int]]:
    """
    Extract series, issue, publisher, year from comic filename

    Args:
        filename: Comic filename

    Returns:
        Tuple of (series, issue, publisher, year)
    """
    parsed = parse_comic_filename_fields(filename)
    if parsed.get("is_valid"):
        series_or_title = parsed.get("series") or parsed.get("title")
        series = normalize_comic_series_title(str(series_or_title or ""))
        issue = parsed.get("issue_number")
        year = parsed.get("year")
        return series, str(issue) if issue is not None else None, None, int(year) if year is not None else None

    return None, None, None, None


def log_cycle_stage(logger: logging.Logger, title: str) -> None:
    """Emit standardized cycle stage delimiters in logs."""
    logger.info("")
    logger.info("%s", "=" * 88)
    logger.info("%s", title)
    logger.info("%s", "=" * 88)


def run_logged_cycle(
    logger: logging.Logger,
    label: str,
    run_organization: Callable[[], int],
    on_pre_organization: Optional[Callable[[], None]] = None,
    on_post_organization: Optional[Callable[[], None]] = None,
    on_cycle_start: Optional[Callable[[], None]] = None,
) -> int:
    """Run one organization cycle with standardized START/END/SUMMARY logging."""
    cycle_status = "success"
    processed = 0

    log_cycle_stage(logger, f"{label} | CYCLE START")
    try:
        if on_cycle_start is not None:
            on_cycle_start()

        if on_pre_organization is not None:
            on_pre_organization()

        log_cycle_stage(logger, f"{label} | ORGANIZATION START")
        processed = run_organization()
        log_cycle_stage(logger, f"{label} | ORGANIZATION END")

        if on_post_organization is not None:
            on_post_organization()
    except Exception as exc:
        cycle_status = "error"
        logger.exception("%s cycle failed: %s", label, exc)
        raise
    except KeyboardInterrupt:
        cycle_status = "interrupted"
        logger.warning("%s cycle interrupted by user", label)
        raise
    finally:
        logger.info(
            "%s | CYCLE SUMMARY | status=%s | files-processed=%d",
            label,
            cycle_status,
            processed,
        )
        log_cycle_stage(logger, f"{label} | CYCLE END")

    return processed


# ============================================================================
# CONFLICT HANDLER
# ============================================================================

class ConflictResolution:
    """Conflict resolution result constants"""
    SKIPPED = "skipped"
    RENAMED = "renamed"
    OVERWRITTEN = "overwritten"
    NO_CONFLICT = "no_conflict"


class ConflictHandler:
    """
    Handle file conflicts during organization.

    Strategies:
    - skip: Keep existing file, skip new one
    - rename: Rename new file with counter
    - overwrite: Replace existing file
    """

    def __init__(
        self,
        strategy: str = "skip",
        rename_pattern: str = "{name}_{counter}{ext}",
        max_attempts: int = 100
    ):
        if strategy not in ["skip", "rename", "overwrite"]:
            raise ValueError(f"Invalid strategy: {strategy}")

        self.strategy = strategy
        self.rename_pattern = rename_pattern
        self.max_attempts = max_attempts

    def resolve(
        self,
        source_path: Path,
        dest_path: Path,
        dry_run: bool = False
    ) -> Tuple[Optional[Path], str]:
        """
        Resolve file conflict

        Args:
            source_path: Source file path
            dest_path: Destination file path
            dry_run: Dry-run mode

        Returns:
            Tuple of (resolved_path, action_taken)
        """
        if not dest_path.exists():
            return dest_path, ConflictResolution.NO_CONFLICT

        if self._are_identical(source_path, dest_path):
            return dest_path, ConflictResolution.SKIPPED

        if self.strategy == "skip":
            return dest_path, ConflictResolution.SKIPPED

        elif self.strategy == "overwrite":
            if not dry_run:
                dest_path.unlink()
            return dest_path, ConflictResolution.OVERWRITTEN

        elif self.strategy == "rename":
            new_path = self._generate_unique_name(dest_path)
            if new_path:
                return new_path, ConflictResolution.RENAMED
            return dest_path, ConflictResolution.SKIPPED

        return dest_path, ConflictResolution.SKIPPED

    def _generate_unique_name(self, base_path: Path) -> Optional[Path]:
        """Generate unique filename"""
        parent = base_path.parent
        stem = base_path.stem
        ext = base_path.suffix

        for counter in range(2, self.max_attempts + 2):
            new_name = self.rename_pattern.format(
                name=stem, counter=counter, ext=ext
            )
            new_path = parent / new_name

            if not new_path.exists():
                return new_path

        return None

    def _are_identical(self, file1: Path, file2: Path) -> bool:
        """Check if files are identical"""
        try:
            if file1.stat().st_ino == file2.stat().st_ino:
                return True
        except OSError:
            pass

        try:
            if file1.stat().st_size != file2.stat().st_size:
                return False
        except OSError:
            return False

        # Compare partial hash
        return calculate_partial_hash(file1) == calculate_partial_hash(file2)
