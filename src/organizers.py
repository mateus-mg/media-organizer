"""
Organizers module for Media Organization System

Consolidated module containing all media organizers:
- BaseOrganizer (Common functionality)
- MovieOrganizer (Movies with TMDB ID)
- TVOrganizer (TV shows, Anime, Doramas)
- MusicOrganizer (Music tracks)
- BookOrganizer (Books and Comics)
- CalibreManager (Calibre integration)

Usage:
    from src.organizers import (
        BaseOrganizer, MovieOrganizer, TVOrganizer,
        MusicOrganizer, BookOrganizer, CalibreManager
    )
"""
import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple
import logging
import re
import json

from src.core import (
    OrganizadorInterface, OrganizationResult, MediaType,
    FileMetadata, ValidationResult
)
from src.config import Config


# ============================================================================
# SECTION 1: BASE ORGANIZER
# ============================================================================

class BaseOrganizer(OrganizadorInterface):
    """
    Base class for all media organizers.
    
    Provides common functionality:
    - Title/author sanitization
    - File hash calculation
    - Conflict resolution
    - Validation helpers
    - File organization with hardlinks
    """
    
    def __init__(
        self,
        config: Config,
        database,
        conflict_handler,
        logger: logging.Logger,
        dry_run: bool = False
    ):
        self.config = config
        self.database = database
        self.conflict_handler = conflict_handler
        self.logger = logger
        self.dry_run = dry_run
    
    def sanitize_title(self, text: str) -> str:
        """Sanitize text for filenames"""
        if not text:
            return "Untitled"
        
        # Remove invalid characters
        for char in '<>:"/\\|?*':
            text = text.replace(char, '')
        
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.rstrip('. ')
        text = re.sub(r'_+$', '', text)
        
        if not text:
            return "Untitled"
        
        if len(text) > 100:
            text = text[:97] + "..."
        
        return text
    
    def sanitize_author(self, text: str) -> str:
        """Sanitize author name"""
        if not text or text == 'Unknown Author':
            return 'Unknown Author'
        
        for char in '<>:"/\\|?*':
            text = text.replace(char, '')
        
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'([A-Z])\.([A-Z])\.', r'\1. \2.', text)
        
        if len(text) > 50:
            text = text[:47] + "..."
        
        return text
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate file hash"""
        import hashlib
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    async def organizar_file(
        self,
        source_path: Path,
        dest_path: Path,
        metadata: Dict[str, Any]
    ) -> OrganizationResult:
        """Organize single file with conflict resolution"""
        try:
            # Check database
            if self.database.is_file_organized(str(source_path)):
                return OrganizationResult(
                    success=True,
                    organized_path=dest_path,
                    skipped=True,
                    metadata=metadata
                )

            # Create destination
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Resolve conflicts
            final_dest_path, action = self.conflict_handler.resolve(
                source_path, dest_path, self.dry_run
            )

            if final_dest_path is None:
                return OrganizationResult(
                    success=False,
                    error_message="Conflict resolution failed"
                )

            # Create hardlink
            if not self.dry_run:
                dest_path.hardlink_to(source_path)
                
                # Register in Link Registry for deletion management
                try:
                    from src.deletion import LinkRegistry
                    link_registry = LinkRegistry(self.config.link_registry_path)
                    link_registry.register_link(
                        source_path=source_path,
                        dest_path=final_dest_path,
                        metadata=metadata
                    )
                    link_registry.close()
                except Exception as e:
                    self.logger.warning(f"Could not register link: {e}")
            else:
                self.logger.info(f"[DRY RUN] Would link: {source_path.name}")

            # Update database
            file_hash = self.calculate_file_hash(source_path)
            self.database.adicionar_midia(
                file_hash=file_hash,
                original_path=str(source_path),
                organized_path=str(final_dest_path),
                metadata=metadata
            )

            # Move subtitles for video files
            if source_path.suffix.lower() in ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']:
                try:
                    from src.utils import move_subtitles_with_video
                    moved = move_subtitles_with_video(
                        source_path, final_dest_path, self.dry_run
                    )
                    if moved:
                        self.logger.info(f"Moved {len(moved)} subtitle(s)")
                except Exception as e:
                    self.logger.warning(f"Could not move subtitles: {e}")

            return OrganizationResult(
                success=True,
                organized_path=final_dest_path,
                metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"Error organizing {source_path.name}: {e}")
            return OrganizationResult(
                success=False,
                error_message=str(e)
            )
    
    def validate_file(self, file_path: Path) -> bool:
        """Basic file validation"""
        if not file_path.exists() or not file_path.is_file():
            return False
        try:
            if file_path.stat().st_size == 0:
                return False
        except OSError:
            return False
        return True
    
    def is_incomplete_file(self, file_path: Path) -> bool:
        """Check if file is incomplete"""
        incomplete_exts = {'.part', '.tmp', '.!qB', '.crdownload', '.download'}
        return file_path.suffix.lower() in incomplete_exts
    
    def is_junk_file(self, file_path: Path) -> bool:
        """Check if file is junk/promotional"""
        filename = file_path.name.upper()
        
        junk_names = {'BLUDV.MP4', '1XBET.MP4', 'SAMPLE.MP4', 'TRAILER.MP4'}
        if filename in junk_names:
            return True
        
        junk_patterns = ['BLUDV', '1XBET', 'SAMPLE', 'WWW.', '_PROMO_']
        for pattern in junk_patterns:
            if pattern in filename:
                try:
                    if file_path.stat().st_size < 100 * 1024 * 1024:
                        return True
                except:
                    pass
        
        return False
    
    # Abstract methods
    async def organizar(self, file_path: Path) -> OrganizationResult:
        raise NotImplementedError
    
    def pode_processar(self, file_path: Path) -> bool:
        raise NotImplementedError
    
    def obter_tipo_midia(self) -> MediaType:
        raise NotImplementedError


# ============================================================================
# SECTION 2: MOVIE ORGANIZER
# ============================================================================

class MovieOrganizer(BaseOrganizer):
    """
    Movie organizer with automatic TMDB ID detection.
    
    Folder format: movies/Movie Title (Year) [tmdbid-ID]/
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.library_path = self.config.library_path_movies
        from src.persistence import UnorganizedDatabase
        self.unorganized_db = UnorganizedDatabase(Path("data/unorganized.json"))
    
    async def organizar(self, file_path: Path) -> OrganizationResult:
        """Organize movie file"""
        from src.integrations import get_tmdb_id_for_movie
        from src.utils import normalize_movie_filename
        
        if self.database.is_file_organized(str(file_path)):
            return OrganizationResult(success=True, skipped=True)
        
        # Extract title/year
        title, year = normalize_movie_filename(file_path.name)
        
        if not title:
            self.unorganized_db.add_unorganized(
                str(file_path),
                f"Could not extract title: {file_path.name}"
            )
            return OrganizationResult(
                success=False,
                error_message="Could not extract title",
                skipped=True
            )
        
        # Get TMDB ID
        tmdb_id = await get_tmdb_id_for_movie(
            title=title, year=year, logger=self.logger
        )
        
        if not tmdb_id:
            self.unorganized_db.add_unorganized(
                str(file_path),
                f"TMDB lookup failed for: {title}"
            )
            return OrganizationResult(
                success=False,
                error_message=f"TMDB lookup failed: {title}",
                skipped=True
            )
        
        # Build metadata
        metadata = {
            'title': title,
            'year': year or 0,
            'tmdb_id': tmdb_id,
            'media_type': 'movie'
        }
        
        # Get destination
        dest_path = self.get_destination_path(file_path, metadata)
        
        # Organize
        return await self.organizar_file(file_path, dest_path, metadata)
    
    def pode_processar(self, file_path: Path) -> bool:
        return True
    
    def obter_tipo_midia(self) -> MediaType:
        return MediaType.MOVIE
    
    def get_destination_path(self, file_path: Path, metadata: Dict) -> Path:
        """Build destination: movies/Title (Year) [tmdbid-ID]/Title (Year).ext"""
        title = self.sanitize_title(metadata['title'])
        year = metadata.get('year')
        tmdb_id = metadata.get('tmdb_id')
        
        if tmdb_id:
            folder_name = f"{title} ({year}) [tmdbid-{tmdb_id}]"
        else:
            folder_name = f"{title} ({year}) [ERROR-MISSING-TMDB-ID]"
        
        file_name = f"{title} ({year}){file_path.suffix}" if year else f"{title}{file_path.suffix}"
        
        return self.library_path / folder_name / file_name


# ============================================================================
# SECTION 3: TV ORGANIZER (TV, ANIME, DORAMA)
# ============================================================================

class TVOrganizer(BaseOrganizer):
    """
    TV show organizer supporting TV, Anime, and Dorama.
    
    Folder format: library/Series (Year) [tmdbid-ID]/Season XX/Series SXXEXX.ext
    """
    
    def __init__(self, *args, media_subtype: str = 'tv', **kwargs):
        super().__init__(*args, **kwargs)
        self.media_subtype = media_subtype
        
        if media_subtype == 'anime':
            self.library_path = self.config.library_path_animes
        elif media_subtype == 'dorama':
            self.library_path = self.config.library_path_doramas
        else:
            self.library_path = self.config.library_path_tv
        
        from src.persistence import UnorganizedDatabase
        self.unorganized_db = UnorganizedDatabase(Path("data/unorganized.json"))
    
    async def organizar(self, file_path: Path) -> OrganizationResult:
        """Organize TV episode"""
        from src.integrations import get_tmdb_id_for_tv_show, extract_year_from_directory
        from src.utils import normalize_tv_filename
        
        if self.database.is_file_organized(str(file_path)):
            return OrganizationResult(success=True, skipped=True)
        
        # Extract metadata
        title, season, episode, _ = normalize_tv_filename(file_path.name)
        year = extract_year_from_directory(file_path.parent)
        
        if not title or not season or not episode:
            self.unorganized_db.add_unorganized(
                str(file_path),
                f"Could not extract series/episode info: {file_path.name}"
            )
            return OrganizationResult(
                success=False,
                error_message="Could not extract series/episode info",
                skipped=True
            )
        
        # Get TMDB ID
        tmdb_id = await get_tmdb_id_for_tv_show(
            title=title, year=year, logger=self.logger
        )
        
        if not tmdb_id:
            self.unorganized_db.add_unorganized(
                str(file_path),
                f"TMDB lookup failed for: {title}"
            )
            return OrganizationResult(
                success=False,
                error_message=f"TMDB lookup failed: {title}",
                skipped=True
            )
        
        # Build metadata
        metadata = {
            'series_title': title,
            'year': year or 0,
            'season': season,
            'episode': episode,
            'tmdb_id': tmdb_id,
            'media_type': 'tv',
            'media_subtype': self.media_subtype
        }
        
        # Get destination
        dest_path = self.get_destination_path(file_path, metadata)
        
        # Organize
        result = await self.organizar_file(file_path, dest_path, metadata)
        
        # Remove from unorganized if successful
        if result.success and not result.skipped:
            try:
                self.unorganized_db.remove_unorganized(str(file_path))
            except Exception as e:
                self.logger.warning(f"Could not remove from unorganized: {e}")
        
        return result
    
    def pode_processar(self, file_path: Path) -> bool:
        return True
    
    def obter_tipo_midia(self) -> MediaType:
        if self.media_subtype == 'anime':
            return MediaType.ANIME
        elif self.media_subtype == 'dorama':
            return MediaType.DORAMA
        return MediaType.TV_SHOW
    
    def get_destination_path(self, file_path: Path, metadata: Dict) -> Path:
        """Build destination: library/Series (Year) [tmdbid-ID]/Season XX/Series SXXEXX.ext"""
        series_title = self.sanitize_title(metadata['series_title'])
        year = metadata.get('year')
        season = metadata['season']
        episode = metadata['episode']
        tmdb_id = metadata.get('tmdb_id')
        
        if tmdb_id:
            series_folder = f"{series_title} ({year}) [tmdbid-{tmdb_id}]"
        else:
            series_folder = f"{series_title} ({year}) [ERROR-MISSING-TMDB-ID]"
        
        season_folder = f"Season {season:02d}"
        episode_name = f"{series_title} S{season:02d}E{episode:02d}{file_path.suffix}"
        
        return self.library_path / series_folder / season_folder / episode_name


# ============================================================================
# SECTION 4: MUSIC ORGANIZER
# ============================================================================

class MusicOrganizer(BaseOrganizer):
    """
    Music organizer with enhanced metadata extraction.
    
    Folder format: music/Artist/Album/## - Track.ext
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.library_path = self.config.library_path_music
        self.music_automation_db_path = self.config.music_automation_db_path
        self.music_automation_data = self._load_music_automation_db()
    
    def _load_music_automation_db(self) -> Optional[Dict]:
        """Load Music Automation database"""
        if not self.music_automation_db_path or not self.music_automation_db_path.exists():
            return None
        
        try:
            with open(self.music_automation_db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not load Music Automation DB: {e}")
            return None
    
    def _get_metadata_from_automation(self, file_path: Path) -> Optional[Dict]:
        """Get metadata from Music Automation DB"""
        if not self.music_automation_data:
            return None
        
        tracks = self.music_automation_data.get('tracks', {})
        if not isinstance(tracks, dict):
            return None
        
        input_path_str = str(file_path.resolve())
        input_filename = file_path.name.lower()
        
        # Strategy 1: Exact path match
        for spotify_id, track in tracks.items():
            if not isinstance(track, dict):
                continue
            
            track_file_path = track.get('file_path', '')
            if not track_file_path:
                continue
            
            if str(Path(track_file_path).resolve()) == input_path_str:
                return self._extract_track_metadata(track, spotify_id)
        
        # Strategy 2: Filename match
        for spotify_id, track in tracks.items():
            if not isinstance(track, dict):
                continue
            
            track_file_path = track.get('file_path', '')
            if not track_file_path:
                continue
            
            track_filename = Path(track_file_path).name.lower()
            if track_filename == input_filename:
                return self._extract_track_metadata(track, spotify_id)
        
        return None
    
    def _extract_track_metadata(self, track: Dict, spotify_id: str) -> Dict:
        """Extract metadata from track"""
        metadata = {
            'spotify_id': spotify_id,
            'title': track.get('title'),
            'artist': track.get('artist'),
            'album': track.get('album'),
            'track_number': track.get('track_number'),
            'source': 'music_automation'
        }
        
        release_year = track.get('release_year')
        if release_year:
            try:
                metadata['year'] = int(release_year)
            except (ValueError, TypeError):
                pass
        
        genres = track.get('genres', [])
        if isinstance(genres, list) and genres:
            metadata['genre'] = genres[0].title() if genres else None
        
        return metadata
    
    def _extract_metadata_from_filename(self, file_path: Path) -> Dict:
        """Extract metadata from filename"""
        filename = file_path.stem
        metadata = {}
        
        # Try "Artist - Track" pattern
        if ' - ' in filename:
            parts = filename.split(' - ', 1)
            if len(parts) == 2:
                metadata['artist'] = parts[0].strip()
                metadata['track_name'] = parts[1].strip()
        else:
            metadata['track_name'] = filename
            metadata['artist'] = 'Unknown Artist'
        
        return metadata
    
    def _read_audio_tags(self, file_path: Path) -> Dict:
        """Read ID3 tags from audio file"""
        try:
            from mutagen.id3 import ID3
            from mutagen.mp3 import MP3
            from mutagen.flac import FLAC
            
            ext = file_path.suffix.lower()
            
            if ext == '.mp3':
                audio = MP3(file_path)
                if audio.tags:
                    return {
                        'title': str(audio.tags.get('TIT2', '')),
                        'artist': str(audio.tags.get('TPE1', '')),
                        'album': str(audio.tags.get('TALB', '')),
                        'genre': str(audio.tags.get('TCON', '')),
                        'track_number': str(audio.tags.get('TRCK', ''))
                    }
            elif ext == '.flac':
                audio = FLAC(file_path)
                return {
                    'title': audio.get('title', [''])[0],
                    'artist': audio.get('artist', [''])[0],
                    'album': audio.get('album', [''])[0],
                    'genre': audio.get('genre', [''])[0],
                    'track_number': audio.get('tracknumber', [''])[0]
                }
        except Exception as e:
            self.logger.debug(f"Could not read tags: {e}")
        
        return {}
    
    def _determine_final_metadata(
        self,
        filename_metadata: Dict,
        id3_metadata: Dict,
        file_path: Path,
        automation_metadata: Optional[Dict] = None
    ) -> Dict:
        """Determine final metadata from all sources"""
        # Priority: Automation > ID3 > Filename
        final = {
            'artist': 'Unknown Artist',
            'track_name': file_path.stem,
            'album': 'Unknown Album',
            'genre': 'Unknown',
            'track_number': None,
            'year': None
        }
        
        # Start with filename
        final.update(filename_metadata)
        
        # Override with ID3
        for key, value in id3_metadata.items():
            if value:
                final[key] = value
        
        # Override with automation (highest priority)
        if automation_metadata:
            for key, value in automation_metadata.items():
                if value:
                    final[key] = value
        
        return final
    
    def _update_audio_tags(self, file_path: Path, metadata: Dict) -> bool:
        """Update ID3 tags in file"""
        try:
            from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TRCK
            
            ext = file_path.suffix.lower()
            if ext != '.mp3':
                return False
            
            audio = ID3(file_path)
            audio['TIT2'] = TIT2(encoding=3, text=metadata.get('track_name', ''))
            audio['TPE1'] = TPE1(encoding=3, text=metadata.get('artist', ''))
            audio['TALB'] = TALB(encoding=3, text=metadata.get('album', ''))
            audio['TCON'] = TCON(encoding=3, text=metadata.get('genre', ''))
            
            if metadata.get('track_number'):
                audio['TRCK'] = TRCK(encoding=3, text=str(metadata['track_number']))
            
            audio.save()
            return True
        except Exception as e:
            self.logger.error(f"Failed to update tags: {e}")
            return False
    
    async def organizar(self, file_path: Path) -> OrganizationResult:
        """Organize music file"""
        if self.database.is_file_organized(str(file_path)):
            return OrganizationResult(success=True, skipped=True)
        
        # Extract metadata from all sources
        automation_meta = self._get_metadata_from_automation(file_path)
        filename_meta = self._extract_metadata_from_filename(file_path)
        id3_meta = self._read_audio_tags(file_path)
        
        # Determine final metadata
        final_meta = self._determine_final_metadata(
            filename_meta, id3_meta, file_path, automation_meta
        )
        
        # Update tags
        self._update_audio_tags(file_path, final_meta)
        
        # Get destination
        dest_path = self.get_destination_path(file_path, final_meta)
        
        # Organize
        return await self.organizar_file(file_path, dest_path, final_meta)
    
    def pode_processar(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in {'.mp3', '.flac', '.m4a', '.ogg', '.opus'}
    
    def obter_tipo_midia(self) -> MediaType:
        return MediaType.MUSIC
    
    def get_destination_path(self, file_path: Path, metadata: Dict) -> Path:
        """Build destination: music/Artist/Album/## - Track.ext"""
        artist = self.sanitize_author(metadata.get('artist', 'Unknown'))
        album = self.sanitize_title(metadata.get('album', 'Unknown Album'))
        track_name = self.sanitize_title(metadata.get('track_name', file_path.stem))
        track_number = metadata.get('track_number')
        
        # Build filename
        if track_number and 1 <= int(track_number) <= 99:
            file_name = f"{int(track_number):02d} - {track_name}{file_path.suffix}"
        else:
            file_name = f"{track_name}{file_path.suffix}"
        
        return self.library_path / artist / album / file_name


# ============================================================================
# SECTION 5: BOOK ORGANIZER (BOOKS, COMICS)
# ============================================================================

class BookOrganizer(BaseOrganizer):
    """
    Book organizer supporting books and comics.
    
    Books: books/Author/Title (Year)/
    Comics: comics/Series (Year)/Issue.cbz
    """
    
    def __init__(self, *args, book_type: str = 'book', **kwargs):
        super().__init__(*args, **kwargs)
        self.book_type = book_type
        
        if book_type == 'comic':
            self.library_path = self.config.library_path_comics
        else:
            self.library_path = self.config.library_path_books
        
        # Calibre integration
        if hasattr(self.config, 'calibre_enabled') and self.config.calibre_enabled:
            self.calibre_manager = CalibreManager(self.config.calibre_library_path)
        else:
            self.calibre_manager = None
    
    def _detect_book_type(self, file_path: Path) -> str:
        """Detect book type from extension"""
        ext = file_path.suffix.lower()
        if ext in {'.cbz', '.cbr', '.cb7', '.cbt'}:
            return 'comic'
        return 'book'
    
    def _extract_book_metadata(self, file_path: Path, book_type: str) -> Dict:
        """Extract book metadata"""
        from src.utils import normalize_title
        
        filename = file_path.stem
        metadata = {
            'title': normalize_title(filename),
            'author': 'Unknown Author',
            'year': None,
            'media_subtype': book_type
        }
        
        # Try to extract year
        import re
        year_match = re.search(r'\((\d{4})\)', filename)
        if year_match:
            metadata['year'] = int(year_match.group(1))
        
        # Try "Author - Title" pattern
        if ' - ' in filename:
            parts = filename.split(' - ', 1)
            if len(parts) == 2:
                metadata['author'] = parts[0].strip()
                metadata['title'] = normalize_title(parts[1].strip())
        
        return metadata
    
    def _extract_comic_metadata(self, file_path: Path) -> Dict:
        """Extract comic metadata"""
        from src.utils import normalize_comic_filename
        
        series, issue, publisher, year = normalize_comic_filename(file_path.stem)
        
        return {
            'title': series or 'Unknown Series',
            'issue_number': issue,
            'publisher': publisher or 'Unknown',
            'year': year,
            'media_subtype': 'comic'
        }
    
    def get_book_destination_path(self, file_path: Path, metadata: Dict) -> Path:
        """Build destination: books/Author/Title (Year)/"""
        author = self.sanitize_author(metadata.get('author', 'Unknown'))
        title = self.sanitize_title(metadata.get('title', 'Untitled'))
        year = metadata.get('year')
        
        if year:
            folder_name = f"{title} ({year})"
        else:
            folder_name = title
        
        return self.library_path / author / folder_name / file_path.name
    
    def get_comic_destination_path(self, file_path: Path, metadata: Dict) -> Path:
        """Build destination: comics/Series (Year)/"""
        series = self.sanitize_title(metadata.get('title', 'Unknown'))
        year = metadata.get('year')
        issue = metadata.get('issue_number')
        
        if year:
            folder_name = f"{series} ({year})"
        else:
            folder_name = series
        
        if issue:
            file_name = f"{series} #{issue}{file_path.suffix}"
        else:
            file_name = file_path.name
        
        return self.library_path / folder_name / file_name
    
    async def organizar(self, file_path: Path) -> OrganizationResult:
        """Organize book file"""
        if self.database.is_file_organized(str(file_path)):
            return OrganizationResult(success=True, skipped=True)
        
        # Detect type
        detected_type = self._detect_book_type(file_path)
        final_type = self.book_type if self.book_type != 'book' else detected_type
        
        # Extract metadata
        if final_type == 'comic':
            metadata = self._extract_comic_metadata(file_path)
            dest_path = self.get_comic_destination_path(file_path, metadata)
        else:
            metadata = self._extract_book_metadata(file_path, final_type)
            dest_path = self.get_book_destination_path(file_path, metadata)
        
        # Organize
        return await self.organizar_file(file_path, dest_path, metadata)
    
    def pode_processar(self, file_path: Path) -> bool:
        book_exts = {'.epub', '.pdf', '.mobi', '.azw', '.azw3'}
        comic_exts = {'.cbz', '.cbr', '.cb7', '.cbt'}
        
        if self.book_type == 'comic':
            return file_path.suffix.lower() in comic_exts
        return file_path.suffix.lower() in book_exts
    
    def obter_tipo_midia(self) -> MediaType:
        if self.book_type == 'comic':
            return MediaType.COMIC
        return MediaType.BOOK


# ============================================================================
# SECTION 6: CALIBRE MANAGER (INTERNAL CLASS)
# ============================================================================

class CalibreManager:
    """
    Calibre integration for metadata management.
    
    Provides:
    - Metadata extraction
    - Metadata update
    - PDF to EPUB conversion
    - Library management
    """
    
    def __init__(self, library_path: Optional[Path] = None):
        self.library_path = library_path
        self.enabled = library_path is not None and library_path.exists()
    
    def add_book(self, book_path: Path, metadata: Dict) -> bool:
        """Add book to Calibre library"""
        if not self.enabled:
            return False
        
        try:
            cmd = ['calibredb', 'add', str(book_path)]
            if self.library_path:
                cmd.extend(['--library-path', str(self.library_path)])
            
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            return result.returncode == 0
        except Exception as e:
            return False
    
    def update_metadata(self, book_path: Path, metadata: Dict) -> bool:
        """Update embedded metadata in book file"""
        if not self.enabled:
            return False
        
        try:
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix=book_path.suffix, delete=False) as tmp:
                temp_path = Path(tmp.name)
            
            cmd = ['ebook-convert', str(book_path), str(temp_path)]
            
            if metadata.get('title'):
                cmd.extend(['--title', metadata['title']])
            if metadata.get('author'):
                cmd.extend(['--authors', metadata['author']])
            
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            
            if result.returncode == 0:
                shutil.move(str(temp_path), str(book_path))
                return True
            else:
                temp_path.unlink()
                return False
        except Exception as e:
            return False
    
    def search_books(self, query: str) -> List[Dict]:
        """Search books in Calibre library"""
        if not self.enabled:
            return []
        
        try:
            cmd = ['calibredb', 'list', '--search', query, '--as-json']
            if self.library_path:
                cmd.extend(['--library-path', str(self.library_path)])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get('books', [])
            return []
        except Exception:
            return []
