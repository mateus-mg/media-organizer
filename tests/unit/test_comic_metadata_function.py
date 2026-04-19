#!/usr/bin/env python3
"""Unit tests for comic metadata functions."""

import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.metadata.metadata import enrich_comic_metadata_with_online_sources


class TestEnrichComicMetadata(unittest.TestCase):
    def test_returns_original_when_disabled(self):
        result = asyncio.run(
            enrich_comic_metadata_with_online_sources(
                file_path=Path("test.cbz"),
                existing_metadata={"series": "Batman", "year": "2020"},
                logger=MagicMock(),
                comic_vine_enabled=False,
                comic_vine_api_key="test_key",
            )
        )
        self.assertEqual(result["series"], "Batman")

    def test_returns_original_when_no_api_key(self):
        result = asyncio.run(
            enrich_comic_metadata_with_online_sources(
                file_path=Path("test.cbz"),
                existing_metadata={"series": "Batman", "year": "2020"},
                logger=MagicMock(),
                comic_vine_enabled=True,
                comic_vine_api_key="",
            )
        )
        self.assertEqual(result["series"], "Batman")

    def test_returns_original_when_no_series_name(self):
        result = asyncio.run(
            enrich_comic_metadata_with_online_sources(
                file_path=Path("test.cbz"),
                existing_metadata={"year": "2020"},
                logger=MagicMock(),
                comic_vine_enabled=True,
                comic_vine_api_key="test_key",
            )
        )
        self.assertNotIn("series", result)

    @patch("app.metadata.comic_vine.ComicVineClient")
    def test_calls_comic_vine_client_when_enabled(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_issue = AsyncMock(return_value=[{
            "name": "The Killing Joke",
            "issue_number": "1",
            "volume_name": {"name": "Batman"},
            "cover_date": "1988-05-00",
            "description": "<p>Classic story</p>",
        }])
        mock_client.map_to_comic_metadata = MagicMock(return_value={
            "description": "Classic story",
            "publisher": "DC Comics",
        })
        mock_client_class.return_value = mock_client

        result = asyncio.run(
            enrich_comic_metadata_with_online_sources(
                file_path=Path("test.cbz"),
                existing_metadata={"series": "Batman", "year": "1988", "issue_number": "1"},
                logger=MagicMock(),
                comic_vine_enabled=True,
                comic_vine_api_key="test_key",
            )
        )

        mock_client.search_issue.assert_called_once()
        call_args = mock_client.search_issue.call_args
        self.assertEqual(call_args.kwargs["series_name"], "Batman")
        self.assertEqual(call_args.kwargs["year"], 1988)
        self.assertEqual(call_args.kwargs["issue_number"], "1")

    @patch("app.metadata.comic_vine.ComicVineClient")
    def test_merges_enriched_metadata(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_issue = AsyncMock(return_value=[{
            "name": "The Killing Joke",
            "issue_number": "1",
            "volume_name": {"name": "Batman"},
            "cover_date": "1988-05-00",
            "description": "<p>Classic story</p>",
        }])
        mock_client.map_to_comic_metadata = MagicMock(return_value={
            "description": "Classic story",
            "publisher": "DC Comics",
        })
        mock_client_class.return_value = mock_client

        result = asyncio.run(
            enrich_comic_metadata_with_online_sources(
                file_path=Path("test.cbz"),
                existing_metadata={"series": "Batman", "year": "1988", "issue_number": "1"},
                logger=MagicMock(),
                comic_vine_enabled=True,
                comic_vine_api_key="test_key",
            )
        )

        self.assertEqual(result["description"], "Classic story")
        self.assertEqual(result["publisher"], "DC Comics")

    @patch("app.metadata.comic_vine.ComicVineClient")
    def test_preserves_existing_values(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_issue = AsyncMock(return_value=[{
            "name": "The Killing Joke",
            "issue_number": "1",
            "volume_name": {"name": "Batman"},
            "cover_date": "1988-05-00",
            "description": "<p>Classic story</p>",
        }])
        mock_client.map_to_comic_metadata = MagicMock(return_value={
            "description": "Online description",
            "publisher": "DC Comics",
            "series": "Batman",  # Should not override
        })
        mock_client_class.return_value = mock_client

        result = asyncio.run(
            enrich_comic_metadata_with_online_sources(
                file_path=Path("test.cbz"),
                existing_metadata={
                    "series": "Batman",
                    "description": "Original description",  # Should be preserved
                    "year": "1988",
                    "issue_number": "1"
                },
                logger=MagicMock(),
                comic_vine_enabled=True,
                comic_vine_api_key="test_key",
            )
        )

        self.assertEqual(result["description"], "Original description")
        self.assertEqual(result["series"], "Batman")

    @patch("app.metadata.comic_vine.ComicVineClient")
    def test_returns_original_on_no_results(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search_issue = AsyncMock(return_value=[])
        mock_client_class.return_value = mock_client

        metadata = {"series": "Batman", "year": "1988", "issue_number": "1"}
        result = asyncio.run(
            enrich_comic_metadata_with_online_sources(
                file_path=Path("test.cbz"),
                existing_metadata=metadata,
                logger=MagicMock(),
                comic_vine_enabled=True,
                comic_vine_api_key="test_key",
            )
        )

        self.assertEqual(result, metadata)


if __name__ == "__main__":
    unittest.main()