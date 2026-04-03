"""Metadata package for Media Organization System."""

from app.metadata.metadata import (
    extract_audio_metadata,
    enrich_book_metadata_with_online_sources,
    enrich_music_metadata_with_online_sources,
    MetadataParser,
)

__all__ = [
    "extract_audio_metadata",
    "enrich_book_metadata_with_online_sources",
    "enrich_music_metadata_with_online_sources",
    "MetadataParser",
]
