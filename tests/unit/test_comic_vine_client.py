#!/usr/bin/env python3
"""Unit tests for Comic Vine client."""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import unquote

from app.metadata.comic_vine import ComicVineClient


class TestComicVineClientInit(unittest.TestCase):
    def test_init_with_all_parameters(self):
        client = ComicVineClient(
            api_key="test_key",
            translate=False,
            api_delay_seconds=2.0,
            timeout_seconds=30.0,
            min_match_score=80,
        )
        self.assertEqual(client.api_key, "test_key")
        self.assertFalse(client.translate)
        self.assertEqual(client.api_delay_seconds, 2.0)
        self.assertEqual(client.timeout_seconds, 30.0)
        self.assertEqual(client.min_match_score, 80)

    def test_init_with_default_parameters(self):
        client = ComicVineClient(api_key="test_key")
        self.assertTrue(client.translate)
        self.assertEqual(client.api_delay_seconds, 1.0)
        self.assertEqual(client.timeout_seconds, 15.0)
        self.assertEqual(client.min_match_score, 75)


class TestTranslateSeriesName(unittest.TestCase):
    def test_translate_when_disabled(self):
        client = ComicVineClient(api_key="test", translate=False)
        result = asyncio.run(client._translate_series_name("Batman"))
        self.assertEqual(result, "Batman")

    def test_translate_when_enabled_but_no_translator_available(self):
        client = ComicVineClient(api_key="test", translate=True)
        with patch.dict("sys.modules", {"deep_translator": None}):
            result = asyncio.run(client._translate_series_name("Batman"))
            self.assertEqual(result, "Batman")

    def test_translate_calls_google_translator(self):
        client = ComicVineClient(api_key="test", translate=True)
        mock_translator = MagicMock()
        mock_translator.translate.return_value = "Batman"
        with patch.dict("sys.modules", {"deep_translator": MagicMock(GoogleTranslator=lambda **kw: mock_translator)}):
            result = asyncio.run(client._translate_series_name("Homem Morcego"))
            self.assertEqual(result, "Batman")
            mock_translator.translate.assert_called_once_with("Homem Morcego")


class TestBuildSearchUrl(unittest.TestCase):
    def test_url_with_only_series_name(self):
        client = ComicVineClient(api_key="test_key")
        url = unquote(client._build_search_url(series_name="Batman"))
        self.assertIn("api_key=test_key", url)
        self.assertIn("filter=name:Batman", url)
        self.assertIn("format=json", url)

    def test_url_with_series_name_and_issue_number(self):
        client = ComicVineClient(api_key="test_key")
        url = unquote(client._build_search_url(series_name="Batman", issue_number="100"))
        self.assertIn("filter=name:Batman+#100", url)

    def test_url_with_year_filter(self):
        client = ComicVineClient(api_key="test_key")
        url = unquote(client._build_search_url(series_name="Batman", year=2020))
        self.assertIn("cover_date:2020", url)

    def test_url_removes_parentheses(self):
        client = ComicVineClient(api_key="test_key")
        url = client._build_search_url(series_name="Batman (Elseworlds)")
        self.assertNotIn("(", url)
        self.assertNotIn(")", url)

    def test_url_with_custom_limit(self):
        client = ComicVineClient(api_key="test_key")
        url = client._build_search_url(series_name="Batman", limit=20)
        self.assertIn("limit=20", url)

    def test_url_includes_field_list(self):
        client = ComicVineClient(api_key="test_key")
        url = client._build_search_url(series_name="Batman")
        self.assertIn("field_list=", url)


class TestNormalizeIssueNumber(unittest.TestCase):
    def test_normalize_simple_number(self):
        client = ComicVineClient(api_key="test")
        self.assertEqual(client._normalize_issue_number("100"), "100")

    def test_normalize_with_hash(self):
        client = ComicVineClient(api_key="test")
        self.assertEqual(client._normalize_issue_number("#100"), "100")

    def test_normalize_with_text(self):
        client = ComicVineClient(api_key="test")
        self.assertEqual(client._normalize_issue_number("100AU"), "100")

    def test_normalize_empty_string(self):
        client = ComicVineClient(api_key="test")
        self.assertEqual(client._normalize_issue_number(""), "")


class TestFilterByIssueNumber(unittest.TestCase):
    def setUp(self):
        self.client = ComicVineClient(api_key="test")
        self.results = [
            {"issue_number": "100"},
            {"issue_number": "101"},
            {"issue_number": "#100"},
            {"issue_number": "100AU"},
        ]

    def test_filter_exact_match(self):
        filtered = self.client._filter_by_issue_number(self.results, "100")
        self.assertEqual(len(filtered), 3)

    def test_filter_no_match(self):
        filtered = self.client._filter_by_issue_number(self.results, "999")
        self.assertEqual(len(filtered), 0)


class TestFilterByYear(unittest.TestCase):
    def setUp(self):
        self.client = ComicVineClient(api_key="test")
        self.results = [
            {"cover_date": "2020-05-01"},
            {"cover_date": "2021-06-15"},
            {"cover_date": "2018-03-20"},
            {"cover_date": "2022-01-10"},
            {"cover_date": ""},
        ]

    def test_filter_exact_year_match(self):
        filtered = self.client._filter_by_year(self.results, 2020)
        self.assertEqual(len(filtered), 2)

    def test_filter_within_one_year_tolerance(self):
        filtered = self.client._filter_by_year(self.results, 2020)
        years = [int(r["cover_date"][:4]) for r in filtered if r["cover_date"]]
        self.assertIn(2020, years)
        self.assertIn(2021, years)


class TestScoreAndRankResults(unittest.TestCase):
    def setUp(self):
        self.client = ComicVineClient(api_key="test", min_match_score=50)

    def test_exact_year_match_scores_higher(self):
        results = [
            {"cover_date": "2020-05-01", "name": "exact"},
            {"cover_date": "2021-06-15", "name": "off_by_one"},
        ]
        scored = self.client._score_and_rank_results(results, 2020, None)
        self.assertEqual(scored[0]["name"], "exact")

    def test_year_off_by_one_scores_lower(self):
        results = [
            {"cover_date": "2019-05-01", "name": "off_by_one"},
            {"cover_date": "2020-05-01", "name": "exact"},
        ]
        scored = self.client._score_and_rank_results(results, 2020, None)
        self.assertEqual(scored[0]["name"], "exact")
        self.assertEqual(scored[1]["name"], "off_by_one")

    def test_results_below_min_score_filtered(self):
        client = ComicVineClient(api_key="test", min_match_score=75)
        results = [
            {"cover_date": "2019-05-01", "name": "low_score"},
            {"cover_date": "2020-05-01", "name": "high_score"},
        ]
        scored = client._score_and_rank_results(results, 2020, None)
        self.assertEqual(len(scored), 1)
        self.assertEqual(scored[0]["name"], "high_score")


class TestExtractCredits(unittest.TestCase):
    def setUp(self):
        self.client = ComicVineClient(api_key="test")

    def test_extract_writer(self):
        credits = [{"name": "John Byrne", "role": "writer"}]
        result = self.client.extract_credits(credits)
        self.assertEqual(result["writer"], "John Byrne")

    def test_extract_multiple_writers(self):
        credits = [
            {"name": "John Byrne", "role": "writer"},
            {"name": "Jane Doe", "role": "writer"},
        ]
        result = self.client.extract_credits(credits)
        self.assertEqual(result["writer"], "John Byrne, Jane Doe")

    def test_extract_penciller(self):
        credits = [{"name": "Jack Kirby", "role": "penciler"}]
        result = self.client.extract_credits(credits)
        self.assertEqual(result["penciller"], "Jack Kirby")

    def test_extract_artist_as_penciller(self):
        credits = [{"name": "Steve Ditko", "role": "artist"}]
        result = self.client.extract_credits(credits)
        self.assertEqual(result["penciller"], "Steve Ditko")

    def test_extract_cover_artist(self):
        credits = [{"name": "Alex Ross", "role": "cover"}]
        result = self.client.extract_credits(credits)
        self.assertEqual(result["cover_artist"], "Alex Ross")

    def test_extract_multiple_roles(self):
        credits = [
            {"name": "Alan Moore", "role": "writer"},
            {"name": "Dave Gibbons", "role": "artist"},
            {"name": "John Romita", "role": "penciler"},
        ]
        result = self.client.extract_credits(credits)
        self.assertEqual(result["writer"], "Alan Moore")
        self.assertEqual(result["penciller"], "Dave Gibbons, John Romita")


class TestMapToComicMetadata(unittest.TestCase):
    def setUp(self):
        self.client = ComicVineClient(api_key="test")

    def test_map_basic_fields(self):
        result = {
            "name": "Batman #100",
            "issue_number": "100",
            "cover_date": "2020-05-01",
            "description": "Test description",
            "volume": {"name": "Batman"},
            "image": {"super_url": "http://example.com/cover.jpg"},
            "id": 12345,
            "site_detail_url": "http://comicvine.com/batman-100",
        }
        metadata = self.client.map_to_comic_metadata(result)
        self.assertEqual(metadata["title"], "Batman #100")
        self.assertEqual(metadata["series"], "Batman")
        self.assertEqual(metadata["issue_number"], "100")
        self.assertEqual(metadata["year"], 2020)
        self.assertEqual(metadata["month"], 5)
        self.assertEqual(metadata["cover_image_url"], "http://example.com/cover.jpg")
        self.assertEqual(metadata["comic_vine_id"], 12345)
        self.assertEqual(metadata["comic_vine_url"], "http://comicvine.com/batman-100")

    def test_map_publisher_from_dict(self):
        result = {
            "name": "Test",
            "volume": {
                "name": "Batman",
                "publisher": {"name": "DC Comics"},
            },
        }
        metadata = self.client.map_to_comic_metadata(result)
        self.assertEqual(metadata["publisher"], "DC Comics")

    def test_map_publisher_from_string(self):
        result = {
            "name": "Test",
            "volume": {
                "name": "Batman",
                "publisher": "DC Comics",
            },
        }
        metadata = self.client.map_to_comic_metadata(result)
        self.assertEqual(metadata["publisher"], "DC Comics")

    def test_map_credits(self):
        result = {
            "name": "Test",
            "volume": {},
            "person_credits": [
                {"name": "Frank Miller", "role": "writer"},
                {"name": "John Romita", "role": "penciler"},
            ],
        }
        metadata = self.client.map_to_comic_metadata(result)
        self.assertEqual(metadata["author"], "Frank Miller")
        self.assertEqual(metadata["penciller"], "John Romita")

    def test_map_excludes_empty_values(self):
        result = {
            "name": "Test",
            "volume": {},
        }
        metadata = self.client.map_to_comic_metadata(result)
        self.assertNotIn("year", metadata)
        self.assertNotIn("month", metadata)
        self.assertNotIn("author", metadata)

    def test_map_fallback_image_urls(self):
        result = {
            "name": "Test",
            "volume": {},
            "image": {"medium_url": "http://example.com/medium.jpg"},
        }
        metadata = self.client.map_to_comic_metadata(result)
        self.assertEqual(metadata["cover_image_url"], "http://example.com/medium.jpg")


class TestRateLimiting(unittest.TestCase):
    def test_rate_limit_initializes_last_request_time(self):
        client = ComicVineClient(api_key="test", api_delay_seconds=1.0)
        self.assertEqual(client._last_request_time, 0.0)

    def test_rate_limit_uses_configured_delay(self):
        client = ComicVineClient(api_key="test", api_delay_seconds=2.5)
        self.assertEqual(client.api_delay_seconds, 2.5)


class TestRateLimitingAsync(unittest.IsolatedAsyncioTestCase):
    async def test_rate_limit_actually_delays(self):
        client = ComicVineClient(api_key="test", api_delay_seconds=0.2)
        client._last_request_time = time.time()
        start = time.time()
        await client._rate_limit()
        elapsed = time.time() - start
        self.assertGreaterEqual(elapsed, 0.15)

    async def test_rate_limit_no_delay_if_enough_time_passed(self):
        client = ComicVineClient(api_key="test", api_delay_seconds=0.01)
        client._last_request_time = time.time() - 10
        start = time.time()
        await client._rate_limit()
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.05)


class TestGetJsonWithRetryAsync(unittest.IsolatedAsyncioTestCase):
    async def test_successful_request_returns_data(self):
        client = ComicVineClient(api_key="test", api_delay_seconds=0)
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"results": [{"name": "Test"}]})
        mock_response.headers = {}

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        status, data = await client._get_json_with_retry(mock_session, "http://test.com")
        self.assertEqual(status, 200)
        self.assertEqual(data["results"][0]["name"], "Test")

    async def test_retries_on_500_error(self):
        client = ComicVineClient(api_key="test", api_delay_seconds=0)
        mock_response_fail = AsyncMock()
        mock_response_fail.status = 500
        mock_response_fail.headers = {}

        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.json = AsyncMock(return_value={"results": [{"name": "Test"}]})
        mock_response_success.headers = {}

        mock_cm_fail = AsyncMock()
        mock_cm_fail.__aenter__ = AsyncMock(return_value=mock_response_fail)
        mock_cm_fail.__aexit__ = AsyncMock(return_value=None)

        mock_cm_success = AsyncMock()
        mock_cm_success.__aenter__ = AsyncMock(return_value=mock_response_success)
        mock_cm_success.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=[mock_cm_fail, mock_cm_success])

        status, data = await client._get_json_with_retry(mock_session, "http://test.com", max_retries=1)
        self.assertEqual(status, 200)

    async def test_returns_429_on_rate_limit_without_retry_after(self):
        client = ComicVineClient(api_key="test", api_delay_seconds=0)
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.headers = {"Retry-After": "30"}

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        status, data = await client._get_json_with_retry(mock_session, "http://test.com", max_retries=0)
        self.assertEqual(status, 429)


class TestSearchIssueAsync(unittest.IsolatedAsyncioTestCase):
    async def test_search_issue_returns_results(self):
        client = ComicVineClient(api_key="test", translate=False, api_delay_seconds=0)
        mock_data = {
            "results": [
                {
                    "name": "Batman #100",
                    "issue_number": "100",
                    "cover_date": "2020-05-01",
                    "volume": {"name": "Batman"},
                    "image": {"super_url": "http://example.com/cover.jpg"},
                    "id": 12345,
                }
            ]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_data)
        mock_response.headers = {}

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        results = await client.search_issue(
            series_name="Batman",
            year=2020,
            issue_number="100",
            session=mock_session,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Batman #100")

    async def test_search_issue_returns_empty_on_error(self):
        client = ComicVineClient(api_key="test", translate=False, api_delay_seconds=0)

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.json = AsyncMock(return_value={"error": "Server Error"})
        mock_response.headers = {}

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        results = await client.search_issue(
            series_name="Batman",
            year=None,
            issue_number=None,
            session=mock_session,
        )

        self.assertEqual(len(results), 0)

    async def test_search_issue_filters_by_issue_number(self):
        client = ComicVineClient(api_key="test", translate=False, api_delay_seconds=0)
        mock_data = {
            "results": [
                {"issue_number": "100", "name": "Batman #100"},
                {"issue_number": "101", "name": "Batman #101"},
            ]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_data)
        mock_response.headers = {}

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        results = await client.search_issue(
            series_name="Batman",
            year=None,
            issue_number="100",
            session=mock_session,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["issue_number"], "100")

    async def test_search_issue_uses_translation_when_enabled(self):
        client = ComicVineClient(api_key="test", translate=True, api_delay_seconds=0)

        mock_translator = MagicMock()
        mock_translator.translate.return_value = "Homem Aranha"

        with patch.dict("sys.modules", {"deep_translator": MagicMock(GoogleTranslator=lambda **kw: mock_translator)}):
            mock_data = {"results": [{"name": "Spider-Man"}]}
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_data)
            mock_response.headers = {}

            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_cm)

            await client.search_issue(
                series_name="Homem Aranha",
                year=None,
                issue_number=None,
                session=mock_session,
            )

            mock_translator.translate.assert_called_once()


if __name__ == "__main__":
    unittest.main()