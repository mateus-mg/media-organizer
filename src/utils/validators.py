"""
Validation utilities for paths, files, and configurations
"""

import os
import re
from pathlib import Path
from typing import Tuple, Optional


def validate_path_exists(path: Path, create_if_missing: bool = False) -> Tuple[bool, str]:
    """
    Validate that a path exists
    
    Args:
        path: Path to validate
        create_if_missing: Create directory if it doesn't exist
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path:
        return False, "Path is empty"
    
    if not path.exists():
        if create_if_missing and not path.suffix:  # It's a directory
            try:
                path.mkdir(parents=True, exist_ok=True)
                return True, ""
            except Exception as e:
                return False, f"Failed to create directory: {e}"
        else:
            return False, f"Path does not exist: {path}"
    
    return True, ""


def validate_file_accessible(file_path: Path) -> Tuple[bool, str]:
    """
    Validate that a file is accessible for reading
    
    Args:
        file_path: File path to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path.exists():
        return False, f"File does not exist: {file_path}"
    
    if not file_path.is_file():
        return False, f"Path is not a file: {file_path}"
    
    if not os.access(file_path, os.R_OK):
        return False, f"File is not readable: {file_path}"
    
    return True, ""


def validate_writable_directory(dir_path: Path) -> Tuple[bool, str]:
    """
    Validate that a directory is writable
    
    Args:
        dir_path: Directory path to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not dir_path.exists():
        return False, f"Directory does not exist: {dir_path}"
    
    if not dir_path.is_dir():
        return False, f"Path is not a directory: {dir_path}"
    
    if not os.access(dir_path, os.W_OK):
        return False, f"Directory is not writable: {dir_path}"
    
    return True, ""


def validate_video_file(file_path: Path) -> bool:
    """
    Check if file is a valid video file
    
    Args:
        file_path: Path to file
    
    Returns:
        True if valid video file
    """
    video_extensions = {
        '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', 
        '.webm', '.m4v', '.mpg', '.mpeg', '.m2ts', '.ts'
    }
    return file_path.suffix.lower() in video_extensions


def validate_audio_file(file_path: Path) -> bool:
    """
    Check if file is a valid audio file
    
    Args:
        file_path: Path to file
    
    Returns:
        True if valid audio file
    """
    audio_extensions = {
        '.mp3', '.flac', '.wav', '.aac', '.ogg', '.opus',
        '.m4a', '.wma', '.alac', '.ape', '.wv'
    }
    return file_path.suffix.lower() in audio_extensions


def validate_subtitle_file(file_path: Path) -> bool:
    """
    Check if file is a valid subtitle file
    
    Args:
        file_path: Path to file
    
    Returns:
        True if valid subtitle file
    """
    subtitle_extensions = {'.srt', '.ass', '.ssa', '.vtt', '.sub', '.idx'}
    return file_path.suffix.lower() in subtitle_extensions


def validate_book_file(file_path: Path) -> bool:
    """
    Check if file is a valid book file
    
    Args:
        file_path: Path to file
    
    Returns:
        True if valid book file
    """
    book_extensions = {
        '.epub', '.pdf', '.mobi', '.azw', '.azw3', 
        '.cbz', '.cbr', '.cb7', '.cbt'
    }
    return file_path.suffix.lower() in book_extensions


def is_temporary_file(file_path: Path) -> bool:
    """
    Check if file is a temporary/incomplete download
    
    Args:
        file_path: Path to file
    
    Returns:
        True if temporary file
    """
    temp_extensions = {'.part', '.tmp', '.temp', '.download', '.!qB', '.crdownload'}
    temp_prefixes = {'~', '.'}
    
    # Check extension
    if file_path.suffix.lower() in temp_extensions:
        return True
    
    # Check if hidden file (starts with .)
    if file_path.name.startswith('.') and not file_path.name.startswith('..'):
        return True
    
    return False


def validate_filename_safe(filename: str) -> Tuple[bool, str]:
    """
    Validate that filename is safe for all platforms
    
    Args:
        filename: Filename to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Invalid characters for Windows/Linux/macOS
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    
    if re.search(invalid_chars, filename):
        return False, f"Filename contains invalid characters: {filename}"
    
    # Reserved names on Windows
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    name_without_ext = Path(filename).stem.upper()
    if name_without_ext in reserved_names:
        return False, f"Filename uses reserved name: {filename}"
    
    # Check length (255 bytes on most filesystems)
    if len(filename.encode('utf-8')) > 255:
        return False, f"Filename too long: {filename}"
    
    return True, ""


def sanitize_filename(filename: str, replacement: str = '_') -> str:
    """
    Sanitize filename for safe use across platforms
    
    Args:
        filename: Filename to sanitize
        replacement: Character to replace invalid chars with
    
    Returns:
        Sanitized filename
    """
    # Replace invalid characters
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, replacement, filename)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')
    
    # Ensure not a reserved name
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    stem = Path(sanitized).stem.upper()
    if stem in reserved_names:
        sanitized = f"{replacement}{sanitized}"
    
    # Truncate if too long (leave room for extension)
    max_length = 200  # Conservative limit
    if len(sanitized) > max_length:
        ext = Path(sanitized).suffix
        name = Path(sanitized).stem
        sanitized = name[:max_length - len(ext)] + ext
    
    return sanitized


def validate_year(year: int) -> bool:
    """
    Validate that year is reasonable for media
    
    Args:
        year: Year to validate
    
    Returns:
        True if valid year
    """
    from datetime import datetime
    current_year = datetime.now().year
    # Media from 1900 to next year
    return 1900 <= year <= current_year + 1


def validate_season_episode(season: int, episode: int) -> bool:
    """
    Validate season and episode numbers
    
    Args:
        season: Season number
        episode: Episode number
    
    Returns:
        True if valid
    """
    # Season 0-99, Episode 1-9999
    return 0 <= season <= 99 and 1 <= episode <= 9999
