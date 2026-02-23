#!/usr/bin/env python3
"""
Log Formatter - Standardized hierarchical structure for logs
Media Organization System

Follows the same principles as Music Automation System:
- Clean logs with simple symbols (no emojis)
- Hierarchical structure (3 levels)
- Consistent formatting
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class LogSection:
    """Hierarchical log formatter with 3 levels of structure"""

    # Visual separators
    SEP_MAJOR = "━" * 80
    SEP_MINOR = "─" * 80

    # Indentation per level
    INDENT_L1 = ""
    INDENT_L2 = "  "
    INDENT_L3 = "    "

    # Symbols (reduced usage)
    CHECK = "✓"
    CROSS = "✗"
    ARROW = "→"
    BULLET = "•"

    @staticmethod
    def major_header(title: str, subtitle: str = None) -> List[str]:
        """
        Main section header (Level 1)

        Args:
            title: Main section title
            subtitle: Optional subtitle (additional info)

        Returns:
            List of formatted lines

        Example:
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            ORGANIZATION START - /path/to/downloads
            Media Type: all | Mode: Normal
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
        lines = [LogSection.SEP_MAJOR, title]
        if subtitle:
            lines.append(subtitle)
        lines.append(LogSection.SEP_MAJOR)
        return lines

    @staticmethod
    def minor_header(title: str) -> List[str]:
        """
        Subsection header (Level 2)

        Args:
            title: Subsection title

        Returns:
            List of formatted lines

        Example:
            ──────────────────────────────────────────────────────────
            Movies - 45 files organized
            ──────────────────────────────────────────────────────────
        """
        return [LogSection.SEP_MINOR, title, LogSection.SEP_MINOR]

    @staticmethod
    def section(title: str, items: Dict[str, Any], indent: str = INDENT_L2) -> List[str]:
        """
        Section with multiple items (Level 2)

        Args:
            title: Section title
            items: Dictionary with key-value pairs
            indent: Indentation string (default: 2 spaces)

        Returns:
            List of formatted lines

        Example:
            System Configuration
              Downloads: 7 configured
              Libraries: 7 configured
              Database: ./data/organization.json
        """
        lines = [f"\n{title}"]

        for key, value in items.items():
            if isinstance(value, dict):
                # Sub-item (Level 3)
                lines.append(f"{indent}{key}")
                for k, v in value.items():
                    lines.append(f"{indent}{indent}{k}: {v}")
            elif isinstance(value, list):
                # List of values
                lines.append(f"{indent}{key}:")
                for item in value:
                    lines.append(f"{indent}{indent}{LogSection.BULLET} {item}")
            else:
                # Simple item
                lines.append(f"{indent}{key}: {value}")

        return lines

    @staticmethod
    def inline_section(title: str, items: Dict[str, Any], sep: str = " | ") -> str:
        """
        Compact inline section with separator

        Args:
            title: Inline section title
            items: Dictionary with key-value pairs
            sep: Separator between items (default: " | ")

        Returns:
            Formatted inline string

        Example:
            "Database: Tracks: 203 | Playlists: 4 | Blacklist: 8 users"
        """
        items_str = sep.join([f"{k}: {v}" for k, v in items.items()])
        return f"{title}: {items_str}" if title else items_str

    @staticmethod
    def key_value_list(items: Dict[str, Any], sep: str = " | ", max_items: Optional[int] = None) -> str:
        """
        List of key-value pairs inline

        Args:
            items: Dictionary with key-value pairs
            sep: Separator between items (default: " | ")
            max_items: Maximum number of items (None = all)

        Returns:
            Formatted string

        Example:
            "Movies: 45 | Series: 32 | Anime: 18"
        """
        items_list = list(items.items())
        if max_items:
            items_list = items_list[:max_items]

        return sep.join([f"{k}: {v}" for k, v in items_list])

    @staticmethod
    def progress_line(current: int, total: int, label: str = "Progress",
                      extras: Optional[Dict[str, Any]] = None) -> str:
        """
        Progress line with additional info

        Args:
            current: Current value
            total: Total value
            label: Progress label (default: "Progress")
            extras: Extra info to include

        Returns:
            Formatted string

        Example:
            "[Progress: 23/25 | 2 failed | 68 quota left | Elapsed: 4m 12s]"
        """
        percentage = (current / total * 100) if total > 0 else 0
        parts = [f"{current}/{total} ({percentage:.1f}%)"]

        if extras:
            parts.extend([f"{k}: {v}" for k, v in extras.items()])

        return f"[{label}: {' | '.join(parts)}]"

    @staticmethod
    def download_item(artist: str, title: str, details: Optional[str] = None,
                      status: str = "✓", indent: str = INDENT_L2) -> List[str]:
        """
        Structured download/organization item

        Args:
            artist: Artist/Series/Author name
            title: Title/Track name
            details: Organization details (size, quality, destination)
            status: Status symbol (default: "✓")
            indent: Indentation (default: 2 spaces)

        Returns:
            List of formatted lines

        Example:
            → Movie Title (2020)
              TMDB ID: 12345 | movies/Movie Title (2020) [tmdbid-12345]/
        """
        lines = [f"{LogSection.ARROW} {artist} - {title}" if title else f"{LogSection.ARROW} {artist}"]
        if details:
            lines.append(f"{indent}{details}")
        return lines

    @staticmethod
    def error_block(title: str, details: Dict[str, Any], indent: str = INDENT_L2) -> List[str]:
        """
        Error block with details

        Args:
            title: Error title
            details: Error details dictionary
            indent: Indentation

        Returns:
            List of formatted lines

        Example:
            ✗ Organization Failed
              File: movie.mkv
              Reason: TMDB lookup failed
              Action: Added to unorganized list
        """
        lines = [f"{LogSection.CROSS} {title}"]
        for key, value in details.items():
            lines.append(f"{indent}{key}: {value}")
        return lines

    @staticmethod
    def stats_block(stats: Dict[str, Any], title: str = "Statistics") -> List[str]:
        """
        Statistics block

        Args:
            stats: Statistics dictionary
            title: Block title

        Returns:
            List of formatted lines
        """
        lines = [f"\n{title}"]
        for key, value in stats.items():
            lines.append(f"  {key}: {value}")
        return lines
