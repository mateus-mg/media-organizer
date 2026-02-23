"""
Integrations module for Media Organization System

Consolidated module containing:
- TMDB Client (Movie/TV show metadata API)
- File Completion Validator (Validate download completion)
- QBittorrent Client (Torrent monitoring)

Usage:
    from src.integrations import (
        TMDBClient, get_tmdb_id_for_movie, get_tmdb_id_for_tv_show,
        FileCompletionValidator, QBittorrentClient
    )
"""
import asyncio
import aiohttp
import os
import time
import fcntl
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import re
from urllib.parse import quote_plus

from src.core import ValidatorInterface, ValidationResult


# ============================================================================
# SECTION 1: TMDB CLIENT
# ============================================================================

@dataclass
class TMDBResult:
    """Result of TMDB API operation"""
    success: bool
    data: Dict[str, Any]
    source: str
    error: Optional[str] = None


class TMDBClient:
    """
    TMDB API client for movie and TV show metadata.
    
    Used only for obtaining IDs, not full metadata.
    Supports async context manager.
    """
    
    def __init__(self, api_key: Optional[str] = None, logger: Optional[logging.Logger] = None):
        self.api_key = api_key or os.getenv("TMDB_API_KEY", "")
        self.logger = logger or logging.getLogger(__name__)
        self.base_url = "https://api.themoviedb.org/3"
        self.session = None
        
        if not self.api_key:
            self.logger.warning("TMDB API key not configured")
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "MediaOrganizer/1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_movie(self, title: str, year: Optional[int] = None) -> TMDBResult:
        """
        Search for movie by title and optional year
        
        Args:
            title: Movie title
            year: Release year (optional)
            
        Returns:
            TMDBResult with search results
        """
        if not self.api_key:
            return TMDBResult(success=False, data={}, source="TMDB", error="No API key")
        
        try:
            clean_title = self._clean_title(title)
            encoded = quote_plus(clean_title)
            url = f"{self.base_url}/search/movie?api_key={self.api_key}&query={encoded}"
            
            if year:
                url += f"&year={year}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('results'):
                        results = sorted(
                            data['results'],
                            key=lambda x: x.get('popularity', 0),
                            reverse=True
                        )
                        
                        # Match by year if provided
                        if year:
                            for result in results:
                                result_year = self._extract_year(result.get('release_date', ''))
                                if result_year and abs(result_year - year) <= 1:
                                    return TMDBResult(success=True, data=result, source="TMDB")
                        
                        return TMDBResult(success=True, data=results[0], source="TMDB")
                    
                    return TMDBResult(success=False, data={}, source="TMDB", error="No results")
                else:
                    return TMDBResult(
                        success=False, data={}, source="TMDB",
                        error=f"HTTP {response.status}"
                    )
        except Exception as e:
            self.logger.error(f"TMDB search error: {e}")
            return TMDBResult(success=False, data={}, source="TMDB", error=str(e))
    
    async def search_tv_show(self, title: str, year: Optional[int] = None) -> TMDBResult:
        """
        Search for TV show by title and optional year
        
        Args:
            title: TV show title
            year: First air date year (optional)
            
        Returns:
            TMDBResult with search results
        """
        if not self.api_key:
            return TMDBResult(success=False, data={}, source="TMDB", error="No API key")
        
        try:
            clean_title = self._clean_title(title)
            encoded = quote_plus(clean_title)
            url = f"{self.base_url}/search/tv?api_key={self.api_key}&query={encoded}"
            
            if year:
                url += f"&first_air_date_year={year}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('results'):
                        results = sorted(
                            data['results'],
                            key=lambda x: x.get('popularity', 0),
                            reverse=True
                        )
                        
                        # Match by year if provided
                        if year:
                            for result in results:
                                result_year = self._extract_year(result.get('first_air_date', ''))
                                if result_year and abs(result_year - year) <= 1:
                                    return TMDBResult(success=True, data=result, source="TMDB")
                        
                        return TMDBResult(success=True, data=results[0], source="TMDB")
                    
                    return TMDBResult(success=False, data={}, source="TMDB", error="No results")
                else:
                    return TMDBResult(
                        success=False, data={}, source="TMDB",
                        error=f"HTTP {response.status}"
                    )
        except Exception as e:
            self.logger.error(f"TMDB TV search error: {e}")
            return TMDBResult(success=False, data={}, source="TMDB", error=str(e))
    
    def _clean_title(self, title: str) -> str:
        """Clean title for TMDB search"""
        cleaned = re.sub(r'\b\d{3,4}[ip]\b', '', title)  # Remove 1080p, etc
        cleaned = re.sub(r'\b(BR.?RIP|DVDRIP|WEB.?RIP)\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'[._\-]+', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    def _extract_year(self, date_str: str) -> Optional[int]:
        """Extract year from date string"""
        if not date_str:
            return None
        match = re.search(r'^(\d{4})-', date_str)
        return int(match.group(1)) if match else None


async def get_tmdb_id_for_movie(title: str, year: Optional[int] = None, logger=None) -> Optional[int]:
    """
    Get TMDB ID for movie
    
    Args:
        title: Movie title
        year: Release year (optional)
        logger: Logger instance
        
    Returns:
        TMDB ID or None
    """
    if not os.getenv("TMDB_API_KEY"):
        return None
    
    async with TMDBClient(logger=logger) as client:
        result = await client.search_movie(title, year)
        if result.success and result.data.get('id'):
            return result.data['id']
    return None


async def get_tmdb_id_for_tv_show(title: str, year: Optional[int] = None, logger=None) -> Optional[int]:
    """
    Get TMDB ID for TV show
    
    Args:
        title: TV show title
        year: First air year (optional)
        logger: Logger instance
        
    Returns:
        TMDB ID or None
    """
    if not os.getenv("TMDB_API_KEY"):
        return None
    
    async with TMDBClient(logger=logger) as client:
        result = await client.search_tv_show(title, year)
        if result.success and result.data.get('id'):
            return result.data['id']
    return None


def extract_year_from_directory(directory: Path) -> Optional[int]:
    """
    Extract year from directory name
    
    Args:
        directory: Path to directory
        
    Returns:
        Year or None
    """
    match = re.search(r'\((\d{4})\)', directory.name)
    if match:
        return int(match.group(1))
    return None


# ============================================================================
# SECTION 2: FILE COMPLETION VALIDATOR
# ============================================================================

class FileCompletionValidator(ValidatorInterface):
    """
    Validate files are complete (not downloading).
    
    Methods:
    - Check temp extensions
    - Check file locks
    - Check size stability
    - Check minimum age
    """
    
    def __init__(
        self,
        min_file_age_seconds: int = 300,
        size_check_duration: int = 5,
        logger: Optional[logging.Logger] = None
    ):
        self.min_file_age = min_file_age_seconds
        self.size_check_duration = size_check_duration
        self.logger = logger or logging.getLogger(__name__)
        
        self.temp_extensions = {'.part', '.tmp', '.!qB', '.crdownload', '.download', '.aria2'}
    
    def validar_arquivos(self, arquivos: List[Path]) -> List[Path]:
        """
        Validate multiple files
        
        Args:
            arquivos: List of file paths
            
        Returns:
            List of complete files
        """
        self.logger.info(f"Validating {len(arquivos)} files...")
        
        valid = []
        for arquivo in arquivos:
            if self._is_complete(arquivo):
                valid.append(arquivo)
        
        self.logger.info(f"{len(valid)}/{len(arquivos)} files complete")
        return valid
    
    async def validate(self, file_path: Path) -> ValidationResult:
        """Validate single file (interface method)"""
        if self._is_complete(file_path):
            return ValidationResult(is_valid=True)
        return ValidationResult(
            is_valid=False,
            error_message="File is incomplete"
        )
    
    def can_validate(self, file_path: Path) -> bool:
        return file_path.is_file()
    
    def _is_complete(self, file_path: Path) -> bool:
        """Check if file is complete"""
        if not file_path.exists():
            return False
        
        if self._has_temp_extension(file_path):
            return False
        
        if self._is_locked(file_path):
            return False
        
        if not self._is_size_stable(file_path):
            return False
        
        if not self._is_old_enough(file_path):
            return False
        
        return True
    
    def _has_temp_extension(self, file_path: Path) -> bool:
        """Check for temp extension"""
        return file_path.suffix.lower() in self.temp_extensions
    
    def _is_locked(self, file_path: Path) -> bool:
        """Check if file is locked by another process"""
        try:
            with open(file_path, 'r+b') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return False
        except (IOError, OSError):
            return True
    
    def _is_size_stable(self, file_path: Path) -> bool:
        """Check if file size is stable"""
        try:
            initial = file_path.stat().st_size
            time.sleep(self.size_check_duration)
            current = file_path.stat().st_size
            return initial == current
        except:
            return False
    
    def _is_old_enough(self, file_path: Path) -> bool:
        """Check if file has minimum age"""
        try:
            mtime = file_path.stat().st_mtime
            age = time.time() - mtime
            return age >= self.min_file_age
        except:
            return False
    
    def esta_conectado(self) -> bool:
        return True
    
    async def desconectar(self) -> None:
        pass


# ============================================================================
# SECTION 3: QBITTORRENT CLIENT
# ============================================================================

class QBittorrentClient:
    """
    QBittorrent API client for torrent monitoring.
    
    Provides:
    - Authentication
    - Torrent list
    - File paths from torrents
    - Completion status
    """
    
    def __init__(self, config, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.host = config.qbittorrent_host
        self.username = config.qbittorrent_username
        self.password = config.qbittorrent_password
        self.session = None
        self.cookie = None
    
    async def connect(self) -> bool:
        """Connect and authenticate"""
        try:
            self.session = aiohttp.ClientSession()
            
            login_url = f"{self.host}/api/v2/auth/login"
            data = {'username': self.username, 'password': self.password}
            
            async with self.session.post(login_url, data=data) as response:
                if response.status == 200:
                    self.cookie = response.cookies.get('SID')
                    return self.cookie is not None
            return False
        except Exception as e:
            self.logger.error(f"QBittorrent connect error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect"""
        if self.session:
            await self.session.close()
    
    async def get_torrents(self) -> List[Dict]:
        """Get all torrents"""
        if not self.cookie:
            return []
        
        try:
            url = f"{self.host}/api/v2/torrents/info"
            async with self.session.get(url, cookies={'SID': self.cookie}) as response:
                if response.status == 200:
                    return await response.json()
            return []
        except Exception as e:
            self.logger.error(f"Get torrents error: {e}")
            return []
    
    async def get_torrent_files(self, torrent_hash: str) -> List[Dict]:
        """Get files in torrent"""
        if not self.cookie:
            return []
        
        try:
            url = f"{self.host}/api/v2/torrents/files?hash={torrent_hash}"
            async with self.session.get(url, cookies={'SID': self.cookie}) as response:
                if response.status == 200:
                    return await response.json()
            return []
        except Exception as e:
            self.logger.error(f"Get torrent files error: {e}")
            return []
    
    def is_complete(self, torrent: Dict) -> bool:
        """Check if torrent is complete"""
        state = torrent.get('state', '')
        progress = torrent.get('progress', 0)
        
        complete_states = {'seeding', 'pausedUP', 'uploading'}
        return state in complete_states and progress >= 1.0


class QBittorrentValidator:
    """
    Validate files against QBittorrent completion status.
    
    Only processes files from completed torrents.
    """
    
    def __init__(self, config, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.client = QBittorrentClient(config, logger)
    
    async def validate_files(self, files: List[Path]) -> List[Path]:
        """Validate files against QBittorrent"""
        if not self.config.qbittorrent_enabled:
            return files
        
        try:
            await self.client.connect()
            torrents = await self.client.get_torrents()
            
            # Build map of complete torrent paths
            complete_paths = set()
            for torrent in torrents:
                if self.client.is_complete(torrent):
                    files = await self.client.get_torrent_files(torrent['hash'])
                    for file_info in files:
                        complete_paths.add(file_info['name'])
            
            # Filter files
            valid = []
            for file_path in files:
                if file_path.name in complete_paths:
                    valid.append(file_path)
                else:
                    self.logger.debug(f"Skipping incomplete: {file_path.name}")
            
            return valid
        except Exception as e:
            self.logger.error(f"QBittorrent validation error: {e}")
            return files
        finally:
            await self.client.disconnect()
