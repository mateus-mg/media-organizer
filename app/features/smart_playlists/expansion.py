"""Genre expansion module for inferring parent genres and expanding subgenres."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

LOGGER = logging.getLogger(__name__)

DEFAULT_HIERARCHY_PATH = Path("./data/genre_hierarchy.json")

class GenreExpander:
    """Expands parent genres into subgenres and infers parents from subgenres."""

    def __init__(self, hierarchy_file_path: Optional[str] = None):
        self._hierarchy_file_path = Path(hierarchy_file_path) if hierarchy_file_path else DEFAULT_HIERARCHY_PATH
        self._hierarchy: Optional[Dict] = None
        self._cache: Optional[Dict[str, List[str]]] = None
        self._load_hierarchy()

    def _create_default_hierarchy(self) -> Dict:
        return {
            "version": 1,
            "updated_at": datetime.now().isoformat(),
            "hierarchy": {}
        }

    def _validate_schema(self, data: dict) -> bool:
        if not isinstance(data, dict):
            return False
        if "version" not in data or not isinstance(data["version"], int):
            return False
        if "updated_at" not in data:
            return False
        if "hierarchy" not in data or not isinstance(data["hierarchy"], dict):
            return False
        return True

    def _save_hierarchy(self) -> None:
        try:
            self._hierarchy_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._hierarchy_file_path, "w", encoding="utf-8") as f:
                json.dump(self._hierarchy, f, indent=2, ensure_ascii=False)
        except Exception as e:
            LOGGER.error("Error saving hierarchy file %s: %s", self._hierarchy_file_path, e)

    def _load_hierarchy(self) -> None:
        """Carrega hierarquia com validação e fallback."""
        if self._hierarchy is not None:
            return

        try:
            if not self._hierarchy_file_path.exists():
                LOGGER.warning(
                    "Hierarchy file not found at %s. Creating default empty hierarchy.",
                    self._hierarchy_file_path,
                )
                self._hierarchy = self._create_default_hierarchy()
                self._save_hierarchy()
                self._cache = {}
                return

            with open(self._hierarchy_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not self._validate_schema(data):
                LOGGER.warning(
                    "Invalid schema in hierarchy file %s. Using default empty hierarchy.",
                    self._hierarchy_file_path,
                )
                self._hierarchy = self._create_default_hierarchy()
                self._cache = {}
                return

            self._hierarchy = data
            self._cache = {k.lower(): [s.lower() for s in v] for k, v in data.get("hierarchy", {}).items()}

        except json.JSONDecodeError as e:
            LOGGER.warning(
                "Invalid JSON in hierarchy file %s: %s. Using default empty hierarchy.",
                self._hierarchy_file_path,
                e,
            )
            self._hierarchy = self._create_default_hierarchy()
            self._cache = {}
        except Exception as e:
            LOGGER.error(
                "Error loading hierarchy file %s: %s. Using default empty hierarchy.",
                self._hierarchy_file_path,
                e,
            )
            self._hierarchy = self._create_default_hierarchy()
            self._cache = {}

    def _ensure_loaded(self) -> Dict[str, List[str]]:
        """Return the cached hierarchy, reloading if necessary."""
        if self._cache is None:
            self._load_hierarchy()
        return self._cache or {}

    def expand(self, parent_genre: str) -> List[str]:
        """Return a list of subgenres for the given parent genre."""
        hierarchy = self._ensure_loaded()
        result = list(hierarchy.get(parent_genre.lower(), []))
        if not result:
            LOGGER.warning(
                "Genre '%s' not found in hierarchy. Returning empty list.",
                parent_genre,
            )
        return result

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
