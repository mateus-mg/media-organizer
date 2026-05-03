import unittest
from app.features.smart_playlists.query_parser import QueryStringParser


class TestQueryParserExpand(unittest.TestCase):
    def setUp(self):
        self.parser = QueryStringParser()

    def test_parse_expand_creates_multiple_rules(self):
        """Parser com :expand deve criar múltiplas regras em any_rules."""
        definition = self.parser.parse("genre:electronic:expand")
        self.assertGreater(len(definition.any_rules), 0)
        self.assertEqual(len(definition.all_rules), 0)

    def test_parse_without_expand_unchanged(self):
        """Parser sem :expand deve funcionar normalmente."""
        definition = self.parser.parse("genre:house")
        self.assertEqual(len(definition.all_rules), 1)
        self.assertEqual(len(definition.any_rules), 0)
        self.assertEqual(definition.all_rules[0].field, "genre")
        self.assertEqual(definition.all_rules[0].value, "house")

    def test_parse_expand_case_insensitive(self):
        """:expand deve funcionar com qualquer case."""
        definition1 = self.parser.parse("genre:ELECTRONIC:expand")
        definition2 = self.parser.parse("genre:electronic:expand")
        self.assertEqual(len(definition1.any_rules), len(definition2.any_rules))
