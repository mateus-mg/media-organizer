"""
Logging utilities for Media Organization System
Provides structured, colorized logging with dry-run support
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler
from datetime import datetime
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme


# Custom theme for Rich console
CUSTOM_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "dry_run": "bold magenta",
    "conflict": "bold yellow",
    "rate_limit": "dim cyan",
})


class MediaOrganizerLogger:
    """Custom logger for Media Organization System"""
    
    def __init__(
        self,
        name: str = "media-organizer",
        log_level: str = "INFO",
        log_file: Optional[Path] = None,
        max_size_mb: int = 50,
        backup_count: int = 5,
        dry_run: bool = False
    ):
        """
        Initialize logger
        
        Args:
            name: Logger name
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            log_file: Path to log file (None for console only)
            max_size_mb: Maximum log file size in MB
            backup_count: Number of backup log files to keep
            dry_run: Whether in dry-run mode
        """
        self.name = name
        self.dry_run = dry_run
        self.console = Console(theme=CUSTOM_THEME)
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.handlers.clear()
        
        # Console handler with Rich
        console_handler = RichHandler(
            console=self.console,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=True
        )
        console_handler.setLevel(getattr(logging, log_level.upper()))
        self.logger.addHandler(console_handler)
        
        # File handler if log file specified
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)  # File gets all logs
            self.logger.addHandler(file_handler)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message, **kwargs)
    
    def success(self, message: str):
        """Log success message (custom level)"""
        self.console.print(f"[success]✓[/success] {message}")
        self.logger.info(f"SUCCESS: {message}")
    
    def dry_run_action(self, action: str, details: str = ""):
        """Log dry-run action"""
        prefix = "[dry_run][DRY-RUN][/dry_run]"
        message = f"{prefix} Would {action}"
        if details:
            message += f": {details}"
        self.console.print(message)
        self.logger.info(f"DRY-RUN: Would {action}: {details}")
    
    def file_operation(
        self,
        operation: str,
        source: str,
        dest: str,
        success: bool = True,
        dry_run: bool = False,
        error_msg: str = ""
    ):
        """
        Log file operation
        
        Args:
            operation: Operation type (hardlink, move, copy, etc.)
            source: Source path
            dest: Destination path
            success: Whether operation succeeded
            dry_run: Whether this was a dry-run
            error_msg: Error message if failed
        """
        if dry_run:
            self.dry_run_action(
                f"{operation}",
                f"{Path(source).name} -> {dest}"
            )
        elif success:
            self.success(f"{operation.capitalize()}: {Path(source).name} -> {dest}")
        else:
            self.error(f"Failed to {operation}: {source} -> {dest}")
            if error_msg:
                self.error(f"  Error: {error_msg}")
    
    def conflict_detected(self, path: str, strategy: str, resolution: str):
        """Log file conflict and resolution"""
        self.console.print(
            f"[conflict]⚠ CONFLICT:[/conflict] File exists: {path}"
        )
        self.console.print(
            f"[conflict]  Strategy:[/conflict] {strategy} -> {resolution}"
        )
        self.logger.warning(f"CONFLICT: {path} (strategy: {strategy}, result: {resolution})")
    
    def rate_limited(self, operation: str, wait_time: float = 0):
        """Log rate limiting"""
        if wait_time > 0:
            self.console.print(
                f"[rate_limit]⏱ RATE LIMITED:[/rate_limit] {operation} "
                f"(waiting {wait_time:.2f}s)"
            )
        else:
            self.debug(f"Rate limited: {operation}")
    
    def api_call(self, service: str, endpoint: str, success: bool, error_msg: str = ""):
        """Log API call"""
        if success:
            self.debug(f"API call to {service}: {endpoint} - SUCCESS")
        else:
            self.error(f"API call to {service}: {endpoint} - FAILED")
            if error_msg:
                self.error(f"  Error: {error_msg}")
    
    def organization_summary(
        self,
        total_files: int,
        organized: int,
        skipped: int,
        failed: int,
        duration_seconds: float
    ):
        """Log organization summary"""
        self.console.print("\n" + "=" * 50)
        self.console.print("[bold cyan]Organization Summary[/bold cyan]")
        self.console.print("=" * 50)
        self.console.print(f"Total files processed: {total_files}")
        self.console.print(f"[success]✓ Organized:[/success] {organized}")
        self.console.print(f"[warning]⊘ Skipped:[/warning] {skipped}")
        self.console.print(f"[error]✗ Failed:[/error] {failed}")
        self.console.print(f"Duration: {duration_seconds:.2f}s")
        self.console.print("=" * 50 + "\n")
    
    def separator(self, title: str = ""):
        """Print a visual separator"""
        if title:
            self.console.print(f"\n[bold]{title}[/bold]")
            self.console.print("─" * 50)
        else:
            self.console.print("─" * 50)


def get_logger(
    name: str = "media-organizer",
    config: Optional[object] = None,
    dry_run: bool = False
) -> MediaOrganizerLogger:
    """
    Get or create logger instance
    
    Args:
        name: Logger name
        config: Config object (optional)
        dry_run: Dry-run mode
    
    Returns:
        MediaOrganizerLogger instance
    """
    if config:
        return MediaOrganizerLogger(
            name=name,
            log_level=config.log_level,
            log_file=config.log_file,
            max_size_mb=config.log_max_size_mb,
            backup_count=config.log_backup_count,
            dry_run=dry_run
        )
    else:
        return MediaOrganizerLogger(
            name=name,
            dry_run=dry_run
        )
