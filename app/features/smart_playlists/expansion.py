"""Genre expansion module for inferring parent genres and expanding subgenres."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

LOGGER = logging.getLogger(__name__)

DEFAULT_HIERARCHY_PATH = Path("./data/genre_hierarchy.json")

DEFAULT_HIERARCHY_CONTENT = {
    "version": 1,
    "updated_at": "1970-01-01T00:00:00Z",
    "hierarchy": {},
}


class GenreExpander:
    """Expands parent genres into subgenres and infers parents from subgenres."""

    def __init__(self, hierarchy_file_path: Optional[str] = None):
        self._hierarchy_file_path = Path(hierarchy_file_path) if hierarchy_file_path else DEFAULT_HIERARCHY_PATH
        self._cache: Optional[Dict[str, List[str]]] = None
        self._load_hierarchy()

    def _load_hierarchy(self) -> None:
        """Load hierarchy from disk with in-memory caching."""
        if self._cache is not None:
            return

        if not self._hierarchy_file_path.exists():
            LOGGER.warning(
                "Hierarchy file not found at %s. Creating default empty hierarchy.",
                self._hierarchy_file_path,
            )
            self._hierarchy_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._hierarchy_file_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_HIERARCHY_CONTENT, f, indent=2, ensure_ascii=False)
            self._cache = {}
            return

        try:
            with open(self._hierarchy_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache = {k.lower(): [s.lower() for s in v] for k, v in data.get("hierarchy", {}).items()}
        except json.JSONDecodeError:
            LOGGER.warning(
                "Invalid JSON in hierarchy file %s. Using default empty hierarchy.",
                self._hierarchy_file_path,
            )
            self._cache = {}

    def _ensure_loaded(self) -> Dict[str, List[str]]:
        """Return the cached hierarchy, reloading if necessary."""
        if self._cache is None:
            self._load_hierarchy()
        return self._cache or {}

    def expand(self, parent_genre: str) -> List[str]:
        """Return a list of subgenres for the given parent genre."""
        hierarchy = self._ensure_loaded()
        return list(hierarchy.get(parent_genre.lower(), []))

    def infer_parent(self, child_genre: str) -> Optional[str]:
        """Infer the parent genre by substring match (case-insensitive)."""
        normalized = child_genre.lower()
        hierarchy = self._ensure_loaded()
        for parent, children in hierarchy.items():
            for sub in children:
                if sub in normalized:
                    return parent
        return None

    def find_matches(self, pattern: str) -> List[str]:
        """Find all subgenres that contain the given pattern."""
        normalized_pattern = pattern.lower()
        hierarchy = self._ensure_loaded()
        matches: List[str] = []
        seen: set = set()
        for children in hierarchy.values():
            for sub in children:
                if normalized_pattern in sub and sub not in seen:
                    seen.add(sub)
                    matches.append(sub)
        return matches
