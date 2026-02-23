"""
Metadata module for Media Organization System

Consolidated module containing:
- Audio metadata extraction (ID3 tags)
- Online metadata fetchers (OpenLibrary, Google Books, MusicBrainz)
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
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass


# ============================================================================
# SECTION 1: AUDIO METADATA
# ============================================================================

def extract_audio_metadata(file_path: Path, logger=None) -> Dict:
    """
    Extract metadata from audio file
    
    Args:
        file_path: Path to audio file
        logger: Logger instance
        
    Returns:
        Dictionary with extracted metadata
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
                metadata['title'] = str(audio.tags.get('TIT2', ''))
                metadata['artist'] = str(audio.tags.get('TPE1', ''))
                metadata['album'] = str(audio.tags.get('TALB', ''))
                metadata['genre'] = str(audio.tags.get('TCON', ''))
                metadata['track_number'] = str(audio.tags.get('TRCK', ''))
                metadata['year'] = str(audio.tags.get('TDRC', ''))
        
        elif ext == '.flac':
            from mutagen.flac import FLAC
            
            audio = FLAC(file_path)
            metadata['title'] = audio.get('title', [''])[0]
            metadata['artist'] = audio.get('artist', [''])[0]
            metadata['album'] = audio.get('album', [''])[0]
            metadata['genre'] = audio.get('genre', [''])[0]
            metadata['track_number'] = audio.get('tracknumber', [''])[0]
            metadata['year'] = audio.get('date', [''])[0]
        
        return metadata
    except Exception as e:
        logger.error(f"Error extracting audio metadata: {e}")
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
    logger=None
) -> Dict:
    """
    Enrich book metadata from OpenLibrary/Google Books
    
    Args:
        file_path: Path to book file
        existing_metadata: Existing metadata dict
        logger: Logger instance
        
    Returns:
        Updated metadata dict
    """
    logger = logger or logging.getLogger(__name__)
    
    try:
        title = existing_metadata.get('title', '')
        author = existing_metadata.get('author', '')
        
        if not title:
            return existing_metadata
        
        async with aiohttp.ClientSession() as session:
            # OpenLibrary search
            url = f"https://openlibrary.org/search.json?title={title}&author={author}&limit=1"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('docs'):
                        doc = data['docs'][0]
                        
                        existing_metadata['isbn'] = doc.get('isbn', [None])[0]
                        existing_metadata['publisher'] = doc.get('publisher', [None])[0]
                        existing_metadata['year'] = doc.get('first_publish_year')
                        existing_metadata['subjects'] = doc.get('subject', [])
                        
                        logger.info(f"Enriched from OpenLibrary: {file_path.name}")
    except Exception as e:
        logger.warning(f"OpenLibrary enrichment failed: {e}")
    
    return existing_metadata


async def enrich_music_metadata_with_online_sources(
    file_path: Path,
    existing_metadata: Dict,
    logger=None
) -> Dict:
    """
    Enrich music metadata from MusicBrainz
    
    Args:
        file_path: Path to music file
        existing_metadata: Existing metadata dict
        logger: Logger instance
        
    Returns:
        Updated metadata dict
    """
    logger = logger or logging.getLogger(__name__)
    
    try:
        artist = existing_metadata.get('artist', '')
        title = existing_metadata.get('title', '')
        
        if not artist or not title:
            return existing_metadata
        
        async with aiohttp.ClientSession() as session:
            # MusicBrainz search
            query = f"{artist} {title}"
            url = f"https://musicbrainz.org/ws/2/recording/?query={query}&fmt=json&limit=1"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('recordings'):
                        recording = data['recordings'][0]
                        
                        if 'disambiguation' in recording:
                            existing_metadata['disambiguation'] = recording['disambiguation']
                        
                        if 'isrcs' in recording:
                            existing_metadata['isrc'] = recording['isrcs'][0]
                        
                        logger.info(f"Enriched from MusicBrainz: {file_path.name}")
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
    - Video files (filename patterns)
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
    
    def parse_video_filename(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse video filename for metadata
        
        Args:
            file_path: Path to video file
            
        Returns:
            Dictionary with extracted metadata
        """
        import re
        
        filename = file_path.stem
        metadata = {}
        
        # Extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', filename)
        if year_match:
            metadata['year'] = int(year_match.group(0))
        
        # Extract season/episode
        se_match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', filename)
        if se_match:
            metadata['season'] = int(se_match.group(1))
            metadata['episode'] = int(se_match.group(2))
        
        return metadata
    
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
            metadata['author'] = match.group(1).strip()
            metadata['title'] = match.group(2).strip()
            metadata['year'] = int(match.group(3))
        else:
            # Just extract year if present
            year_match = re.search(r'\((\d{4})\)', filename)
            if year_match:
                metadata['year'] = int(year_match.group(1))
        
        return metadata


# ============================================================================
# SECTION 4: FILENAME PARSERS (LEGACY SUPPORT)
# ============================================================================

def detect_media_type(file_path: Path) -> str:
    """
    Detect media type from filename and extension
    
    Args:
        file_path: Path to file
        
    Returns:
        Media type string
    """
    filename = file_path.name.lower()
    ext = file_path.suffix.lower()
    
    music_exts = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus', '.m4b'}
    book_exts = {'.epub', '.pdf', '.mobi', '.azw', '.azw3'}
    comic_exts = {'.cbz', '.cbr', '.cb7', '.cbt'}
    video_exts = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
    
    if ext in music_exts:
        return 'music'
    if ext in book_exts:
        return 'book'
    if ext in comic_exts:
        return 'comic'
    if ext in video_exts:
        # Check for episode patterns
        episode_patterns = [
            r's\d{1,2}e\d{1,2}',
            r'\d{1,2}x\d{1,2}',
            r'season[\s\._-]*\d+',
        ]
        
        import re
        if any(re.search(p, filename, re.IGNORECASE) for p in episode_patterns):
            return 'tv'
        return 'movie'
    
    return 'unknown'
