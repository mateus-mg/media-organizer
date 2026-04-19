"""
Detection module for Media Organization System

Consolidated module containing:
- MediaClassifier (Classify media by extension and context)
- FileScanner (Scan directories for media files)
- FileAnalyzer (Advanced file analysis helpers)

Usage:
    from app.core.detection import MediaClassifier, FileScanner, FileAnalyzer
"""
import re
from pathlib import Path
from typing import List, Optional, Dict
import logging

from app.core import (
    MediaType, FileMetadata,
    MediaClassifierInterface, FileScannerInterface
)
from app.config.constants import (
    AUDIO_EXTS,
    BOOK_EXTS,
    COMIC_EXTS,
    IMAGE_EXTS,
    LYRICS_EXTS,
    SUPPORTED_MEDIA_EXTS,
)
from app.metadata.metadata import MetadataParser
from app.utils.helpers import is_incomplete_file, is_junk_file


# ============================================================================
# SECTION 1: MEDIA CLASSIFIER
# ============================================================================

class MediaClassifier(MediaClassifierInterface):
    """
    Classify media files based on extension and context.

    Priority:
    1. Extension (most reliable)
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

        self.music_exts = set(AUDIO_EXTS)
        self.lyrics_exts = set(LYRICS_EXTS)
        self.image_exts = set(IMAGE_EXTS)
        self.book_exts = set(BOOK_EXTS)
        self.comic_exts = set(COMIC_EXTS)
        self.metadata_parser = MetadataParser(logger=self.logger)

    def _is_pdf_in_comics_downloads(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != ".pdf":
            return False

        parts = [part.lower() for part in file_path.parts]
        for idx in range(len(parts) - 1):
            if parts[idx] == "downloads" and parts[idx + 1] == "comics":
                return True

        return False

    def _is_image_in_music_downloads(self, file_path: Path) -> bool:
        if file_path.suffix.lower() not in self.image_exts:
            return False

        parts = [part.lower() for part in file_path.parts]
        for idx in range(len(parts) - 1):
            if parts[idx] == "downloads" and parts[idx + 1] in {"music", "musics"}:
                return True

        return False

    def _has_local_audio_pair(self, file_path: Path) -> bool:
        for audio_ext in self.music_exts:
            if file_path.with_suffix(audio_ext).exists():
                return True
        return False

    def classificar_tipo_midia(self, file_path: Path) -> MediaType:
        """
        Classify media type

        Args:
            file_path: Path to file

        Returns:
            MediaType enum value
        """
        ext = file_path.suffix.lower()
        # Check by extension first
        if ext in self.music_exts:
            return MediaType.MUSIC
        if ext in self.lyrics_exts:
            return MediaType.LYRICS
        if ext in self.image_exts and (
            self._is_image_in_music_downloads(file_path)
            or self._has_local_audio_pair(file_path)
        ):
            return MediaType.ARTWORK
        if self._is_pdf_in_comics_downloads(file_path):
            return MediaType.COMIC
        if ext in self.comic_exts:
            return MediaType.COMIC
        if ext in self.book_exts:
            return MediaType.BOOK

        return MediaType.UNKNOWN

    def extrair_metadados(self, file_path: Path) -> FileMetadata:
        """
        Extract basic metadata from filename

        Args:
            file_path: Path to file

        Returns:
            FileMetadata with extracted info
        """
        media_type = self.classificar_tipo_midia(file_path)

        metadata = FileMetadata(
            media_type=media_type,
            extra_metadata={'file_path': str(file_path)}
        )

        if media_type == MediaType.BOOK:
            book_data = self.metadata_parser.parse_book_filename(file_path)
            if book_data.get('title'):
                metadata.title = str(book_data['title'])
            if book_data.get('author'):
                metadata.author = str(book_data['author'])
            if isinstance(book_data.get('year'), int):
                metadata.year = book_data['year']

        # Extract year from filename
        filename = file_path.stem
        year_match = re.search(r'\b(19|20)\d{2}\b', filename)
        if year_match:
            try:
                metadata.year = int(year_match.group(0))
            except ValueError:
                pass

        return metadata


# ============================================================================
# SECTION 2: FILE SCANNER
# ============================================================================

class FileScanner(FileScannerInterface):
    """
    Scan directories for media files.

    Supports recursive scanning with extension filtering.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

        self.media_extensions = set(SUPPORTED_MEDIA_EXTS)

    def escanear_diretorio(self, diretorio: Path) -> List[Path]:
        """
        Scan directory recursively for media files

        Args:
            diretorio: Directory to scan

        Returns:
            List of media file paths
        """
        if not diretorio.exists() or not diretorio.is_dir():
            self.logger.error(f"Directory not found: {diretorio}")
            return []

        media_files = [
            file_path
            for file_path in diretorio.rglob('*')
            if file_path.is_file() and file_path.suffix.lower() in self.media_extensions
        ]

        self.logger.info(f"Found {len(media_files)} media files")
        return media_files

    def filtrar_arquivos_para_organizacao(self, arquivos: List[Path]) -> List[Path]:
        """
        Filter files for organization

        Args:
            arquivos: List of file paths

        Returns:
            Filtered list of files
        """
        filtered = []

        for file_path in arquivos:
            # Skip incomplete
            if is_incomplete_file(file_path):
                continue

            # Skip hidden
            if file_path.name.startswith('.'):
                continue

            # Skip junk
            if is_junk_file(file_path):
                self.logger.debug(f"Skipping junk: {file_path.name}")
                continue

            filtered.append(file_path)

        self.logger.info(f"Filtered to {len(filtered)} files")
        return filtered

# ============================================================================
# SECTION 3: FILE ANALYZER (HELPER)
# ============================================================================


class FileAnalyzer:
    """
    Advanced file analysis for detailed metadata extraction.

    Provides additional analysis beyond basic classification.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def analyze_audio(self, file_path: Path) -> Dict[str, str]:
        """
        Analyze audio file for track info

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary with extracted metadata
        """
        filename = file_path.stem
        analysis = {}

        # Try to extract track number from beginning
        track_match = re.match(r'^(\d{1,2})[\s\-_]', filename)
        if track_match:
            analysis['track_number'] = track_match.group(1)

        return analysis

    def analyze_book(self, file_path: Path) -> Dict[str, str]:
        """
        Analyze book file for title/author/year

        Args:
            file_path: Path to book file

        Returns:
            Dictionary with extracted metadata
        """
        filename = file_path.stem
        analysis = {}

        # Try pattern: "Author - Title (Year)"
        match = re.match(r'^(.+?)\s*-\s*(.+?)\s*\((\d{4})\)', filename)
        if match:
            analysis['author'] = match.group(1).strip()
            analysis['title'] = match.group(2).strip()
            analysis['year'] = match.group(3)
        else:
            # Just extract year if present
            year_match = re.search(r'\((\d{4})\)', filename)
            if year_match:
                analysis['year'] = year_match.group(1)

        return analysis
