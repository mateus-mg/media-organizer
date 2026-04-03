#!/usr/bin/env python3
"""Unit tests for music quality monitor."""

import json
import tempfile
import unittest
from pathlib import Path

from app.features.quality_monitor import MusicQualityMonitor


class TestMusicQualityMonitor(unittest.TestCase):
    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False,
                        indent=2), encoding="utf-8")

    def test_generate_report_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"

            organization_path = data_dir / "organization.json"
            registry_path = data_dir / "link_registry.json"

            organization_payload = {
                "media": {
                    "1": {
                        "organized_path": "/library/musics/Artist A/Album/01 - Song A.flac",
                        "metadata": {
                            "media_type": "music",
                            "title": "Song A",
                            "artist": "Artist A",
                            "album": "Album",
                            "genre": "Pop",
                            "genres": ["Pop"],
                        },
                    },
                    "2": {
                        "organized_path": "/library/musics/Artist B/Album/02 - Song B.flac",
                        "metadata": {
                            "media_type": "music",
                            "title": "Song B",
                            "artist": "Artist B",
                            "album": "Album",
                            "genre": "",
                            "genres": [],
                        },
                    },
                    "3": {
                        "organized_path": "/library/musics/Artist C/Album/03 - Song C.flac",
                        "metadata": {
                            "media_type": "music",
                            "title": "Song C",
                            "artist": "Artist C",
                            "album": "Album",
                            "genre": "Pop, Dance",
                            "genres": ["Pop", "Dance"],
                        },
                    },
                    "4": {
                        "metadata": {
                            "media_type": "lyrics",
                        }
                    },
                }
            }
            registry_payload = {
                "media": {
                    "1": {"metadata": {"media_type": "music"}},
                    "2": {"metadata": {"media_type": "lyrics"}},
                }
            }

            self._write_json(organization_path, organization_payload)
            self._write_json(registry_path, registry_payload)

            monitor = MusicQualityMonitor(
                data_dir=data_dir,
                organization_path=organization_path,
                link_registry_path=registry_path,
            )

            report = monitor.generate_report(top_n=3)
            metrics = report["metrics"]

            self.assertEqual(metrics["total_tracks"], 3)
            self.assertEqual(metrics["tracks_with_genre"], 2)
            self.assertEqual(metrics["tracks_missing_genre"], 1)
            self.assertEqual(metrics["multi_genre_tracks"], 1)
            self.assertEqual(metrics["registry_music_records"], 1)
            self.assertEqual(report["top_genres"][0][0], "Pop")
            self.assertEqual(report["top_genres"][0][1], 2)

    def test_playlist_like_token_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            organization_path = data_dir / "organization.json"

            organization_payload = {
                "media": {
                    "1": {
                        "organized_path": "/library/musics/Artist/Album/song.flac",
                        "metadata": {
                            "media_type": "music",
                            "title": "Song",
                            "artist": "Artist",
                            "album": "Album",
                            "genre": "Billboard Hot 100",
                            "genres": ["Billboard Hot 100"],
                        },
                    }
                }
            }

            self._write_json(organization_path, organization_payload)

            monitor = MusicQualityMonitor(
                data_dir=data_dir,
                organization_path=organization_path,
            )
            report = monitor.generate_report(top_n=5)
            self.assertGreaterEqual(
                report["metrics"]["playlist_like_tokens"], 1)

    def test_save_report_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            monitor = MusicQualityMonitor(data_dir=data_dir)

            report = {
                "timestamp": "2026-03-22T00:00:00",
                "metrics": {"total_tracks": 0},
                "top_genres": [],
            }
            output = data_dir / "quality_report_test.json"
            saved_path = monitor.save_report(report, output)

            self.assertTrue(saved_path.exists())
            loaded = json.loads(saved_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["metrics"]["total_tracks"], 0)


if __name__ == "__main__":
    unittest.main()
