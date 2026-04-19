"""
Comic Vine API client with automatic PT→EN translation.
"""
import asyncio
import logging
import os
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)

COMIC_VINE_BASE_URL = "https://comicvine.gamespot.com/api"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class ComicVineClient:
    """Async Comic Vine API client with translation support."""

    def __init__(
        self,
        api_key: str,
        translate: bool = True,
        api_delay_seconds: float = 1.0,
        timeout_seconds: float = 15.0,
        min_match_score: int = 75,
    ):
        self.api_key = api_key
        self.translate = translate
        self.api_delay_seconds = api_delay_seconds
        self.timeout_seconds = timeout_seconds
        self.min_match_score = min_match_score
        self.base_url = COMIC_VINE_BASE_URL
        self._last_request_time = 0.0

    def _do_translate_sync(self, series_name: str) -> str:
        """Synchronous translation helper (runs in thread pool)."""
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='pt', target='en')
        return translator.translate(series_name)

    async def _translate_series_name(self, series_name: str) -> str:
        """Translate series name from Portuguese to English using Google Translate."""
        if not self.translate:
            return series_name

        try:
            translated = await asyncio.to_thread(self._do_translate_sync, series_name)
            if translated and translated != series_name:
                logger.debug("Translated '%s' -> '%s'", series_name, translated)
                return translated
        except Exception as exc:
            logger.warning("Translation failed for '%s': %s", series_name, exc)

        return series_name

    async def _rate_limit(self) -> None:
        """Ensure minimum delay between API requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.api_delay_seconds:
            await asyncio.sleep(self.api_delay_seconds - elapsed)
        self._last_request_time = time.time()

    async def _get_json_with_retry(
        self,
        session: aiohttp.ClientSession,
        url: str,
        max_retries: int = 2,
    ) -> Tuple[int, Dict[str, Any]]:
        """Fetch JSON with rate limiting and retry on transient errors."""
        for attempt in range(max_retries + 1):
            await self._rate_limit()
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
                async with session.get(url, timeout=timeout) as response:
                    data = await response.json()
                    status = response.status

                    if status == 200:
                        return (status, data)

                    if status == 429:
                        if attempt < max_retries:
                            retry_after = float(response.headers.get("Retry-After", 60))
                            logger.warning("Rate limited, waiting %ss", retry_after)
                            await asyncio.sleep(retry_after)
                            continue
                        return (status, data)

                    if status in (500, 502, 503, 504):
                        if attempt < max_retries:
                            wait_time = (2 ** attempt) + 1
                            logger.warning("Server error %d, retrying in %ss", status, wait_time)
                            await asyncio.sleep(wait_time)
                            continue

                    return (status, data)

            except asyncio.TimeoutError:
                logger.warning("Timeout for URL: %s", url)
                if attempt >= max_retries:
                    return (408, {})
            except Exception as exc:
                logger.error("Request failed: %s", exc)
                if attempt >= max_retries:
                    return (500, {})
                await asyncio.sleep(2 ** attempt)

        return (500, {})

    def _build_search_url(
        self,
        series_name: str,
        issue_number: Optional[str] = None,
        year: Optional[int] = None,
        limit: int = 10,
    ) -> str:
        """Build Comic Vine issues search URL.

        Note: Filtering by issue_number and year is done in Python after
        receiving results, as API filter syntax for these fields is unreliable.
        """
        query = re.sub(r"[()]", "", series_name).strip()

        filters = [f"name:{query}"]
        # Note: cover_date filter with year range is unreliable, so we filter in Python

        filter_str = ",".join(filters)
        field_list = (
            "name,issue_number,cover_date,store_date,volume,"
            "description,image,person_credits"
        )

        params = {
            "api_key": self.api_key,
            "format": "json",
            "filter": filter_str,
            "field_list": field_list,
            "limit": limit,
        }

        query_string = urllib.parse.urlencode(params)
        return f"{self.base_url}/issues/?{query_string}"

    async def search_issue(
        self,
        series_name: str,
        year: Optional[int],
        issue_number: Optional[str],
        session: Optional[aiohttp.ClientSession] = None,
    ) -> List[Dict[str, Any]]:
        """Search for a comic issue on Comic Vine."""
        translated_name = await self._translate_series_name(series_name)
        if translated_name != series_name:
            logger.info("Translated '%s' -> '%s'", series_name, translated_name)

        search_url = self._build_search_url(
            series_name=translated_name,
            issue_number=issue_number,
            year=year,
        )

        logger.debug("Comic Vine search URL: %s", search_url)

        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        if session is None:
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                return await self._do_search(session, search_url, issue_number, year)
        else:
            return await self._do_search(session, search_url, issue_number, year)

    async def _do_search(
        self,
        session: aiohttp.ClientSession,
        search_url: str,
        issue_number: Optional[str],
        year: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Execute the actual search with the given session."""
        status, data = await self._get_json_with_retry(session, search_url)

        if status != 200:
            logger.warning("Comic Vine search failed (status=%d): %s", status, data)
            return []

        results = data.get("results") or []

        if issue_number:
            results = self._filter_by_issue_number(results, issue_number)

        if year:
            results = self._filter_by_year(results, year)

        if len(results) > 1:
            results = self._score_and_rank_results(results, year, issue_number)

        return results[:1] if results else []

    def _filter_by_issue_number(
        self,
        results: List[Dict[str, Any]],
        target_issue: str,
    ) -> List[Dict[str, Any]]:
        """Filter results by issue number."""
        filtered = []
        for result in results:
            result_issue = str(result.get("issue_number", "")).strip()
            if self._normalize_issue_number(result_issue) == self._normalize_issue_number(target_issue):
                filtered.append(result)
        return filtered

    def _filter_by_year(
        self,
        results: List[Dict[str, Any]],
        target_year: int,
    ) -> List[Dict[str, Any]]:
        """Filter results by cover date year (±1 tolerance)."""
        filtered = []
        for result in results:
            cover_date = result.get("cover_date") or ""
            if cover_date:
                try:
                    result_year = int(cover_date[:4])
                    if abs(result_year - target_year) <= 1:
                        filtered.append(result)
                except ValueError:
                    continue
        return filtered

    def _score_and_rank_results(
        self,
        results: List[Dict[str, Any]],
        target_year: Optional[int],
        target_issue: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Score and rank results to find best match.

        When target_year is None, all results pass with score 0.
        """
        scored = []
        for result in results:
            score = 0
            cover_date = result.get("cover_date") or ""
            if cover_date and target_year:
                try:
                    result_year = int(cover_date[:4])
                    if result_year == target_year:
                        score += 100
                    elif abs(result_year - target_year) <= 1:
                        score += 50
                except ValueError:
                    pass

            if target_year is None or score >= self.min_match_score:
                scored.append((score, result))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored]

    def _normalize_issue_number(self, issue: str) -> str:
        """Normalize issue number for comparison."""
        match = re.search(r"(\d+)", issue.strip())
        return match.group(1) if match else issue

    def extract_credits(self, credits: List[Dict[str, Any]]) -> Dict[str, str]:
        """Extract writer, artist, colorist, etc. from person credits."""
        roles = {
            "writer": [],
            "penciller": [],
            "inker": [],
            "colorist": [],
            "letterer": [],
            "editor": [],
            "cover_artist": [],
        }

        for credit in credits:
            name = credit.get("name", "")
            role_list = credit.get("role", "").lower().split(",")

            for role in role_list:
                role = role.strip()
                if not role:
                    continue

                if role in roles:
                    roles[role].append(name)
                elif "writer" in role:
                    roles["writer"].append(name)
                elif "penciler" in role:
                    roles["penciller"].append(name)
                elif "artist" in role:
                    roles["penciller"].append(name)
                elif "ink" in role:
                    roles["inker"].append(name)
                elif "color" in role:
                    roles["colorist"].append(name)
                elif "letter" in role:
                    roles["letterer"].append(name)
                elif "cover" in role:
                    roles["cover_artist"].append(name)

        return {k: ", ".join(v) for k, v in roles.items() if v}

    def map_to_comic_metadata(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Map Comic Vine result to our metadata format."""
        volume = result.get("volume", {}) or {}
        image = result.get("image", {}) or {}
        credits = result.get("person_credits") or []

        credits_data = self.extract_credits(credits)

        cover_url = image.get("super_url") or image.get("medium_url") or image.get("thumb_url") or ""

        year_str = result.get("cover_date", "") or ""
        year = None
        month = None
        if year_str:
            try:
                parts = year_str.split("-")
                year = int(parts[0])
                if len(parts) > 1:
                    month = int(parts[1])
            except ValueError:
                pass

        publisher_val = volume.get("publisher")
        publisher = ""
        if isinstance(publisher_val, dict):
            publisher = publisher_val.get("name", "")
        elif isinstance(publisher_val, str):
            publisher = publisher_val

        metadata = {
            "title": result.get("name") or "",
            "series": volume.get("name") or "",
            "issue_number": str(result.get("issue_number", "")),
            "year": year,
            "month": month,
            "publisher": publisher,
            "description": result.get("description", ""),
            "cover_image_url": cover_url,
            "author": credits_data.get("writer", ""),
            "penciller": credits_data.get("penciller", ""),
            "inker": credits_data.get("inker", ""),
            "colorist": credits_data.get("colorist", ""),
            "letterer": credits_data.get("letterer", ""),
            "editor": credits_data.get("editor", ""),
            "cover_artist": credits_data.get("cover_artist", ""),
            "comic_vine_id": result.get("id"),
            "comic_vine_url": result.get("site_detail_url", ""),
        }

        return {k: v for k, v in metadata.items() if v}