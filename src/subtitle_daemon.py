#!/usr/bin/env python3
"""
Subtitle Downloader Daemon

Runs every 24 hours to download missing subtitles from OpenSubtitles.

Media Organization System - Subtitle Automation Module

Usage:
    python -m src.subtitle_daemon
"""

import asyncio
import time
import signal
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.subtitle_config import SubtitleConfig, get_config
from src.subtitle_downloader import SubtitleDownloader, OpenSubtitlesClient
from src.persistence import OrganizationDatabase
from src.log_config import (
    get_logger,
    set_console_log_level,
    log_info,
    log_success,
    log_error,
    log_warning,
    log_stats,
)
from src.log_formatter import LogSection


class SubtitleDaemon:
    """
    Daemon for automatic subtitle downloads.
    
    Runs every 24 hours (configurable) to:
    1. Scan organized media for files without subtitles
    2. Download subtitles from OpenSubtitles (respecting rate limits)
    3. Update database with subtitle information
    """
    
    def __init__(self, config: Optional[SubtitleConfig] = None):
        """
        Initialize subtitle daemon
        
        Args:
            config: SubtitleConfig instance (optional, will create if None)
        """
        self.config = config or get_config()
        self.running = False
        self.shutdown_requested = False
        
        # Initialize logger (uses centralized log file: logs/organizer.log)
        self.logger = get_logger(
            name="SubtitleDaemon",
            log_file=str(self.config.log_file)
        )
        
        # Set console log level
        set_console_log_level(logging.WARNING)
        
        # Initialize database
        self.database = OrganizationDatabase(
            db_path=self.config.database_path,
            backup_enabled=self.config.database_backup_enabled if hasattr(self.config, 'database_backup_enabled') else True,
            backup_keep_days=self.config.database_backup_keep_days if hasattr(self.config, 'database_backup_keep_days') else 7
        )
        
        # Initialize downloader
        self.downloader = SubtitleDownloader(
            config=self.config,
            database=self.database,
            logger=self.logger
        )
        
        # Statistics
        self.cycles_completed = 0
        self.total_downloads = 0
        self.start_time = None
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        log_info(self.logger, "Shutdown signal received")
        self.shutdown_requested = True
    
    def log_startup(self):
        """Log daemon startup information"""
        lines = LogSection.major_header(
            "SUBTITLE DAEMON STARTUP",
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | PID: {Path.cwd()}"
        )
        
        for line in lines:
            log_info(self.logger, line)
        
        # Configuration summary
        config_info = self.config.get_all_settings()
        lines = LogSection.section("Configuration", config_info)
        for line in lines:
            log_info(self.logger, line)
        
        # Validation
        if not self.config.is_valid:
            errors = self.config.validation_errors
            for error in errors:
                log_error(self.logger, f"Configuration error: {error}")
            return False
        
        if not self.config.is_configured:
            log_warning(
                self.logger,
                "OpenSubtitles API not configured. Please set credentials in .env"
            )
            return False
        
        log_success(self.logger, "Configuration valid")
        return True
    
    async def run_cycle(self) -> dict:
        """
        Run one download cycle
        
        Returns:
            Statistics dictionary
        """
        cycle_start = datetime.now()
        log_info(self.logger, f"Starting download cycle #{self.cycles_completed + 1}")
        
        # Ensure authenticated
        if not self.downloader.ensure_authenticated():
            log_error(self.logger, "Failed to authenticate with OpenSubtitles")
            return {'error': 'Authentication failed'}
        
        # Check remaining downloads
        remaining = self.downloader.client.get_remaining_downloads()
        log_info(
            self.logger,
            f"Remaining downloads today: {remaining}/{self.config.download_limit}"
        )
        
        if remaining <= 0:
            log_warning(self.logger, "No downloads remaining for today")
            return {'skipped': 'Rate limit reached'}
        
        # Process by priority
        stats = {
            'files_processed': 0,
            'subtitles_downloaded': 0,
            'subtitles_skipped': 0,
        }
        
        for media_type in self.config.priority_order:
            if self.shutdown_requested:
                log_info(self.logger, "Shutdown requested, stopping cycle")
                break
            
            remaining = self.downloader.client.get_remaining_downloads()
            if remaining <= 0:
                log_info(self.logger, "Rate limit reached, stopping cycle")
                break
            
            log_info(
                self.logger,
                f"Processing {media_type}s ({remaining} downloads remaining)"
            )
            
            # Get files without subtitles
            files = self.downloader.get_files_without_subtitles(
                media_type=media_type
            )
            
            log_info(self.logger, f"Found {len(files)} files without subtitles")
            
            # Process files
            for file_info in files:
                if self.shutdown_requested:
                    break
                
                remaining = self.downloader.client.get_remaining_downloads()
                if remaining <= 0:
                    break
                
                organized_path = Path(file_info.get('organized_path', ''))
                
                if not organized_path.exists():
                    log_warning(
                        self.logger,
                        f"File not found: {organized_path.name}"
                    )
                    continue
                
                # Download subtitle
                success = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.downloader.download_for_file(
                        file_info, organized_path
                    )
                )
                
                if success:
                    stats['subtitles_downloaded'] += 1
                else:
                    stats['subtitles_skipped'] += 1
                
                stats['files_processed'] += 1
                
                # Small delay between downloads
                await asyncio.sleep(1)
        
        # Calculate cycle duration
        cycle_end = datetime.now()
        duration = (cycle_end - cycle_start).total_seconds()
        
        # Log summary
        self.log_cycle_summary(stats, duration)
        
        # Update statistics
        self.cycles_completed += 1
        self.total_downloads += stats['subtitles_downloaded']
        
        return stats
    
    def log_cycle_summary(self, stats: dict, duration: float):
        """Log cycle summary"""
        # Format duration
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        if hours > 0:
            duration_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            duration_str = f"{minutes}m {seconds}s"
        else:
            duration_str = f"{seconds}s"
        
        # Get downloader stats
        downloader_stats = self.downloader.get_statistics()
        
        # Build summary
        summary_lines = [
            f"Cycle Complete: {stats.get('subtitles_downloaded', 0)} downloaded | "
            f"{stats.get('subtitles_skipped', 0)} skipped | "
            f"{stats.get('files_processed', 0)} processed",
            f"Duration: {duration_str}",
            f"Downloads remaining: {downloader_stats.get('Remaining', 0)}",
        ]
        
        log_stats(self.logger, " | ".join(summary_lines))
    
    def log_shutdown(self):
        """Log daemon shutdown"""
        summary = {
            'Uptime': str(datetime.now() - self.start_time) if self.start_time else 'N/A',
            'Cycles completed': self.cycles_completed,
            'Total downloads': self.total_downloads,
            'Final stats': str(self.downloader.get_statistics()),
        }
        
        lines = LogSection.major_header(
            "SUBTITLE DAEMON SHUTDOWN",
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        for line in lines:
            log_info(self.logger, line)
        
        for key, value in summary.items():
            log_info(self.logger, f"{key}: {value}")
    
    async def run(self):
        """Run daemon continuously"""
        self.running = True
        self.start_time = datetime.now()
        
        # Log startup
        if not self.log_startup():
            log_error(
                self.logger,
                "Daemon startup failed. Check configuration."
            )
            return
        
        log_success(self.logger, "Subtitle Daemon started")
        log_info(
            self.logger,
            f"Check interval: {self.config.check_interval // 3600} hours"
        )
        
        # Main loop
        while not self.shutdown_requested:
            try:
                # Run cycle
                await self.run_cycle()
                
                # Wait for next cycle
                next_check = datetime.now().timestamp() + self.config.check_interval
                next_check_str = datetime.fromtimestamp(next_check).strftime('%Y-%m-%d %H:%M:%S')
                
                log_info(
                    self.logger,
                    f"Next check: {next_check_str} "
                    f"({self.config.check_interval // 3600} hours)"
                )
                
                # Sleep in small increments to check for shutdown
                sleep_interval = 60  # Check every minute
                for _ in range(int(self.config.check_interval / sleep_interval)):
                    if self.shutdown_requested:
                        break
                    await asyncio.sleep(sleep_interval)
                
            except Exception as e:
                log_error(self.logger, f"Cycle error: {e}")
                # Wait 1 hour before retrying on error
                await asyncio.sleep(3600)
        
        # Shutdown
        self.running = False
        self.log_shutdown()
        
        # Cleanup
        self.downloader.client.logout()
        self.database.close()
        
        log_info(self.logger, "Subtitle Daemon stopped")
    
    def stop(self):
        """Request daemon stop"""
        log_info(self.logger, "Stop requested")
        self.shutdown_requested = True


async def main():
    """Main entry point"""
    daemon = SubtitleDaemon()
    await daemon.run()


if __name__ == "__main__":
    import logging
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDaemon interrupted")
        sys.exit(0)
