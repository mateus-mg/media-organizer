"""
TMDB (The Movie Database) API client
Used ONLY for fetching IDs to add to folder names
Does NOT download metadata, images, or other content
"""

import requests
import time
from typing import Optional, Dict, List
from pathlib import Path
import json


class TMDBClient:
    """Client for TMDB API (ID retrieval only)"""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str, use_fallback: bool = True):
        """
        Initialize TMDB client

        Args:
            api_key: TMDB API key
            use_fallback: Use filename parsing if API fails
        """
        self.api_key = api_key
        self.use_fallback = use_fallback
        self.cache: Dict[str, int] = {}
        self.last_request_time = 0
        self.min_request_interval = 0.25  # 4 requests per second max

    def _rate_limit(self):
        """Apply rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)

        self.last_request_time = time.time()

    def _clean_title_for_search(self, title: str) -> str:
        """
        Clean title before TMDB search by removing actor names and extra info

        Args:
            title: Raw movie title extracted from filename

        Returns:
            Cleaned title ready for search
        """
        import re

        original_title = title

        # Remove actor names after comma (e.g., "Safe Haven Julianne Hough, Josh Duhamel")
        if ',' in title:
            title = title.split(',')[0].strip()

        # Try to find pattern of capitalized words that might be the English title
        # after a Portuguese title (e.g., "Um porto seguro Safe Haven")
        words = title.split()

        # Look for sequences of capitalized words (likely proper title)
        capitalized_sequences = []
        current_sequence = []

        portuguese_indicators = ['um', 'uma', 'o', 'a', 'os',
                                 'as', 'de', 'da', 'do', 'das', 'dos', 'para', 'com']

        for i, word in enumerate(words):
            # Skip single letters
            if len(word) <= 1:
                continue

            # Check if word starts with capital
            if word and word[0].isupper():
                # Check if this might be start of Portuguese title (skip it)
                if i == 0 and word.lower() in portuguese_indicators:
                    continue
                current_sequence.append(word)
            else:
                # Lowercase word - might be Portuguese, save sequence if we have one
                if len(current_sequence) >= 2:
                    capitalized_sequences.append(' '.join(current_sequence))
                current_sequence = []

        # Add last sequence if exists
        if len(current_sequence) >= 2:
            capitalized_sequences.append(' '.join(current_sequence))

        # If we found capitalized sequences
        if capitalized_sequences:
            # Prefer sequences that appear after the start (likely English after Portuguese)
            for seq in capitalized_sequences:
                start_pos = title.find(seq)
                # If sequence starts after position 10, it's likely the English title
                if start_pos > 10:
                    # Now remove potential actor names from this sequence
                    # Remove patterns like "Firstname Lastname" at the end
                    seq_words = seq.split()
                    # Keep only first 2-4 words (typical movie title length)
                    if len(seq_words) > 4:
                        # Try to identify where the title ends and actor names begin
                        # Usually the title is 1-3 words
                        seq = ' '.join(seq_words[:3])
                    elif len(seq_words) == 4:
                        # If exactly 4 words, likely "Title Title Actor Actor"
                        seq = ' '.join(seq_words[:2])
                    return seq

            # Otherwise, try the longest sequence but clean it
            longest = max(capitalized_sequences, key=len)
            if len(longest.split()) >= 2:
                # Clean potential actor names
                seq_words = longest.split()
                if len(seq_words) > 4:
                    longest = ' '.join(seq_words[:3])
                return longest

        # Fallback: return cleaned title
        return title.strip()
        return longest

        # Fallback: return cleaned title
        return title.strip()

    def _make_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """
        Make API request with rate limiting

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            JSON response or None if error
        """
        if not self.api_key or self.api_key == "your_api_key_here":
            return None

        self._rate_limit()

        params['api_key'] = self.api_key
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"TMDB API error: {e}")
            return None

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """
        Search for movie and return TMDB data with English title

        Args:
            title: Movie title
            year: Release year (optional, improves accuracy)

        Returns:
            Dict with 'id', 'title' (English), and 'original_title' or None if not found
        """
        # Clean title before search
        clean_title = self._clean_title_for_search(title)

        # Check cache
        cache_key = f"movie:{clean_title}:{year}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # First try: search with Portuguese language for better PT matching
        params = {
            'query': clean_title,
            'include_adult': 'false',
            'language': 'pt-BR'  # Search in Portuguese for better matching
        }

        if year:
            params['year'] = year

        data = self._make_request('/search/movie', params)

        if data and data.get('results'):
            # Get first result
            result = data['results'][0]

            # Get movie ID
            movie_id = result.get('id')

            # Fetch full movie details with English title
            if movie_id:
                details = self.get_movie_details(movie_id)
                if details:
                    movie_data = {
                        'id': movie_id,
                        # English title from details
                        'title': details.get('title'),
                        'original_title': details.get('original_title'),
                        'year': details.get('release_date', '')[:4] if details.get('release_date') else None,
                        'release_date': details.get('release_date')
                    }

                    # Cache result
                    self.cache[cache_key] = movie_data
                    return movie_data

        return None

    def search_tv(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """
        Search for TV show and return TMDB data with English title

        Args:
            title: TV show title
            year: First air year (optional, improves accuracy)

        Returns:
            Dict with 'id', 'name' (English), and 'original_name' or None if not found
        """
        # Check cache
        cache_key = f"tv:{title}:{year}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Search in Portuguese for better matching
        params = {
            'query': title,
            'include_adult': 'false',
            'language': 'pt-BR'
        }

        if year:
            params['first_air_date_year'] = year

        data = self._make_request('/search/tv', params)

        if data and data.get('results'):
            # Get first result
            result = data['results'][0]
            tv_id = result.get('id')

            # Fetch full TV details with English title
            if tv_id:
                details = self.get_tv_details(tv_id)
                if details:
                    tv_data = {
                        'id': tv_id,
                        'name': details.get('name'),  # English title
                        # Original language title
                        'original_name': details.get('original_name'),
                        'year': details.get('first_air_date', '')[:4] if details.get('first_air_date') else None
                    }

                    # Cache result
                self.cache[cache_key] = tv_data
                return tv_data

        return None

    def get_movie_year(self, tmdb_id: int) -> Optional[int]:
        """
        Get movie release year from TMDB ID

        Args:
            tmdb_id: TMDB movie ID

        Returns:
            Release year or None
        """
        data = self._make_request(f'/movie/{tmdb_id}', {})

        if data and data.get('release_date'):
            try:
                year_str = data['release_date'][:4]
                return int(year_str)
            except (ValueError, IndexError):
                return None

        return None

    def get_movie_details(self, tmdb_id: int) -> Optional[Dict]:
        """
        Get full movie details from TMDB ID with English title

        Args:
            tmdb_id: TMDB movie ID

        Returns:
            Dict with movie details or None
        """
        params = {'language': 'en-US'}
        data = self._make_request(f'/movie/{tmdb_id}', params)
        return data if data else None

    def get_tv_details(self, tmdb_id: int) -> Optional[Dict]:
        """
        Get full TV show details from TMDB ID with English title

        Args:
            tmdb_id: TMDB TV show ID

        Returns:
            Dict with TV show details or None
        """
        params = {'language': 'en-US'}
        data = self._make_request(f'/tv/{tmdb_id}', params)
        return data if data else None

    def get_tv_year(self, tmdb_id: int) -> Optional[int]:
        """
        Get TV show first air year from TMDB ID

        Args:
            tmdb_id: TMDB TV show ID

        Returns:
            First air year or None
        """
        data = self._make_request(f'/tv/{tmdb_id}', {})

        if data and data.get('first_air_date'):
            try:
                year_str = data['first_air_date'][:4]
                return int(year_str)
            except (ValueError, IndexError):
                return None

        return None

    def find_movie_id(self, title: str, year: Optional[int] = None) -> Optional[int]:
        """
        Find movie TMDB ID with fallback to None if not found

        Args:
            title: Movie title
            year: Release year (optional)

        Returns:
            TMDB ID or None
        """
        tmdb_id = self.search_movie(title, year)

        if tmdb_id:
            return tmdb_id

        # Try without year if first search failed
        if year:
            tmdb_id = self.search_movie(title)
            if tmdb_id:
                return tmdb_id

        # Try with cleaned title (remove articles)
        cleaned_title = self._clean_title_for_search(title)
        if cleaned_title != title:
            tmdb_id = self.search_movie(cleaned_title, year)
            if tmdb_id:
                return tmdb_id

        return None

    def find_tv_id(self, title: str, year: Optional[int] = None) -> Optional[int]:
        """
        Find TV show TMDB ID with fallback strategies

        Args:
            title: TV show title
            year: First air year (optional)

        Returns:
            TMDB ID or None
        """
        tmdb_id = self.search_tv(title, year)

        if tmdb_id:
            return tmdb_id

        # Try without year if first search failed
        if year:
            tmdb_id = self.search_tv(title)
            if tmdb_id:
                return tmdb_id

        # Try with cleaned title
        cleaned_title = self._clean_title_for_search(title)
        if cleaned_title != title:
            tmdb_id = self.search_tv(cleaned_title, year)
            if tmdb_id:
                return tmdb_id

        return None

    def save_cache(self, cache_file: Path):
        """
        Save cache to file

        Args:
            cache_file: Path to cache file
        """
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"Error saving TMDB cache: {e}")

    def load_cache(self, cache_file: Path):
        """
        Load cache from file

        Args:
            cache_file: Path to cache file
        """
        try:
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    self.cache = json.load(f)
        except Exception as e:
            print(f"Error loading TMDB cache: {e}")
            self.cache = {}

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        movie_count = sum(1 for k in self.cache.keys()
                          if k.startswith('movie:'))
        tv_count = sum(1 for k in self.cache.keys() if k.startswith('tv:'))

        return {
            'total_entries': len(self.cache),
            'movie_entries': movie_count,
            'tv_entries': tv_count
        }
