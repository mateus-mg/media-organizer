"""
qBittorrent Processor

Processes completed torrents from qBittorrent.
Designed for scheduled execution (cron/systemd timer), not continuous monitoring.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass

try:
    from qbittorrentapi import Client as QBittorrentClient
    from qbittorrentapi.exceptions import LoginFailed, APIConnectionError
    QBITTORRENT_AVAILABLE = True
except ImportError:
    QBITTORRENT_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(
        "qbittorrent-api not installed, torrent processing disabled")

logger = logging.getLogger(__name__)


@dataclass
class TorrentInfo:
    """Information about a completed torrent"""
    hash: str
    name: str
    state: str
    progress: float
    save_path: Path
    files: List[Path]


class TorrentProcessor:
    """
    qBittorrent torrent processor.

    Queries qBittorrent for completed torrents and returns their file paths.
    Designed for one-time execution, not continuous monitoring.

    Features:
    - Simple connection and query
    - Returns completed torrent files
    - Path mapping support (container -> host)
    - Stateless (no tracking between executions)
    """

    # States indicating torrent is complete and ready for organization
    COMPLETE_STATES = {'stalledUP', 'uploading',
                       'pausedUP', 'queuedUP', 'checkingUP', 'forcedUP'}

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        min_progress: float = 1.0,
        path_mapping: Optional[Dict[str, str]] = None,
        ignored_categories: Optional[list] = None
    ):
        """
        Initialize torrent processor.

        Args:
            host: qBittorrent Web UI URL (e.g., http://localhost:8080)
            username: qBittorrent username
            password: qBittorrent password
            min_progress: Minimum progress to consider complete (0.0-1.0)
            path_mapping: Dict mapping container paths to host paths
            ignored_categories: List of category names to ignore (case-insensitive)
        """
        if not QBITTORRENT_AVAILABLE:
            raise ImportError(
                "qbittorrent-api not installed. "
                "Install with: pip install qbittorrent-api"
            )

        self.host = host
        self.username = username
        self.password = password
        self.min_progress = min_progress
        self.path_mapping = path_mapping or {}
        self.ignored_categories = [c.lower()
                                   for c in (ignored_categories or [])]

        self.client: Optional[QBittorrentClient] = None

        logger.debug(f"TorrentProcessor initialized for {host}")
        if self.path_mapping:
            logger.debug(
                f"Path mapping configured: {len(self.path_mapping)} mappings")
        if self.ignored_categories:
            logger.debug(
                f"Ignoring categories: {', '.join(self.ignored_categories)}")

    def connect(self) -> bool:
        """
        Connect to qBittorrent Web API.

        Returns:
            True if connected successfully
        """
        try:
            self.client = QBittorrentClient(
                host=self.host,
                username=self.username,
                password=self.password
            )

            # Test connection
            version = self.client.app.version
            logger.info(f"✓ Connected to qBittorrent {version}")
            return True

        except LoginFailed:
            logger.error("✗ qBittorrent login failed (invalid credentials)")
            return False

        except APIConnectionError as e:
            logger.error(f"✗ Cannot connect to qBittorrent: {e}")
            return False

        except Exception as e:
            logger.error(f"✗ Unexpected error connecting to qBittorrent: {e}")
            return False

    def disconnect(self):
        """Disconnect from qBittorrent"""
        if self.client:
            try:
                self.client.auth_log_out()
            except:
                pass
            self.client = None

    def get_completed_torrents(self) -> List[TorrentInfo]:
        """
        Get all completed torrents with their files.

        Returns:
            List of completed torrent information
        """
        if not self.connect():
            logger.error("Cannot connect to qBittorrent")
            return []

        try:
            torrents = self.client.torrents_info()
            completed_torrents = []
            ignored_count = 0

            for torrent in torrents:
                # Skip torrents in ignored categories
                category = torrent.category.lower() if torrent.category else ""
                if category and category in self.ignored_categories:
                    ignored_count += 1
                    logger.debug(
                        f"Skipping torrent in '{torrent.category}' category: {torrent.name}")
                    continue

                state = torrent.state
                progress = torrent.progress

                # Check if torrent is complete
                is_complete = (
                    state in self.COMPLETE_STATES and
                    progress >= self.min_progress
                )

                if is_complete:
                    # Get file paths
                    file_paths = self._get_torrent_files(torrent.hash)

                    if file_paths:
                        completed_torrents.append(TorrentInfo(
                            hash=torrent.hash,
                            name=torrent.name,
                            state=state,
                            progress=progress,
                            save_path=Path(torrent.save_path),
                            files=file_paths
                        ))

                        logger.debug(
                            f"Found completed torrent: {torrent.name} "
                            f"({len(file_paths)} files)"
                        )

            if ignored_count > 0:
                logger.info(
                    f"✓ Ignored {ignored_count} torrent(s) in ignored categories")

            logger.info(
                f"✓ Found {len(completed_torrents)} completed torrent(s)")
            return completed_torrents

        except Exception as e:
            logger.error(f"Error getting completed torrents: {e}")
            return []

        finally:
            self.disconnect()

    def _get_torrent_files(self, torrent_hash: str) -> List[Path]:
        """
        Get list of file paths for a torrent.

        Args:
            torrent_hash: Torrent hash

        Returns:
            List of file paths in the torrent
        """
        try:
            # Get torrent properties
            torrent = self.client.torrents_info(torrent_hashes=torrent_hash)[0]
            save_path = Path(torrent.save_path)

            # Get files in torrent
            files = self.client.torrents_files(torrent_hash=torrent_hash)

            file_paths = []
            for file_info in files:
                # Build full path
                file_path = save_path / file_info.name

                # Apply path mapping (container -> host)
                mapped_path = self._map_path(file_path)

                if mapped_path.exists():
                    file_paths.append(mapped_path)
                else:
                    # Try to find file with different extension (e.g., converted PDF->EPUB)
                    found = False
                    if mapped_path.suffix == '.pdf':
                        epub_path = mapped_path.with_suffix('.epub')
                        if epub_path.exists():
                            file_paths.append(epub_path)
                            found = True
                            logger.debug(f"Found converted file: {epub_path}")

                    if not found:
                        logger.debug(
                            f"Torrent file path not found on host: {mapped_path}")

            return file_paths

        except Exception as e:
            logger.error(f"Error getting torrent files: {e}")
            return []

    def _map_path(self, container_path: Path) -> Path:
        """
        Map container path to host path.

        Args:
            container_path: Path as returned by qBittorrent (container)

        Returns:
            Mapped host path
        """
        if not self.path_mapping:
            return container_path

        path_str = str(container_path)

        # Try each mapping (longest first to handle nested paths)
        for container_prefix, host_prefix in sorted(
            self.path_mapping.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            if path_str.startswith(container_prefix):
                # Replace container prefix with host prefix
                mapped_str = path_str.replace(container_prefix, host_prefix, 1)
                logger.debug(f"Path mapped: {container_path} -> {mapped_str}")
                return Path(mapped_str)

        # No mapping found, return original
        return container_path
