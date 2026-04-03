"""Configuration package for Media Organization System."""

from app.config.constants import (
    AUDIO_EXTS,
    LYRICS_EXTS,
    BOOK_EXTS,
    COMIC_EXTS,
    SUPPORTED_MEDIA_EXTS,
)
from app.config.settings import Config

__all__ = [
    "Config",
    "AUDIO_EXTS",
    "LYRICS_EXTS",
    "BOOK_EXTS",
    "COMIC_EXTS",
    "SUPPORTED_MEDIA_EXTS",
]
