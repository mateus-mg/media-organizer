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

    def test_rule_to_nsp_dict(self):
        r = Rule("eq", "artist", "Test Artist")
        self.assertEqual(r.to_nsp_dict(), {"eq": {"artist": "Test Artist"}})

    def test_any_rules_in_payload(self):
        d = SmartPlaylistDefinition(
            name="Mixed",
            any_rules=[
                Rule("startsWith", "title", "A"),
                Rule("endsWith", "title", "Z"),
            ],
        )
        nsp = d.to_nsp_dict()
        self.assertIn("any", nsp)
        self.assertEqual(nsp["any"], [
            {"startsWith": {"title": "A"}},
            {"endsWith": {"title": "Z"}},
        ])
        self.assertNotIn("all", nsp)

    def test_limit_percent_serialization(self):
        d = SmartPlaylistDefinition(name="Percent", limit_percent=25)
        nsp = d.to_nsp_dict()
        self.assertEqual(nsp["limitPercent"], 25)
        self.assertNotIn("limit", nsp)

    def test_order_field(self):
        d = SmartPlaylistDefinition(name="Ordered", order="asc")
        nsp = d.to_nsp_dict()
        self.assertEqual(nsp["order"], "asc")

    def test_comment_field(self):
        d = SmartPlaylistDefinition(name="Commented", comment="My playlist")
        nsp = d.to_nsp_dict()
        self.assertEqual(nsp["comment"], "My playlist")

    def test_public_true(self):
        d = SmartPlaylistDefinition(name="Public", public=True)
        nsp = d.to_nsp_dict()
        self.assertTrue(nsp["public"])

    def test_empty_rules_omitted(self):
        d = SmartPlaylistDefinition(
            name="Empty",
            all_rules=[],
            any_rules=[],
        )
        nsp = d.to_nsp_dict()
        self.assertNotIn("all", nsp)
        self.assertNotIn("any", nsp)
