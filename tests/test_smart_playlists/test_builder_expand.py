import unittest
from app.features.smart_playlists.builder import SmartPlaylistBuilder, field


class TestBuilderExpand(unittest.TestCase):
    def test_with_subgenres_returns_rules(self):
        """with_subgenres() deve retornar lista de Rules."""
        rules = field("genre").with_subgenres("electronic")
        self.assertGreater(len(rules), 0)
        self.assertEqual(rules[0].field, "genre")
        self.assertEqual(rules[0].operator, "is")

    def test_with_subgenres_integration(self):
        """with_subgenres() deve funcionar com any_of()."""
        builder = SmartPlaylistBuilder("Test")
        rules = field("genre").with_subgenres("electronic")
        builder.any_of(*rules)
        definition = builder.build()
        self.assertGreater(len(definition.any_rules), 0)
