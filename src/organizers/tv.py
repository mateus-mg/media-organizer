"""
TV show organizer (includes anime and doramas)
Organizes TV episodes into standard media server structure
"""

from pathlib import Path
from typing import Dict, Optional
from .base import BaseOrganizer, OrganizationResult
from ..metadata.parsers import parse_tv_episode, parse_anime_name, is_spam_file
from ..metadata.tmdb_client import TMDBClient


class TVOrganizer(BaseOrganizer):
    """Organizes TV show files"""

    def __init__(
        self,
        *args,
        tmdb_client: Optional[TMDBClient] = None,
        media_subtype: str = 'series',
        **kwargs
    ):
        """
        Initialize TV organizer

        Args:
            tmdb_client: TMDB client instance (optional)
            media_subtype: Type of TV media (series, anime, dorama)
        """
        super().__init__(*args, **kwargs)
        self.tmdb_client = tmdb_client
        self.media_subtype = media_subtype

        # Cache for TMDB searches (avoid repeated API calls for same series)
        self._tmdb_cache = {}

        # Select library path based on subtype
        if media_subtype == 'anime':
            self.library_path = self.config.library_path_animes
        elif media_subtype == 'dorama':
            self.library_path = self.config.library_path_doramas
        else:
            self.library_path = self.config.library_path_tv

    async def organize(self, file_path: Path) -> OrganizationResult:
        """
        Organize a TV episode file

        Args:
            file_path: Path to episode file

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
        if self.media_subtype == 'anime':
            media_info = parse_anime_name(file_path.name)
        else:
            media_info = parse_tv_episode(file_path.name)

        if not media_info.season or not media_info.episode:
            result = OrganizationResult()
            result.error_message = "Could not parse season/episode from filename"
            return result

        # Skip files without a valid title
        if not media_info.title or len(media_info.title.strip()) == 0:
            result = OrganizationResult()
            result.success = False
            result.file_path = str(file_path)
            result.error_message = "No valid title found in filename"
            result.skipped = True
            return result

        # Try to get TMDB data (ID and English name)
        tmdb_id = None
        english_name = None
        year = None

        if self.tmdb_client and media_info.title:
            self.logger.info(f"Searching TMDB for: {media_info.title}")
            tmdb_data = await self._get_tmdb_data(media_info.title)

            if tmdb_data:
                tmdb_id = tmdb_data.get('id')
                english_name = tmdb_data.get('name')  # English title from TMDB
                year = tmdb_data.get('year')
                if year:
                    year = int(year)
                self.logger.info(
                    f"Found TMDB: ID={tmdb_id}, english={english_name}, year={year}")
            else:
                self.logger.warning(
                    f"No TMDB data found for: {media_info.title}")

        # Use English title if available, otherwise use parsed title
        final_title = english_name if english_name else media_info.title

        # Build metadata
        # Use media_subtype as media_type for proper statistics counting
        # (anime, dorama, or series for TV shows)
        metadata = {
            'media_type': self.media_subtype if self.media_subtype in ['anime', 'dorama'] else 'series',
            'media_subtype': self.media_subtype,
            'series_title': final_title,  # English title
            'english_name': english_name,
            'parsed_title': media_info.title,
            'year': year,
            'season': media_info.season,
            'episode': media_info.episode,
            'episode_title': media_info.episode_title,
            'tmdb_id': tmdb_id
        }

        # Get destination path
        dest_path = self.get_destination_path(file_path, metadata)

        # Organize file
        return await self.organize_file(file_path, dest_path, metadata)

    def get_destination_path(self, file_path: Path, metadata: Dict) -> Path:
        """
        Get destination path for TV episode
        Format: tv/Series Name (Year)/Season 01/Series Name S01E01.ext

        Args:
            file_path: Source file path
            metadata: Episode metadata

        Returns:
            Destination path
        """
        title = self.sanitize_title(metadata['series_title'])
        year = metadata.get('year')
        tmdb_id = metadata.get('tmdb_id')
        season = metadata['season']
        episode = metadata['episode']

        # Create series folder name (MUST include year for proper identification)
        series_folder = self.format_folder_name(title, year, tmdb_id)

        # If no year available, add current year as fallback
        if not year:
            from datetime import datetime
            series_folder = self.format_folder_name(
                title, datetime.now().year, tmdb_id)
            self.logger.warning(
                f"No year found for {title}, using current year")

        # Create season folder name
        season_folder = f"Season {season:02d}"

        # Create episode filename (NO hyphen before S01E01)
        episode_name = f"{title} S{season:02d}E{episode:02d}{file_path.suffix}"

        return self.library_path / series_folder / season_folder / episode_name

    async def _get_tmdb_data(self, title: str) -> Optional[Dict]:
        """
        Get TMDB data (ID and original name) for TV show (with caching)

        Args:
            title: TV show title (can be in any language)

        Returns:
            Dict with TMDB data or None
        """
        if not self.tmdb_client:
            return None

        # Check cache first
        if title in self._tmdb_cache:
            self.logger.debug(f"Using cached TMDB data for: {title}")
            return self._tmdb_cache[title]

        try:
            # Search TMDB (now returns dict with id and original_name)
            tmdb_data = self.tmdb_client.search_tv(title)

            # Handle old cache format (int) vs new format (dict)
            if isinstance(tmdb_data, int):
                # Old cache format: just ID, convert to dict
                tmdb_data = {'id': tmdb_data,
                             'original_name': None, 'name': None, 'year': None}

            # Cache the result (even if None)
            self._tmdb_cache[title] = tmdb_data
            return tmdb_data
        except Exception as e:
            self.logger.error(f"Error fetching TMDB data: {e}")
            # Cache None to avoid retrying on every episode
            self._tmdb_cache[title] = None
            return None
