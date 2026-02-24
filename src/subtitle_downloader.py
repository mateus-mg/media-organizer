#!/usr/bin/env python3
"""
OpenSubtitles API Client and Subtitle Downloader

Media Organization System - Subtitle Automation Module

API Documentation: https://api.opensubtitles.com/docs
"""

import os
import time
import hashlib
import struct
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from src.subtitle_config import SubtitleConfig


# ============================================================================
# OPENSubtitles API CLIENT
# ============================================================================

class OpenSubtitlesClient:
    """
    Client for OpenSubtitles.com REST API v2
    
    Handles:
    - Authentication
    - Subtitle search
    - File download
    - Rate limit tracking
    """
    
    def __init__(self, config: SubtitleConfig, logger=None):
        """
        Initialize OpenSubtitles client
        
        Args:
            config: SubtitleConfig instance
            logger: Logger instance
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        self.api_key = config.api_key
        self.base_url = config.api_url
        self.username = config.api_username
        
        # Session management
        self.session = requests.Session()
        self.token = None
        self.token_expires = None
        
        # User agent (required by API)
        self.user_agent = "MediaOrganizer v2.0"
        
        # Rate limiting
        self.downloads_today = 0
        self.last_request_time = None
        self.rate_limit_remaining = 20
        self.rate_limit_reset = None
        
        # Statistics
        self.total_requests = 0
        self.successful_downloads = 0
        self.failed_downloads = 0
    
    def _get_headers(self, include_token: bool = True) -> Dict[str, str]:
        """Get request headers"""
        headers = {
            'Api-Key': self.api_key,
            'User-Agent': self.user_agent,
            'Content-Type': 'application/json',
        }
        
        if include_token and self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        return headers
    
    def _check_rate_limit(self) -> bool:
        """Check if we can make more requests"""
        if self.downloads_today >= self.config.download_limit:
            self.logger.warning(
                f"Daily download limit reached: {self.downloads_today}/{self.config.download_limit}"
            )
            return False
        
        return True
    
    def _apply_rate_limit_delay(self):
        """Apply delay between API calls"""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.config.api_delay:
                time.sleep(self.config.api_delay - elapsed)
        self.last_request_time = time.time()
    
    def login(self) -> bool:
        """
        Authenticate with OpenSubtitles API
        
        Returns:
            True if authentication successful
        """
        try:
            url = f"{self.base_url}/login"
            payload = {
                'username': self.username,
                'password': self.config.api_password
            }
            
            self._apply_rate_limit_delay()
            response = self.session.post(
                url,
                headers=self._get_headers(include_token=False),
                json=payload,
                timeout=30
            )
            
            self.total_requests += 1
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')
                
                # Token expires in 1 day (per API docs)
                self.token_expires = datetime.now() + timedelta(days=1)
                
                self.logger.info("✓ OpenSubtitles authentication successful")
                return True
            else:
                self.logger.error(
                    f"✗ OpenSubtitles authentication failed: {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"✗ OpenSubtitles login error: {e}")
            return False
    
    def logout(self):
        """Logout and clear token"""
        if self.token:
            try:
                url = f"{self.base_url}/logout"
                self._apply_rate_limit_delay()
                self.session.post(
                    url,
                    headers=self._get_headers(),
                    timeout=10
                )
            except:
                pass
            finally:
                self.token = None
                self.token_expires = None
    
    def search_subtitles(
        self,
        tmdb_id: int,
        media_type: str = 'movie',
        languages: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for subtitles
        
        Args:
            tmdb_id: TMDB ID of the media
            media_type: 'movie' or 'tv'
            languages: List of language codes (e.g., ['pt', 'en'])
        
        Returns:
            List of subtitle info dictionaries
        """
        if not self._check_rate_limit():
            return []
        
        if languages is None:
            languages = self.config.preferred_languages
        
        try:
            url = f"{self.base_url}/subtitles"
            params = {
                'tmdb_id': tmdb_id,
                'type': media_type,
                'languages': ','.join(languages),
                'order_by': 'download_count',
                'sort': 'desc',
                'limit': 10  # Get top 10 results
            }
            
            self._apply_rate_limit_delay()
            response = self.session.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )
            
            self.total_requests += 1
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('data', [])
                
                self.logger.info(
                    f"Found {len(results)} subtitle(s) for TMDB {tmdb_id}"
                )
                
                return results
            else:
                self.logger.error(
                    f"Search failed: {response.status_code}"
                )
                return []
                
        except Exception as e:
            self.logger.error(f"Search error: {e}")
            return []
    
    def download_subtitle(
        self,
        file_id: int,
        save_path: Path
    ) -> Optional[Path]:
        """
        Download subtitle file
        
        Args:
            file_id: File ID from search results
            save_path: Path to save subtitle file
        
        Returns:
            Path to downloaded file, or None if failed
        """
        if not self._check_rate_limit():
            return None
        
        try:
            url = f"{self.base_url}/download"
            payload = {'file_id': file_id}
            
            self._apply_rate_limit_delay()
            response = self.session.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30,
                stream=True  # Stream download
            )
            
            self.total_requests += 1
            
            if response.status_code == 200:
                # Ensure directory exists
                save_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write file
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                self.downloads_today += 1
                self.successful_downloads += 1
                self.rate_limit_remaining -= 1
                
                self.logger.info(
                    f"✓ Downloaded subtitle: {save_path.name} "
                    f"({self.downloads_today}/{self.config.download_limit} today)"
                )
                
                return save_path
            else:
                self.failed_downloads += 1
                self.logger.error(
                    f"✗ Download failed: {response.status_code}"
                )
                return None
                
        except Exception as e:
            self.failed_downloads += 1
            self.logger.error(f"Download error: {e}")
            return None
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get current user information"""
        try:
            url = f"{self.base_url}/user"
            
            self._apply_rate_limit_delay()
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=30
            )
            
            self.total_requests += 1
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception as e:
            self.logger.error(f"Get user info error: {e}")
            return None
    
    def get_remaining_downloads(self) -> int:
        """
        Get remaining downloads for today
        
        Returns:
            Number of remaining downloads
        """
        return self.config.download_limit - self.downloads_today
    
    def reset_daily_counter(self):
        """Reset daily download counter"""
        self.downloads_today = 0
        self.rate_limit_remaining = self.config.download_limit
        self.logger.info("Reset daily download counter")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            'Downloads today': f"{self.downloads_today}/{self.config.download_limit}",
            'Remaining': self.get_remaining_downloads(),
            'Total requests': self.total_requests,
            'Successful': self.successful_downloads,
            'Failed': self.failed_downloads,
            'Token valid': bool(self.token and self.token_expires),
        }


# ============================================================================
# SUBTITLE DOWNLOADER
# ============================================================================

class SubtitleDownloader:
    """
    Main subtitle downloader logic
    
    Coordinates:
    - Reading organized media database
    - Finding files without subtitles
    - Searching and downloading subtitles
    - Updating database
    """
    
    def __init__(self, config: SubtitleConfig, database, logger=None):
        """
        Initialize subtitle downloader
        
        Args:
            config: SubtitleConfig instance
            database: OrganizationDatabase instance
            logger: Logger instance
        """
        self.config = config
        self.database = database
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize API client
        self.client = OpenSubtitlesClient(config, self.logger)
        
        # Statistics
        self.files_processed = 0
        self.subtitles_downloaded = 0
        self.subtitles_skipped = 0
    
    def ensure_authenticated(self) -> bool:
        """Ensure client is authenticated"""
        if not self.client.token:
            return self.client.login()
        
        # Check if token is expired
        if self.client.token_expires and datetime.now() > self.client.token_expires:
            self.logger.info("Token expired, re-authenticating...")
            self.client.token = None
            return self.client.login()
        
        return True
    
    def get_files_without_subtitles(
        self,
        media_type: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of files without subtitles
        
        Args:
            media_type: Filter by media type (movie, tv, etc.)
        
        Returns:
            List of file info dictionaries
        """
        files = []
        
        # Get all media from database
        all_media = self.database.get_all_media()
        
        for media in all_media:
            # Filter by media type if specified
            if media_type:
                media_media_type = media.get('metadata', {}).get('media_type', '')
                if media_media_type != media_type:
                    continue
            
            # Check if already has subtitles
            subtitles = media.get('subtitles', [])
            if subtitles and self.config.skip_if_exists:
                # Check if has subtitle in preferred language
                for sub in subtitles:
                    lang = sub.get('language', '').lower()
                    if lang in self.config.preferred_languages:
                        self.subtitles_skipped += 1
                        continue
            
            files.append(media)
        
        return files
    
    def extract_video_hash(self, video_path: Path) -> str:
        """
        Calculate OpenSubtitles hash for video file
        
        OpenSubtitles uses a custom hash based on file size and checksums
        of first and last 64KB of the file.
        
        Args:
            video_path: Path to video file
        
        Returns:
            Hash string
        """
        try:
            file_size = video_path.stat().st_size
            hash_value = file_size
            
            if file_size < 65536 * 2:
                # File too small
                return ""
            
            # Read first 64KB
            with open(video_path, 'rb') as f:
                for _ in range(65536 // 8):
                    buffer = f.read(8)
                    (long_value,) = struct.unpack('<Q', buffer)
                    hash_value += long_value
                    hash_value &= 0xFFFFFFFFFFFFFFFF
            
            # Read last 64KB
            with open(video_path, 'rb') as f:
                f.seek(max(0, file_size - 65536), 0)
                for _ in range(65536 // 8):
                    buffer = f.read(8)
                    (long_value,) = struct.unpack('<Q', buffer)
                    hash_value += long_value
                    hash_value &= 0xFFFFFFFFFFFFFFFF
            
            return format(hash_value, '016x')
            
        except Exception as e:
            self.logger.error(f"Error calculating hash: {e}")
            return ""
    
    def download_for_file(
        self,
        file_info: Dict[str, Any],
        organized_path: Path
    ) -> bool:
        """
        Download subtitle for single file
        
        Args:
            file_info: File info from database
            organized_path: Path to organized video file
        
        Returns:
            True if subtitle downloaded successfully
        """
        if not organized_path.exists():
            self.logger.warning(f"Video file not found: {organized_path}")
            return False
        
        # Ensure authenticated
        if not self.ensure_authenticated():
            self.logger.error("Not authenticated with OpenSubtitles")
            return False
        
        # Check rate limit
        if not self.client._check_rate_limit():
            self.logger.warning("Daily download limit reached")
            return False
        
        # Get metadata
        metadata = file_info.get('metadata', {})
        tmdb_id = metadata.get('tmdb_id')
        media_type = metadata.get('media_type', 'movie')
        title = metadata.get('title', 'Unknown')
        
        if not tmdb_id:
            self.logger.warning(f"No TMDB ID for: {title}")
            return False
        
        # Map media type
        api_media_type = 'movie' if media_type in ['movie'] else 'tv'
        
        self.logger.info(
            f"Searching subtitles for: {title} (TMDB: {tmdb_id})"
        )
        
        # Search for subtitles
        results = self.client.search_subtitles(
            tmdb_id=tmdb_id,
            media_type=api_media_type,
            languages=self.config.preferred_languages
        )
        
        if not results:
            self.logger.warning(f"No subtitles found for: {title}")
            return False
        
        # Download best match
        for result in results:
            # Get files from result
            files = result.get('files', [])
            if not files:
                continue
            
            file_info_api = files[0]
            file_id = file_info_api.get('file_id')
            language = file_info_api.get('language', 'en')
            
            if not file_id:
                continue
            
            # Check if we already have this language
            existing_subs = file_info.get('subtitles', [])
            has_language = any(
                sub.get('language', '').lower() == language.lower()
                for sub in existing_subs
            )
            
            if has_language and self.config.skip_if_exists:
                continue
            
            # Build save path
            save_name = f"{organized_path.stem}.{language}.srt"
            save_path = organized_path.parent / save_name
            
            # Download
            downloaded_path = self.client.download_subtitle(
                file_id=file_id,
                save_path=save_path
            )
            
            if downloaded_path:
                # Update database
                self.database.add_subtitle(
                    file_hash=file_info.get('file_hash'),
                    subtitle_path=str(downloaded_path),
                    language=language
                )
                
                self.subtitles_downloaded += 1
                self.files_processed += 1
                
                return True
        
        self.logger.warning(f"Could not download subtitle for: {title}")
        return False
    
    def process_all_media(self) -> Dict[str, int]:
        """
        Process all organized media looking for subtitles
        
        Returns:
            Statistics dictionary
        """
        self.logger.info("Starting subtitle download process")
        
        # Process by priority
        for media_type in self.config.priority_order:
            remaining = self.client.get_remaining_downloads()
            if remaining <= 0:
                self.logger.info("No downloads remaining for today")
                break
            
            self.logger.info(
                f"Processing {media_type}s "
                f"({remaining} downloads remaining)"
            )
            
            files = self.get_files_without_subtitles(media_type=media_type)
            
            for file_info in files:
                if remaining <= 0:
                    break
                
                organized_path = Path(file_info.get('organized_path', ''))
                self.download_for_file(file_info, organized_path)
                
                remaining = self.client.get_remaining_downloads()
        
        # Return statistics
        return {
            'Files processed': self.files_processed,
            'Subtitles downloaded': self.subtitles_downloaded,
            'Subtitles skipped': self.subtitles_skipped,
            'Downloads remaining': self.client.get_remaining_downloads(),
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get downloader statistics"""
        stats = self.client.get_statistics()
        stats['Files processed'] = self.files_processed
        stats['Subtitles downloaded'] = self.subtitles_downloaded
        stats['Subtitles skipped'] = self.subtitles_skipped
        return stats
