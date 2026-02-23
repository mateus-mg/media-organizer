"""
Detection module for Media Organization System

Consolidated module containing:
- MediaClassifier (Classify media by extension and context)
- FileScanner (Scan directories for media files)
- FileAnalyzer (Advanced file analysis helpers)

Usage:
    from src.detection import MediaClassifier, FileScanner, FileAnalyzer
"""
import re
from pathlib import Path
from typing import List, Optional, Dict
import logging

from src.core import (
    MediaType, FileMetadata,
    MediaClassifierInterface, FileScannerInterface
)


# ============================================================================
# SECTION 1: MEDIA CLASSIFIER
# ============================================================================

class MediaClassifier(MediaClassifierInterface):
    """
    Classify media files based on extension and context.
    
    Priority:
    1. Extension (most reliable)
    2. Parent folder context
    3. Filename patterns
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
        self.music_exts = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus', '.m4b'}
        self.book_exts = {'.epub', '.pdf', '.mobi', '.azw', '.azw3'}
        self.comic_exts = {'.cbz', '.cbr', '.cb7', '.cbt'}
        self.video_exts = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
    
    def classificar_tipo_midia(self, file_path: Path) -> MediaType:
        """
        Classify media type
        
        Args:
            file_path: Path to file
            
        Returns:
            MediaType enum value
        """
        ext = file_path.suffix.lower()
        filename = file_path.name.lower()
        
        # Check by extension first
        if ext in self.music_exts:
            return MediaType.MUSIC
        if ext in self.book_exts:
            return MediaType.BOOK
        if ext in self.comic_exts:
            return MediaType.COMIC
        
        if ext in self.video_exts:
            return self._classify_video(filename, file_path.parents)
        
        return MediaType.UNKNOWN
    
    def _classify_video(self, filename: str, parents) -> MediaType:
        """Classify video file using patterns and context"""
        # Check for episode patterns
        episode_patterns = [
            r's\d{1,2}e\d{1,2}',      # S01E01
            r'\d{1,2}x\d{1,2}',       # 1x01
            r'season[\s\._-]*\d+',    # Season 1
            r'episode[\s\._-]*\d+',   # Episode 1
            r'ep[\s\._-]*\d+',        # Ep 01
        ]
        
        has_episode = any(re.search(p, filename, re.IGNORECASE) for p in episode_patterns)
        
        # Check folder context
        parent_folders = [p.name.lower() for p in parents]
        
        if has_episode:
            if 'animes' in parent_folders or 'anime' in parent_folders:
                return MediaType.ANIME
            elif 'doramas' in parent_folders or 'dorama' in parent_folders:
                return MediaType.DORAMA
            else:
                return MediaType.TV_SHOW
        
        # Context without episode pattern
        if 'animes' in parent_folders or 'anime' in parent_folders:
            return MediaType.ANIME
        elif 'doramas' in parent_folders or 'dorama' in parent_folders:
            return MediaType.DORAMA
        elif 'tv' in parent_folders or 'series' in parent_folders:
            return MediaType.TV_SHOW
        
        return MediaType.MOVIE
    
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
        
        self.media_extensions = {
            # Video
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
            # Audio
            '.mp3', '.flac', '.ogg', '.m4a', '.wma', '.aac', '.opus', '.wav', '.m4b',
            # Books
            '.epub', '.pdf', '.mobi', '.azw', '.azw3',
            # Comics
            '.cbz', '.cbr', '.cb7', '.cbt'
        }
    
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
        
        media_files = []
        for ext in self.media_extensions:
            media_files.extend(diretorio.rglob(f'*{ext}'))
        
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
            if self._is_incomplete(file_path):
                continue
            
            # Skip hidden
            if file_path.name.startswith('.'):
                continue
            
            # Skip junk
            if self._is_junk(file_path):
                self.logger.debug(f"Skipping junk: {file_path.name}")
                continue
            
            filtered.append(file_path)
        
        self.logger.info(f"Filtered to {len(filtered)} files")
        return filtered
    
    def _is_incomplete(self, file_path: Path) -> bool:
        """Check if file is incomplete (still downloading)"""
        incomplete_exts = {'.part', '.tmp', '.!qB', '.crdownload', '.download'}
        
        if file_path.suffix.lower() in incomplete_exts:
            return True
        
        try:
            if file_path.stat().st_size == 0:
                return True
        except:
            return True
        
        return False
    
    def _is_junk(self, file_path: Path) -> bool:
        """Check if file is junk/promotional"""
        filename = file_path.name.upper()
        
        junk_names = {'BLUDV.MP4', '1XBET.MP4', 'SAMPLE.MP4', 'TRAILER.MP4'}
        if filename in junk_names:
            return True
        
        junk_patterns = ['BLUDV', '1XBET', 'SAMPLE', 'WWW.', '_PROMO_', 'DINHEIRO_LIVRE', 'ACESSE']
        for pattern in junk_patterns:
            if pattern in filename:
                try:
                    if file_path.stat().st_size < 100 * 1024 * 1024:
                        return True
                except:
                    pass
        
        return False


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
    
    def analyze_video(self, file_path: Path) -> Dict[str, str]:
        """
        Analyze video file for season/episode/year
        
        Args:
            file_path: Path to video file
            
        Returns:
            Dictionary with extracted metadata
        """
        filename = file_path.stem
        analysis = {}
        
        # Extract season/episode
        patterns = [
            r'[Ss](\d{1,2})[Ee](\d{1,2})',  # S01E01
            r'(\d{1,2})x(\d{1,2})',          # 1x01
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                analysis['season'] = match.group(1)
                analysis['episode'] = match.group(2)
                break
        
        # Extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', filename)
        if year_match:
            analysis['year'] = year_match.group(0)
        
        return analysis
    
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
