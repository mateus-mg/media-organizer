import unittest
from app.features.smart_playlists.query_parser import QueryStringParser


class TestQueryStringParser(unittest.TestCase):
    def setUp(self):
        self.parser = QueryStringParser()

    def test_simple_contains(self):
        d = self.parser.parse("genre:rock")
        self.assertEqual(len(d.all_rules), 1)
        self.assertEqual(d.all_rules[0].operator, "contains")
        self.assertEqual(d.all_rules[0].field, "genre")
        self.assertEqual(d.all_rules[0].value, "rock")

    def test_explicit_operator(self):
        d = self.parser.parse("year:gt:2020")
        self.assertEqual(d.all_rules[0].operator, "gt")
        self.assertEqual(d.all_rules[0].value, 2020)

    def test_multiple_and(self):
        d = self.parser.parse("genre:rock year:gt:2020")
        self.assertEqual(len(d.all_rules), 2)
        self.assertEqual(d.all_rules[0].field, "genre")
        self.assertEqual(d.all_rules[1].field, "year")

    def test_quoted_value(self):
        d = self.parser.parse('artist:"Daft Punk"')
        self.assertEqual(d.all_rules[0].value, "Daft Punk")

    def test_boolean(self):
        d = self.parser.parse("loved:true")
        self.assertEqual(d.all_rules[0].value, True)
        self.assertEqual(d.all_rules[0].operator, "is")

    def test_invalid_field_raises(self):
        with self.assertRaises(ValueError):
            self.parser.parse("invalidfield:test")

    def test_empty_returns_empty(self):
        d = self.parser.parse("")
        self.assertEqual(len(d.all_rules), 0)

    def test_number_default_operator_is(self):
        d = self.parser.parse("year:2020")
        self.assertEqual(d.all_rules[0].operator, "is")
        self.assertEqual(d.all_rules[0].value, 2020)

    def test_explicit_contains_operator(self):
        d = self.parser.parse("artist:contains:John")
        self.assertEqual(d.all_rules[0].operator, "contains")
        self.assertEqual(d.all_rules[0].value, "John")
