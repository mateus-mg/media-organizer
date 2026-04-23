import unittest
from app.features.smart_playlists.definition import SmartPlaylistDefinition, Rule


class TestSmartPlaylistDefinition(unittest.TestCase):
    def test_to_nsp_dict_basic(self):
        d = SmartPlaylistDefinition(name="Test")
        self.assertEqual(d.to_nsp_dict()["name"], "Test")
        self.assertEqual(d.to_nsp_dict()["public"], False)

    def test_to_nsp_dict_with_rules(self):
        d = SmartPlaylistDefinition(
            name="Rock",
            all_rules=[Rule("contains", "genre", "rock")],
            sort="-rating",
            limit=50,
        )
        nsp = d.to_nsp_dict()
        self.assertEqual(nsp["all"], [{"contains": {"genre": "rock"}}])
        self.assertEqual(nsp["sort"], "-rating")
        self.assertEqual(nsp["limit"], 50)
        self.assertNotIn("any", nsp)
