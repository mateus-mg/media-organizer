#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from app.features.smart_playlists.builder import SmartPlaylistBuilder, FieldCondition

b = SmartPlaylistBuilder("Test")
rules = FieldCondition("genre").with_subgenres("electronic")
b.any_of(*rules)
d = b.build()

print(f"Any rules count: {len(d.any_rules)}")
if d.any_rules:
    print(f"First rule: {d.any_rules[0]}")
else:
    print("First rule: None")

rules2 = FieldCondition("genre").with_subgenres("unknown_genre")
print(f"Unknown genre rules: {len(rules2)}")
if rules2:
    print(f"Unknown genre first rule: {rules2[0]}")

for i, rule in enumerate(d.any_rules):
    assert rule.operator == "is", f"Rule {i} operator should be 'is', got {rule.operator}"
    assert rule.field == "genre", f"Rule {i} field should be 'genre', got {rule.field}"
    assert isinstance(rule.value, str), f"Rule {i} value should be string, got {type(rule.value)}"

rules3 = FieldCondition("genre").with_subgenres("nonexistent_xyz")
assert len(rules3) == 1, f"Fallback should return 1 rule, got {len(rules3)}"
assert rules3[0].value == "nonexistent_xyz", f"Fallback value should be 'nonexistent_xyz', got {rules3[0].value}"

print("\nAll QA checks passed!")
