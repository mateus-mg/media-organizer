"""
Core types for Media Organization System.

Contains:
- MediaType enum
- Dataclasses (ValidationResult, FileMetadata, OrganizationResult, etc.)
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any


class MediaType(Enum):
    """Supported media types"""
    MUSIC = "music"
    LYRICS = "lyrics"
    ARTWORK = "artwork"
    BOOK = "book"
    COMIC = "comic"
    RENAMER = "renamer"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of validation operation"""
    is_valid: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FileMetadata:
    """Metadata extracted from media file"""
    media_type: MediaType
    title: Optional[str] = None
    year: Optional[int] = None
    author: Optional[str] = None
    album: Optional[str] = None
    track_number: Optional[int] = None
    genre: Optional[str] = None
    media_subtype: Optional[str] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrganizationResult:
    """Result of file organization"""
    success: bool
    organized_path: Optional[Path] = None
    error_message: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def was_processed(self) -> bool:
        """Check if file was processed (organized or skipped)"""
        return self.success or self.skipped


@dataclass
class ValidationRule:
    """Definition of validation rule"""
    name: str
    description: str
    applies_to: List[MediaType]
    required: bool = True
    error_message: str = "Validation failed"

    def validate(self, file_path: Path, metadata: FileMetadata) -> ValidationResult:
        """Validate file against this rule"""
        raise NotImplementedError


@dataclass
class ProcessedFile:
    """Information about processed file"""
    original_path: Path
    organized_path: Optional[Path] = None
    media_type: Optional[MediaType] = None
    success: bool = False
    error_message: Optional[str] = None
    processing_time: Optional[datetime] = None
    metadata: FileMetadata = field(
        default_factory=lambda: FileMetadata(media_type=MediaType.UNKNOWN))
    was_skipped: bool = False
