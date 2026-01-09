"""
File operations module
Handles file operations with hardlinks, hashing, and subtitle management
"""

import os
import hashlib
import time
import shutil
from pathlib import Path
from typing import Optional, List, Tuple
from .validators import (
    validate_file_accessible,
    validate_writable_directory,
    sanitize_filename,
    validate_subtitle_file,
    is_temporary_file
)


def calculate_file_hash(file_path: Path, algorithm: str = 'sha256') -> Optional[str]:
    """
    Calculate file hash

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, md5)

    Returns:
        Hex digest of file hash or None if error
    """
    try:
        if algorithm == 'sha256':
            hasher = hashlib.sha256()
        elif algorithm == 'md5':
            hasher = hashlib.md5()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)

        return hasher.hexdigest()

    except Exception as e:
        print(f"Error calculating hash: {e}")
        return None


def calculate_partial_hash(file_path: Path, chunk_size_mb: int = 1) -> Optional[str]:
    """
    Calculate partial file hash (first + last chunks) for fast duplicate detection.
    Much faster than full hash for large files.

    Args:
        file_path: Path to file
        chunk_size_mb: Size in MB to read from start and end

    Returns:
        Hex digest of partial hash or None if error
    """
    try:
        file_size = file_path.stat().st_size
        chunk_bytes = chunk_size_mb * 1024 * 1024

        hasher = hashlib.sha256()

        with open(file_path, 'rb') as f:
            # Read first chunk
            first_chunk = f.read(min(chunk_bytes, file_size))
            hasher.update(first_chunk)

            # Read last chunk if file is large enough
            if file_size > chunk_bytes * 2:
                f.seek(-chunk_bytes, 2)  # Seek to last chunk
                last_chunk = f.read(chunk_bytes)
                hasher.update(last_chunk)

            # Include file size in hash to differentiate files
            hasher.update(str(file_size).encode())

        return hasher.hexdigest()

    except Exception as e:
        print(f"Error calculating partial hash: {e}")
        return None


def check_file_stability(
    file_path: Path,
    wait_time: int = 30,
    check_interval: int = 5
) -> bool:
    """
    Check if file is stable (download complete)
    Monitors file size over time

    Args:
        file_path: Path to file
        wait_time: Total time to wait in seconds
        check_interval: Interval between checks in seconds

    Returns:
        True if file is stable
    """
    if not file_path.exists():
        return False

    # Check if it's a temporary file
    if is_temporary_file(file_path):
        return False

    try:
        initial_size = file_path.stat().st_size
        checks_needed = wait_time // check_interval

        for _ in range(checks_needed):
            time.sleep(check_interval)

            if not file_path.exists():
                return False

            current_size = file_path.stat().st_size

            if current_size != initial_size:
                # Size changed, file still downloading
                initial_size = current_size
                continue

        # File size stable for required time
        return True

    except Exception:
        return False


def create_hardlink(
    source: Path,
    dest: Path,
    dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Create hardlink from source to destination

    Args:
        source: Source file path
        dest: Destination file path
        dry_run: If True, only simulate

    Returns:
        Tuple of (success, error_message)
    """
    if dry_run:
        return True, ""

    # Validate source
    is_valid, error = validate_file_accessible(source)
    if not is_valid:
        return False, error

    # Validate destination directory
    dest.parent.mkdir(parents=True, exist_ok=True)
    is_valid, error = validate_writable_directory(dest.parent)
    if not is_valid:
        return False, error

    try:
        # Create hardlink
        os.link(source, dest)
        return True, ""

    except FileExistsError:
        return False, "Destination file already exists"

    except OSError as e:
        # Hardlink not supported, try copying
        if "cross-device" in str(e).lower() or "not permitted" in str(e).lower():
            return False, "Hardlink not supported (files on different filesystems)"
        return False, f"Failed to create hardlink: {e}"

    except Exception as e:
        return False, f"Unexpected error: {e}"


def find_subtitle_files(video_path: Path) -> List[Path]:
    """
    Find subtitle files associated with a video file

    Args:
        video_path: Path to video file

    Returns:
        List of subtitle file paths
    """
    subtitle_files = []
    video_stem = video_path.stem
    parent_dir = video_path.parent

    # Look for subtitle files with same base name
    for file in parent_dir.iterdir():
        if file.is_file() and validate_subtitle_file(file):
            # Check if filename starts with video stem
            if file.stem.startswith(video_stem):
                subtitle_files.append(file)

    return subtitle_files


def parse_subtitle_language(subtitle_path: Path) -> Tuple[str, List[str]]:
    """
    Parse language and flags from subtitle filename

    Supports formats like:
    - filename.en.srt
    - filename.pt.br.srt
    - filename.en.forced.srt
    - filename.es.sdh.srt

    Args:
        subtitle_path: Path to subtitle file

    Returns:
        Tuple of (language_code, flags)
    """
    parts = subtitle_path.stem.split('.')
    extension = subtitle_path.suffix

    # Remove base filename (everything before language code)
    # Typically: Movie.Name.2024.en.forced.srt
    # We want to extract: en, [forced]

    language = ""
    flags = []

    # Common language codes (2-letter and some 3-letter)
    language_codes = {
        'en', 'pt', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'zh', 'ru',
        'ar', 'hi', 'nl', 'pl', 'tr', 'sv', 'no', 'da', 'fi',
        'eng', 'por', 'spa', 'fra', 'deu', 'ita', 'jpn', 'kor'
    }

    # Common flags
    flag_keywords = {'forced', 'sdh', 'cc', 'hi', 'full'}

    # Parse from right to left (after base name)
    for part in reversed(parts):
        part_lower = part.lower()

        if part_lower in language_codes and not language:
            language = part_lower
        elif part_lower in flag_keywords:
            flags.insert(0, part_lower)
        elif '.' in part_lower:  # Multi-part language (pt.br)
            sub_parts = part_lower.split('.')
            if sub_parts[0] in language_codes:
                language = part_lower
                break

    return language, flags


def rename_subtitle_for_video(
    subtitle_path: Path,
    video_base_name: str,
    dest_dir: Path,
    dry_run: bool = False
) -> Optional[Path]:
    """
    Rename subtitle file to match video naming convention

    Args:
        subtitle_path: Original subtitle path
        video_base_name: Base name of video file (without extension)
        dest_dir: Destination directory
        dry_run: If True, only simulate

    Returns:
        New subtitle path or None if failed
    """
    language, flags = parse_subtitle_language(subtitle_path)
    extension = subtitle_path.suffix

    # Build new filename: VideoName.language.flag.ext
    parts = [video_base_name]

    if language:
        parts.append(language)

    for flag in flags:
        parts.append(flag)

    new_filename = '.'.join(parts) + extension
    new_path = dest_dir / new_filename

    if dry_run:
        return new_path

    try:
        # Create hardlink for subtitle
        dest_dir.mkdir(parents=True, exist_ok=True)
        os.link(subtitle_path, new_path)
        return new_path

    except Exception as e:
        print(f"Error renaming subtitle: {e}")
        return None


def move_subtitles_with_video(
    video_source: Path,
    video_dest: Path,
    dry_run: bool = False
) -> List[Path]:
    """
    Find and move all subtitle files associated with a video

    Args:
        video_source: Source video file path
        video_dest: Destination video file path
        dry_run: If True, only simulate

    Returns:
        List of moved subtitle paths
    """
    moved_subtitles = []

    # Find subtitle files
    subtitle_files = find_subtitle_files(video_source)

    if not subtitle_files:
        return moved_subtitles

    # Get video base name (without extension)
    video_base = video_dest.stem
    dest_dir = video_dest.parent

    # Move each subtitle
    for subtitle in subtitle_files:
        new_path = rename_subtitle_for_video(
            subtitle,
            video_base,
            dest_dir,
            dry_run
        )

        if new_path:
            moved_subtitles.append(new_path)

    return moved_subtitles


def safe_create_directory(path: Path, dry_run: bool = False) -> bool:
    """
    Safely create directory with all parents

    Args:
        path: Directory path to create
        dry_run: If True, only simulate

    Returns:
        True if successful
    """
    if dry_run:
        return True

    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"Error creating directory: {e}")
        return False


def get_file_size(file_path: Path) -> int:
    """
    Get file size in bytes

    Args:
        file_path: Path to file

    Returns:
        File size in bytes or 0 if error
    """
    try:
        return file_path.stat().st_size
    except Exception:
        return 0


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def is_same_filesystem(path1: Path, path2: Path) -> bool:
    """
    Check if two paths are on the same filesystem
    Required for hardlinks to work

    Args:
        path1: First path
        path2: Second path

    Returns:
        True if on same filesystem
    """
    try:
        stat1 = path1.stat()
        stat2 = path2.stat()
        return stat1.st_dev == stat2.st_dev
    except Exception:
        return False


def count_hardlinks(file_path: Path) -> int:
    """
    Count number of hardlinks to a file

    Args:
        file_path: Path to file

    Returns:
        Number of hardlinks
    """
    try:
        return file_path.stat().st_nlink
    except Exception:
        return 0
