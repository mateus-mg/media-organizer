"""
Movie organizer
Organizes movies into standard media server structure
"""

from pathlib import Path
from typing import Dict, Optional
from .base import BaseOrganizer, OrganizationResult
from ..metadata.parsers import parse_movie_name, is_spam_file
from ..metadata.tmdb_client import TMDBClient


class MovieOrganizer(BaseOrganizer):
    """Organizes movie files"""

    def __init__(self, *args, tmdb_client: Optional[TMDBClient] = None, **kwargs):
        """
        Initialize movie organizer

        Args:
            tmdb_client: TMDB client instance (optional)
        """
        super().__init__(*args, **kwargs)
        self.tmdb_client = tmdb_client
        self.library_path = self.config.library_path_movies

    async def organize(self, file_path: Path) -> OrganizationResult:
        """
        Organize a movie file

        Args:
            file_path: Path to movie file

        Returns:
            OrganizationResult
        """
        # Skip spam/advertisement files
        if is_spam_file(file_path.name):
            result = OrganizationResult()
            result.success = False
            result.file_path = str(file_path)
            result.error_message = "Spam/advertisement file - skipped"
            result.skipped = True
            return result

        # Parse filename
        media_info = parse_movie_name(file_path.name)

        # Skip files without a valid title
        if not media_info.title or len(media_info.title.strip()) == 0:
            result = OrganizationResult()
            result.success = False
            result.file_path = str(file_path)
            result.error_message = "No valid title found in filename"
            result.skipped = True
            return result

        # Try to get TMDB data (ID and English title)
        tmdb_id = None
        english_title = None

        if self.tmdb_client and media_info.title:
            tmdb_data = await self._get_tmdb_data(media_info.title, media_info.year)

            if tmdb_data:
                tmdb_id = tmdb_data.get('id')
                english_title = tmdb_data.get(
                    'title')  # English title from TMDB

                # If year was missing, get it from TMDB
                if not media_info.year and tmdb_data.get('year'):
                    media_info.year = int(tmdb_data['year'])

        # Use English title if available, otherwise use parsed title
        final_title = english_title if english_title else media_info.title

        # Build metadata
        metadata = {
            'media_type': 'movie',
            'title': final_title,  # English title
            'english_title': english_title,
            'parsed_title': media_info.title,
            'year': media_info.year,
            'tmdb_id': tmdb_id,
            'quality': media_info.quality,
            'codec': media_info.codec,
            'is_3d': media_info.is_3d
        }

        # Get destination path
        dest_path = self.get_destination_path(file_path, metadata)

        # Organize file
        return await self.organize_file(file_path, dest_path, metadata)

    def get_destination_path(self, file_path: Path, metadata: Dict) -> Path:
        """
        Get destination path for movie
        Format: movies/Movie Name (Year) [tmdbid-ID]/Movie Name (Year).ext

        Args:
            file_path: Source file path
            metadata: Movie metadata

        Returns:
            Destination path
        """
        title = self.sanitize_title(metadata['title'])
        year = metadata.get('year')
        tmdb_id = metadata.get('tmdb_id')

        # Create folder name
        folder_name = self.format_folder_name(title, year, tmdb_id)

        # Create file name
        if year:
            file_name = f"{title} ({year})"
        else:
            file_name = title

        # Add quality suffix if multiple versions
        if metadata.get('quality'):
            quality = metadata['quality']
            file_name = f"{file_name} - {quality}"

        file_name += file_path.suffix

        return self.library_path / folder_name / file_name

    async def _get_tmdb_data(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """
        Get TMDB data (ID and English title) for movie

        Args:
            title: Movie title (can be in any language)
            year: Release year (optional)

        Returns:
            Dict with TMDB data or None
        """
        if not self.tmdb_client:
            return None

        try:
            # Search TMDB (now returns dict with id and original_title)
            return self.tmdb_client.search_movie(title, year)
        except Exception as e:
            self.logger.warning(f"TMDB search failed for '{title}': {e}")
            return None
