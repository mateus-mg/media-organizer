#!/usr/bin/env python3
"""
Configuration for OpenSubtitles Subtitle Downloader

Media Organization System - Subtitle Automation Module
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv


class SubtitleConfig:
    """
    Configuration manager for OpenSubtitles subtitle downloader.
    
    All configuration is loaded from .env file.
    """
    
    def __init__(self, env_file: str = None):
        """
        Initialize subtitle configuration
        
        Args:
            env_file: Path to .env file (default: .env in project root)
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        # ========== API Credentials ==========
        self.api_key = os.getenv('OPENSUBTITLES_API_KEY', '')
        self.api_username = os.getenv('OPENSUBTITLES_USERNAME', '')
        self.api_password = os.getenv('OPENSUBTITLES_PASSWORD', '')
        
        # ========== API Settings ==========
        self.api_url = 'https://api.opensubtitles.com/api/v1'
        self.download_limit = 20  # downloads per day (API limit)
        self.reset_time = '00:00'  # time when limit resets (HH:MM)
        
        # ========== Download Preferences ==========
        # Preferred languages in priority order
        languages_str = os.getenv('SUBTITLE_LANGUAGES', 'pt,en,es')
        self.preferred_languages = [
            lang.strip().lower() 
            for lang in languages_str.split(',')
        ]
        
        # Only download if no subtitle exists for this language
        self.skip_if_exists = os.getenv(
            'SUBTITLE_SKIP_IF_EXISTS', 'true'
        ).lower() == 'true'
        
        # Download foreign language subtitles only
        self.foreign_only = os.getenv(
            'SUBTITLE_FOREIGN_ONLY', 'false'
        ).lower() == 'true'
        
        # ========== Paths ==========
        self.database_path = Path(os.getenv(
            'DATABASE_PATH', './data/organization.json'
        ))

        # Use same log file as main system for centralized logging
        self.log_file = Path(os.getenv(
            'SUBTITLE_LOG_FILE', './logs/organizer.log'  # Centralized log
        ))

        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # ========== Daemon Settings ==========
        # Check interval in seconds (default: 24 hours)
        self.check_interval = int(os.getenv(
            'SUBTITLE_DOWNLOAD_INTERVAL', '86400'
        ))
        
        # Enable/disable daemon
        self.daemon_enabled = os.getenv(
            'SUBTITLE_DAEMON_ENABLED', 'true'
        ).lower() == 'true'
        
        # ========== Rate Limiting ==========
        # Delay between API calls (seconds)
        self.api_delay = float(os.getenv(
            'OPENSUBTITLES_API_DELAY', '1.0'
        ))
        
        # Retry attempts on failure
        self.max_retries = int(os.getenv(
            'OPENSUBTITLES_MAX_RETRIES', '3'
        ))
        
        # Retry backoff (seconds)
        self.retry_backoff = float(os.getenv(
            'OPENSUBTITLES_RETRY_BACKOFF', '5.0'
        ))
        
        # ========== File Settings ==========
        # Subtitle file extensions to accept
        self.accepted_extensions = ['.srt', '.sub', '.txt', '.smi', '.rt', '.ssa']
        
        # Preferred subtitle extension
        self.preferred_extension = '.srt'
        
        # ========== Logging ==========
        self.log_level = os.getenv('SUBTITLE_LOG_LEVEL', 'INFO').upper()
        
        # ========== Priority Order ==========
        # Order to process media types
        self.priority_order = ['movie', 'tv', 'dorama', 'anime']
    
    @property
    def is_configured(self) -> bool:
        """Check if API credentials are configured"""
        return bool(self.api_key and self.api_username and self.api_password)
    
    @property
    def validation_errors(self) -> List[str]:
        """Get list of configuration validation errors"""
        errors = []
        
        if not self.api_key:
            errors.append("OPENSUBTITLES_API_KEY is not set")
        
        if not self.api_username:
            errors.append("OPENSUBTITLES_USERNAME is not set")
        
        if not self.api_password:
            errors.append("OPENSUBTITLES_PASSWORD is not set")
        
        if self.download_limit < 1 or self.download_limit > 20:
            errors.append("DOWNLOAD_LIMIT must be between 1 and 20")
        
        if self.check_interval < 3600:
            errors.append("CHECK_INTERVAL must be at least 3600 seconds (1 hour)")
        
        if not self.preferred_languages:
            errors.append("SUBTITLE_LANGUAGES cannot be empty")
        
        return errors
    
    @property
    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        return len(self.validation_errors) == 0
    
    def get_all_settings(self) -> dict:
        """Get all settings as dictionary"""
        return {
            'API Key': '***' if self.api_key else 'Not set',
            'Username': self.api_username or 'Not set',
            'API URL': self.api_url,
            'Download Limit': f"{self.download_limit}/day",
            'Languages': ', '.join(self.preferred_languages),
            'Check Interval': f"{self.check_interval // 3600}h",
            'Log File': str(self.log_file),
            'Log Level': self.log_level,
        }
    
    def __repr__(self) -> str:
        return f"SubtitleConfig(valid={self.is_valid}, languages={self.preferred_languages})"


# Singleton instance
_config_instance = None


def get_config() -> SubtitleConfig:
    """
    Get or create SubtitleConfig singleton
    
    Returns:
        SubtitleConfig instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = SubtitleConfig()
    return _config_instance
