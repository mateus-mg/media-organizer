import unittest
from app.features.smart_playlists.builder import SmartPlaylistBuilder


class TestSmartPlaylistBuilder(unittest.TestCase):
    def test_basic_build(self):
        builder = SmartPlaylistBuilder("Test")
        d = builder.build()
        self.assertEqual(d.name, "Test")
        self.assertEqual(d.public, False)

    def test_fluent_chain(self):
        d = (
            SmartPlaylistBuilder("Rock 80s")
            .all_of(
                SmartPlaylistBuilder("Rock 80s").field("genre").contains("rock"),
                SmartPlaylistBuilder("Rock 80s").field("year").in_the_range(1980, 1989),
            )
            .sort("-rating", "title")
            .limit(50)
            .public(True)
            .build()
        )
        self.assertEqual(d.all_rules[0].field, "genre")
        self.assertEqual(d.sort, "-rating,title")
        self.assertEqual(d.limit, 50)
        self.assertTrue(d.public)

    def test_invalid_operator_raises(self):
        builder = SmartPlaylistBuilder("Test")
        with self.assertRaises(ValueError):
            builder.field("genre").gt("rock")  # gt não é operador de string

    def test_limit_and_limit_percent_mutually_exclusive(self):
        b = SmartPlaylistBuilder("Test").limit(50)
        self.assertEqual(b.build().limit, 50)
        self.assertIsNone(b.build().limit_percent)
        b2 = SmartPlaylistBuilder("Test").limit_percent(10)
        self.assertEqual(b2.build().limit_percent, 10)
        self.assertIsNone(b2.build().limit)

    def test_any_of(self):
        d = SmartPlaylistBuilder("Test").any_of(
            SmartPlaylistBuilder("Test").field("genre").contains("rock"),
            SmartPlaylistBuilder("Test").field("genre").contains("metal"),
        ).build()
        self.assertEqual(len(d.any_rules), 2)
        self.assertEqual(len(d.all_rules), 0)

    def test_order_validation(self):
        with self.assertRaises(ValueError):
            SmartPlaylistBuilder("Test").order("invalid")

    def test_comment_and_public(self):
        d = SmartPlaylistBuilder("Test").comment("My comment").public(False).build()
        self.assertEqual(d.comment, "My comment")
        self.assertFalse(d.public)
