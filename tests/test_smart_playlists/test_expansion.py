import unittest
import json
import tempfile
import os
from app.features.smart_playlists.expansion import GenreExpander


class TestGenreExpander(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.hierarchy_path = os.path.join(self.temp_dir, "test_hierarchy.json")
        with open(self.hierarchy_path, 'w') as f:
            json.dump({
                "version": 1,
                "updated_at": "2026-01-01T00:00:00",
                "hierarchy": {
                    "electronic": ["house", "techno", "trance"],
                    "rock": ["alternative", "punk", "metal"]
                }
            }, f)
        self.expander = GenreExpander(self.hierarchy_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_expand_returns_subgenres(self):
        """expand() deve retornar lista de subgêneros."""
        result = self.expander.expand("electronic")
        self.assertEqual(len(result), 3)
        self.assertIn("house", result)
        self.assertIn("techno", result)

    def test_infer_parent_finds_match(self):
        """infer_parent() deve encontrar pai por substring."""
        self.assertEqual(self.expander.infer_parent("Deep House"), "electronic")
        self.assertEqual(self.expander.infer_parent("Alternative Rock"), "rock")

    def test_expand_unknown_returns_empty(self):
        """expand() com gênero desconhecido retorna lista vazia."""
        result = self.expander.expand("unknown_genre")
        self.assertEqual(result, [])

    def test_case_insensitive_matching(self):
        """Matching deve ser case insensitive."""
        self.assertEqual(self.expander.expand("ELECTRONIC"), ["house", "techno", "trance"])
        self.assertEqual(self.expander.infer_parent("deep house"), "electronic")
