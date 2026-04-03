"""Features package for Media Organization System."""

# Lazy imports to avoid circular dependencies
__all__ = [
    "MusicQualityMonitor",
    "FilenameSuggestionEngine",
    "FilenameSuggestion",
    "iter_preview_lines",
]


def __getattr__(name):
    """Lazy loading to avoid circular imports."""
    if name == "MusicQualityMonitor":
        from app.features.quality_monitor import MusicQualityMonitor
        return MusicQualityMonitor
    elif name in ("FilenameSuggestionEngine", "FilenameSuggestion", "iter_preview_lines"):
        from app.features.filename_suggestions import (
            FilenameSuggestionEngine,
            FilenameSuggestion,
            iter_preview_lines,
        )
        if name == "FilenameSuggestionEngine":
            return FilenameSuggestionEngine
        elif name == "FilenameSuggestion":
            return FilenameSuggestion
        return iter_preview_lines
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
