import json
import os
import tempfile
import unittest

from app.features.smart_playlists.builder import SmartPlaylistBuilder, field
from app.features.smart_playlists.expansion import GenreExpander
from app.features.smart_playlists.query_parser import QueryStringParser


class TestIntegration(unittest.TestCase):
    """Integration tests for smart playlists: parser → builder → expansion."""

    def _create_temp_hierarchy(self, hierarchy_data):
        """Create a temporary hierarchy file and return its path."""
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump({
            "version": 1,
            "updated_at": "2026-01-01T00:00:00",
            "hierarchy": hierarchy_data,
        }, f)
        f.close()
        return f.name

    def test_end_to_end_parser_builder_expansion(self):
        """Fluxo completo: parser com :expand → builder → definição válida."""
        hierarchy_path = self._create_temp_hierarchy({
            "electronic": ["house", "techno", "trance"],
        })
        try:
            # Parse query com expand
            parser = QueryStringParser()
            definition = parser.parse("genre:electronic:expand")

            # Verificar que gerou regras (deve ter 3 subgêneros)
            self.assertGreater(len(definition.any_rules), 0)

            # Criar builder e adicionar regras
            builder = SmartPlaylistBuilder("Electronic Playlist")
            for rule in definition.any_rules:
                builder.any_of(rule)

            # Build final
            result = builder.build()
            self.assertEqual(result.name, "Electronic Playlist")
            self.assertGreater(len(result.any_rules), 0)

            # Verificar que todas as regras têm field=genre e operator=is
            for rule in result.any_rules:
                self.assertEqual(rule.field, "genre")
                self.assertEqual(rule.operator, "is")
        finally:
            os.unlink(hierarchy_path)

    def test_builder_with_subgenres_flow(self):
        """Fluxo: field().with_subgenres() → any_of() → build()."""
        hierarchy_path = self._create_temp_hierarchy({
            "rock": ["hard rock", "progressive rock", "alternative rock"],
        })
        try:
            builder = SmartPlaylistBuilder("Test")
            rules = field("genre").with_subgenres("rock")
            builder.any_of(*rules)
            definition = builder.build()

            self.assertGreater(len(definition.any_rules), 0)
            for rule in definition.any_rules:
                self.assertEqual(rule.field, "genre")
                self.assertEqual(rule.operator, "is")
        finally:
            os.unlink(hierarchy_path)

    def test_special_characters_in_genre(self):
        """Gêneros com caracteres especiais (R&B, Drum & Bass)."""
        hierarchy_path = self._create_temp_hierarchy({
            "r&b": ["contemporary r&b", "neo soul"],
            "drum & bass": ["liquid funk", "neurofunk"],
        })
        try:
            expander = GenreExpander(hierarchy_path)

            # Testar que não quebra com caracteres especiais
            result = expander.expand("R&B")
            self.assertIsInstance(result, list)

            result = expander.expand("Drum & Bass")
            self.assertIsInstance(result, list)

            parent = expander.infer_parent("liquid funk")
            self.assertEqual(parent, "drum & bass")
        finally:
            os.unlink(hierarchy_path)

    def test_case_insensitivity(self):
        """Testar case insensitive em todas as operações."""
        hierarchy_path = self._create_temp_hierarchy({
            "electronic": ["deep house", "techno"],
        })
        try:
            expander = GenreExpander(hierarchy_path)

            # Expand com diferentes cases
            r1 = expander.expand("electronic")
            r2 = expander.expand("ELECTRONIC")
            r3 = expander.expand("Electronic")
            self.assertEqual(r1, r2)
            self.assertEqual(r2, r3)

            # Infer com diferentes cases
            p1 = expander.infer_parent("Deep House")
            p2 = expander.infer_parent("deep house")
            p3 = expander.infer_parent("DEEP HOUSE")
            self.assertEqual(p1, p2)
            self.assertEqual(p2, p3)
        finally:
            os.unlink(hierarchy_path)

    def test_unknown_genre_handling(self):
        """Comportamento com gênero inexistente."""
        hierarchy_path = self._create_temp_hierarchy({})
        try:
            expander = GenreExpander(hierarchy_path)

            # Expand deve retornar lista vazia
            result = expander.expand("unknown_genre_xyz")
            self.assertEqual(result, [])

            # Infer deve retornar None
            parent = expander.infer_parent("Totally Unknown Genre")
            self.assertIsNone(parent)
        finally:
            os.unlink(hierarchy_path)

    def test_multiple_expand_in_query(self):
        """Múltiplos :expand na mesma query."""
        hierarchy_path = self._create_temp_hierarchy({
            "electronic": ["house", "techno"],
        })
        try:
            parser = QueryStringParser()

            # Query com múltiplos campos (um com expand, outro sem)
            definition = parser.parse("genre:electronic:expand artist:Beatles")
            # Deve funcionar sem erro
            self.assertGreater(len(definition.any_rules), 0)
            self.assertEqual(len(definition.all_rules), 1)
            self.assertEqual(definition.all_rules[0].field, "artist")
            self.assertEqual(definition.all_rules[0].value, "Beatles")
        finally:
            os.unlink(hierarchy_path)

    def test_empty_hierarchy_handling(self):
        """Comportamento com hierarquia vazia."""
        hierarchy_path = self._create_temp_hierarchy({})
        try:
            expander = GenreExpander(hierarchy_path)
            result = expander.expand("electronic")
            self.assertEqual(result, [])
        finally:
            os.unlink(hierarchy_path)

    def test_parser_expand_fallback_to_single_rule(self):
        """Quando expand retorna vazio, parser deve criar uma única regra."""
        hierarchy_path = self._create_temp_hierarchy({})
        try:
            parser = QueryStringParser()
            definition = parser.parse("genre:unknown:expand")

            # Com hierarquia vazia, deve criar uma única regra is=unknown
            self.assertEqual(len(definition.all_rules), 1)
            self.assertEqual(len(definition.any_rules), 0)
            self.assertEqual(definition.all_rules[0].operator, "is")
            self.assertEqual(definition.all_rules[0].field, "genre")
            self.assertEqual(definition.all_rules[0].value, "unknown")
        finally:
            os.unlink(hierarchy_path)

    def test_full_playlist_definition_serialization(self):
        """Testar serialização NSP completa após fluxo inteiro."""
        hierarchy_path = self._create_temp_hierarchy({
            "rock": ["classic rock", "hard rock"],
        })
        try:
            parser = QueryStringParser()
            parsed = parser.parse("genre:rock:expand")

            builder = SmartPlaylistBuilder("Rock Mix")
            for rule in parsed.any_rules:
                builder.any_of(rule)
            builder.all_of(
                field("year").in_the_range(1970, 1989),
            ).sort("-rating", "title").limit(100).public(True)

            definition = builder.build()
            nsp = definition.to_nsp_dict()

            self.assertEqual(nsp["name"], "Rock Mix")
            self.assertTrue(nsp["public"])
            self.assertEqual(nsp["sort"], "-rating,title")
            self.assertEqual(nsp["limit"], 100)
            self.assertIn("any", nsp)
            self.assertIn("all", nsp)
            self.assertEqual(len(nsp["any"]), 2)
            self.assertEqual(len(nsp["all"]), 1)
        finally:
            os.unlink(hierarchy_path)

    def test_builder_with_subgenres_empty_hierarchy(self):
        """with_subgenres com hierarquia vazia deve retornar uma regra única."""
        hierarchy_path = self._create_temp_hierarchy({})
        try:
            rules = field("genre").with_subgenres("jazz")
            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0].field, "genre")
            self.assertEqual(rules[0].operator, "is")
            self.assertEqual(rules[0].value, "jazz")
        finally:
            os.unlink(hierarchy_path)

    def test_find_matches_with_special_characters(self):
        """find_matches deve funcionar com caracteres especiais no padrão."""
        hierarchy_path = self._create_temp_hierarchy({
            "electronic": ["drum & bass", "d&b", "r&b influenced"],
        })
        try:
            expander = GenreExpander(hierarchy_path)
            matches = expander.find_matches("&")
            self.assertEqual(len(matches), 3)
            self.assertIn("drum & bass", matches)
            self.assertIn("d&b", matches)
            self.assertIn("r&b influenced", matches)
        finally:
            os.unlink(hierarchy_path)


if __name__ == "__main__":
    unittest.main()
