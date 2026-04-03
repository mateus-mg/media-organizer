"""Artist genre cache to avoid repeated MusicBrainz/Last.fm lookups."""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

CACHE_PATH = Path(os.getenv("ARTIST_GENRE_CACHE_PATH",
                  "data/artist_genre_cache.json"))
CACHE_TTL_HOURS = int(
    os.getenv("ARTIST_GENRE_CACHE_TTL_HOURS", "720"))  # 30 days


class ArtistGenreCache:
    """Cache genres per artist."""

    def __init__(self, cache_path: Path = CACHE_PATH):
        self.cache_path = cache_path
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load cache from disk."""
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        """Persist cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get(self, artist: str) -> Optional[Dict]:
        """Get genres for an artist from cache.

        Returns:
            Dict with 'genres' and 'source', or None if missing/expired.
        """
        artist_key = artist.lower().strip()
        entry = self.cache.get(artist_key)

        if not entry:
            return None

        # Check TTL.
        cached_at = datetime.fromisoformat(
            entry.get('cached_at', datetime.now().isoformat()))
        if datetime.now() - cached_at > timedelta(hours=CACHE_TTL_HOURS):
            del self.cache[artist_key]
            return None

        return {
            'genres': entry.get('genres', []),
            'source': entry.get('source', 'unknown')
        }

    def set(self, artist: str, genres: List[str], source: str = 'musicbrainz'):
        """Save artist genres in cache.

        Args:
            artist: Artist name
            genres: List of genres
            source: Genre source ('musicbrainz', 'lastfm', etc.)
        """
        artist_key = artist.lower().strip()
        self.cache[artist_key] = {
            'genres': genres,
            'cached_at': datetime.now().isoformat(),
            'source': source
        }
        self._save_cache()

    def clear(self):
        """Clear the full cache."""
        self.cache = {}
        self._save_cache()

    def stats(self) -> Dict:
        """Return cache statistics."""
        now = datetime.now()
        total = len(self.cache)
        expired = 0

        for entry in self.cache.values():
            cached_at = datetime.fromisoformat(
                entry.get('cached_at', now.isoformat()))
            if now - cached_at > timedelta(hours=CACHE_TTL_HOURS):
                expired += 1

        return {
            'total_entries': total,
            'expired_entries': expired,
            'valid_entries': total - expired,
            'cache_file': str(self.cache_path),
            'cache_file_size_kb': self.cache_path.stat().st_size / 1024 if self.cache_path.exists() else 0
        }


# Global cache instance
_genre_cache = None


def get_artist_genre_cache() -> ArtistGenreCache:
    """Get the global cache instance."""
    global _genre_cache
    if _genre_cache is None:
        _genre_cache = ArtistGenreCache()
    return _genre_cache
