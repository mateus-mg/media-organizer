"""
Music organizer
Organizes music files into Artist/Album structure
Integrates with Music Automation database
"""

from pathlib import Path
from typing import Dict, Optional
import json
from .base import BaseOrganizer, OrganizationResult
from ..metadata.parsers import parse_music_file


class MusicOrganizer(BaseOrganizer):
    """Organizes music files"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.library_path = self.config.library_path_music
        self.music_automation_db_path = self.config.music_automation_db_path
        self.music_automation_data = self._load_music_automation_db()

    def _load_music_automation_db(self) -> Optional[Dict]:
        """Load Music Automation database if available"""
        if not self.music_automation_db_path or not self.music_automation_db_path.exists():
            return None

        try:
            with open(self.music_automation_db_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not load Music Automation DB: {e}")
            return None

    async def organize(self, file_path: Path) -> OrganizationResult:
        """Organize a music file"""
        from ..metadata.parsers import normalize_artist_name, detect_various_artists

        # Parse filename and directory structure
        music_info = parse_music_file(file_path)

        # Try to get metadata from mutagen (ID3 tags)
        metadata = self._read_audio_tags(file_path)

        # Prioritize filename parsing over potentially incorrect ID3 tags
        # Use ID3 tags only if they look reasonable
        artist = self._get_best_artist(music_info, metadata)
        album = self._get_best_album(music_info, metadata)
        track_name = self._get_best_track_name(music_info, metadata, file_path)
        # Only use track_number from filename parsing, ignore ID3 (often wrong from YouTube)
        track_number = music_info.get('track_number')

        # Normalize artist name and extract featuring artists
        main_artist, featured_artists = normalize_artist_name(artist)

        # Detect if this is a Various Artists compilation
        is_compilation = detect_various_artists(artist, album)
        if is_compilation:
            album_artist = 'Various Artists'
        else:
            album_artist = main_artist

        final_metadata = {
            'media_type': 'music',
            'artist': main_artist,
            'album_artist': album_artist,
            'album': album,
            'track_name': track_name,
            'track_number': track_number,
            'year': metadata.get('year'),
            'featured_artists': featured_artists,
            'is_compilation': is_compilation
        }

        # Get destination path
        dest_path = self.get_destination_path(file_path, final_metadata)

        # Organize file
        result = await self.organize_file(file_path, dest_path, final_metadata)

        # Update ID3 tags with clean metadata
        if result and result.organized_path:
            self._update_id3_tags(Path(result.organized_path), final_metadata)

        return result

    def get_destination_path(self, file_path: Path, metadata: Dict) -> Path:
        """
        Get destination path for music file
        Format: musics/Artist Name/Album Name/## - Track Name.ext
        """
        artist = self._sanitize_artist_name(metadata['artist'])
        album = self.sanitize_title(metadata['album'])
        track_name = self.sanitize_title(metadata['track_name'])
        track_number = metadata.get('track_number')

        # Create filename
        if track_number and track_number > 0 and track_number < 100:
            file_name = f"{track_number:02d} - {track_name}{file_path.suffix}"
        else:
            file_name = f"{track_name}{file_path.suffix}"

        return self.library_path / artist / album / file_name

    def _get_best_artist(self, filename_info: Dict, id3_info: Dict) -> str:
        """Get best artist name, preferring filename over potentially incorrect ID3"""
        # ALWAYS prefer filename artist over ID3 tags
        # (ID3 tags often have wrong info from YouTube downloads)
        if filename_info.get('artist'):
            return filename_info['artist']

        # Only use ID3 if no artist in filename
        if id3_info.get('artist'):
            return id3_info['artist']

        return 'Unknown Artist'

    def _get_best_album(self, filename_info: Dict, id3_info: Dict) -> str:
        """Get best album name"""
        # Prefer ID3 album over filename (albums usually not in filename)
        if id3_info.get('album'):
            return id3_info['album']

        if filename_info.get('album'):
            return filename_info['album']

        # Use "Singles" as default album
        return 'Singles'

    def _get_best_track_name(self, filename_info: Dict, id3_info: Dict, file_path: Path) -> str:
        """Get best track name"""
        # Prefer filename over ID3 (ID3 often has extra info like "(Official Video)")
        track_name = None

        if filename_info.get('track_name'):
            track_name = filename_info['track_name']
        elif id3_info.get('title'):
            track_name = id3_info['title']
        else:
            track_name = file_path.stem

        # Clean up the track name
        return self._clean_track_name(track_name)

    def _clean_track_name(self, track_name: str) -> str:
        """
        Clean track name by removing common suffixes and unwanted text.
        Examples:
        - "Song (Official Video)" -> "Song"
        - "Song [Official Audio]" -> "Song"
        - "Song Legendado" -> "Song"
        """
        import re

        # List of patterns to remove (case-insensitive)
        # Note: More specific patterns first to avoid partial matches
        patterns_to_remove = [
            r'\s*\(?\s*official\s+music\s+video\s*\)?',
            r'\s*\(?\s*official\s+video\s*\)?',
            r'\s*\(?\s*official\s+audio\s*\)?',
            r'\s*\(?\s*lyric\s+video\s*\)?',
            r'\s*\(?\s*lyrics?\s*\)?',
            r'\s*\(?\s*audio\s*\)?',
            r'\s*\(?\s*video\s*\)?',
            r'\s*\(?\s*official\s*\)?',
            r'\s+legendado\s*$',  # Only at the end to avoid matching "Leg" in "Legend"
            r'\s*\(?\s*hd\s*\)?',
            r'\s*\(?\s*hq\s*\)?',
            r'\s*\(?\s*4k\s*\)?',
            r'\s*\[\s*official\s+music\s+video\s*\]',
            r'\s*\[\s*official\s+video\s*\]',
            r'\s*\[\s*official\s+audio\s*\]',
            r'\s*\[\s*lyric\s+video\s*\]',
            r'\s*\[\s*lyrics?\s*\]',
            r'\s*\[\s*audio\s*\]',
            r'\s*\[\s*video\s*\]',
            r'\s*\[\s*official\s*\]',
            r'\s*\[\s*legendado\s*\]',
            r'\s*\[\s*hd\s*\]',
            r'\s*\[\s*hq\s*\]',
            r'\s*\[\s*4k\s*\]',
        ]

        # Apply each pattern
        cleaned = track_name
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Remove empty brackets or parentheses
        cleaned = re.sub(r'\s*\[\s*\]', '', cleaned)
        cleaned = re.sub(r'\s*\(\s*\)', '', cleaned)

        # Remove extra whitespace and trailing/leading spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Remove trailing dashes or commas
        cleaned = re.sub(r'[\s\-,]+$', '', cleaned)

        # Return original if cleaning resulted in empty string
        return cleaned if cleaned else track_name

    def _sanitize_artist_name(self, artist: str) -> str:
        """Sanitize artist name, adding spaces to camelCase if needed"""
        import re

        # First apply standard sanitization
        artist = self.sanitize_title(artist)

        # Add spaces to camelCase (e.g., "ImagineDragons" -> "Imagine Dragons")
        # Only if there are no spaces already
        if ' ' not in artist:
            # Insert space before capital letters that follow lowercase letters
            artist = re.sub(r'([a-z])([A-Z])', r'\1 \2', artist)

        return artist

    def _read_audio_tags(self, file_path: Path) -> Dict:
        """Read audio metadata tags using mutagen"""
        try:
            from mutagen import File

            audio = File(file_path, easy=True)
            if not audio:
                return {}

            metadata = {}

            # Extract common tags
            if 'artist' in audio:
                metadata['artist'] = audio['artist'][0]
            if 'album' in audio:
                metadata['album'] = audio['album'][0]
            if 'title' in audio:
                metadata['title'] = audio['title'][0]
            if 'tracknumber' in audio:
                try:
                    # Handle "1/12" format
                    track_str = str(audio['tracknumber'][0]).split('/')[0]
                    track_num = int(track_str)
                    # Ignore unrealistic track numbers (likely from YouTube downloads)
                    if 1 <= track_num <= 999:
                        metadata['track_number'] = track_num
                except (ValueError, IndexError):
                    pass
            if 'date' in audio:
                try:
                    year_str = str(audio['date'][0])[:4]
                    metadata['year'] = int(year_str)
                except (ValueError, IndexError):
                    pass

            return metadata

        except Exception as e:
            self.logger.debug(f"Could not read audio tags: {e}")
            return {}

    def _update_id3_tags(self, file_path: Path, metadata: Dict) -> bool:
        """
        Update ID3 tags with cleaned metadata.
        This ensures media servers read clean metadata from files.
        """
        try:
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, TIT2, TPE1, TPE2, TALB, TRCK, TDRC, TCMP

            audio = MP3(str(file_path), ID3=ID3)

            # Add ID3 tag if it doesn't exist
            if audio.tags is None:
                audio.add_tags()

            # Update tags with cleaned metadata
            audio.tags['TIT2'] = TIT2(
                encoding=3, text=metadata['track_name'])  # Title
            audio.tags['TPE1'] = TPE1(
                encoding=3, text=metadata['artist'])      # Artist
            audio.tags['TPE2'] = TPE2(
                encoding=3, text=metadata['album_artist'])  # Album Artist
            audio.tags['TALB'] = TALB(
                encoding=3, text=metadata['album'])       # Album

            # Track number
            if metadata.get('track_number'):
                audio.tags['TRCK'] = TRCK(
                    encoding=3, text=str(metadata['track_number']))

            # Year
            if metadata.get('year'):
                audio.tags['TDRC'] = TDRC(
                    encoding=3, text=str(metadata['year']))

            # Compilation flag (for Various Artists albums)
            if metadata.get('is_compilation'):
                audio.tags['TCMP'] = TCMP(encoding=3, text='1')

            # Featured artists in comment (for reference)
            if metadata.get('featured_artists'):
                featured_str = ', '.join(metadata['featured_artists'])
                # Note: Could add COMM frame here if needed
                self.logger.debug(f"Featured artists: {featured_str}")

            audio.save()
            self.logger.debug(f"Updated ID3 tags for: {file_path.name}")
            return True

        except Exception as e:
            self.logger.warning(
                f"Failed to update ID3 tags for {file_path.name}: {e}")
            return False
