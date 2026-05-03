"""Fluent API builder for Navidrome smart playlists."""
from typing import Any, List, Optional

from .definition import Rule, SmartPlaylistDefinition
from .validators import validate_operator_for_field


class FieldCondition:
    """Represents a field in a smart playlist condition, providing operator methods."""

    def __init__(self, field: str):
        self.field = field

    def _rule(self, operator: str, value: Any) -> Rule:
        validate_operator_for_field(operator, self.field, value)
        return Rule(operator, self.field, value)

    def is_(self, value: Any) -> Rule:
        """Match exactly (is)."""
        return self._rule("is", value)

    def is_not(self, value: Any) -> Rule:
        """Match not equal (isNot)."""
        return self._rule("isNot", value)

    def gt(self, value: Any) -> Rule:
        """Greater than (gt)."""
        return self._rule("gt", value)

    def lt(self, value: Any) -> Rule:
        """Less than (lt)."""
        return self._rule("lt", value)

    def contains(self, value: Any) -> Rule:
        """String contains (contains)."""
        return self._rule("contains", value)

    def not_contains(self, value: Any) -> Rule:
        """String does not contain (notContains)."""
        return self._rule("notContains", value)

    def starts_with(self, value: Any) -> Rule:
        """String starts with (startsWith)."""
        return self._rule("startsWith", value)

    def ends_with(self, value: Any) -> Rule:
        """String ends with (endsWith)."""
        return self._rule("endsWith", value)

    def in_the_range(self, start: Any, end: Any) -> Rule:
        """In range inclusive (inTheRange)."""
        return self._rule("inTheRange", [start, end])

    def before(self, value: Any) -> Rule:
        """Before date (before)."""
        return self._rule("before", value)

    def after(self, value: Any) -> Rule:
        """After date (after)."""
        return self._rule("after", value)

    def in_the_last(self, days: int) -> Rule:
        """In the last N days (inTheLast)."""
        return self._rule("inTheLast", days)

    def not_in_the_last(self, days: int) -> Rule:
        """Not in the last N days (notInTheLast)."""
        return self._rule("notInTheLast", days)

    def in_playlist(self, playlist_id: str) -> Rule:
        """In playlist (inPlaylist)."""
        return self._rule("inPlaylist", playlist_id)

    def not_in_playlist(self, playlist_id: str) -> Rule:
        """Not in playlist (notInPlaylist)."""
        return self._rule("notInPlaylist", playlist_id)

    def with_subgenres(self, parent_genre: str) -> List[Rule]:
        """Expand parent_genre into multiple OR Rules for subgenres."""
        from .expansion import GenreExpander

        expander = GenreExpander()
        subgenres = expander.expand(parent_genre)

        if not subgenres:
            return [self.is_(parent_genre)]

        return [self.is_(subgenre) for subgenre in subgenres]


class SmartPlaylistBuilder:
    """Fluent builder for composing Navidrome smart playlists."""

    def __init__(self, name: str):
        self._definition = SmartPlaylistDefinition(name=name)

    def field(self, field_name: str) -> FieldCondition:
        """Select a field to build a condition on."""
        return FieldCondition(field_name)

    def all_of(self, *rules: Rule) -> "SmartPlaylistBuilder":
        """Add rules that all must match (AND)."""
        self._definition.all_rules.extend(rules)
        return self

    def any_of(self, *rules: Rule) -> "SmartPlaylistBuilder":
        """Add rules where any can match (OR)."""
        self._definition.any_rules.extend(rules)
        return self

    def sort(self, *fields: str) -> "SmartPlaylistBuilder":
        """Set sort fields, e.g. sort('-rating', 'title')."""
        self._definition.sort = ",".join(fields)
        return self

    def order(self, order: str) -> "SmartPlaylistBuilder":
        """Set global order: 'asc' or 'desc'."""
        if order not in {"asc", "desc"}:
            raise ValueError("order must be 'asc' or 'desc'")
        self._definition.order = order
        return self

    def limit(self, limit: int) -> "SmartPlaylistBuilder":
        """Set max number of tracks."""
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self._definition.limit = limit
        self._definition.limit_percent = None
        return self

    def limit_percent(self, percent: int) -> "SmartPlaylistBuilder":
        """Set percentage of matching tracks (1-100)."""
        if not 1 <= percent <= 100:
            raise ValueError("limit_percent must be between 1 and 100")
        self._definition.limit_percent = percent
        self._definition.limit = None
        return self

    def comment(self, comment: str) -> "SmartPlaylistBuilder":
        """Set playlist comment."""
        self._definition.comment = comment
        return self

    def public(self, public: bool = True) -> "SmartPlaylistBuilder":
        """Set playlist visibility."""
        self._definition.public = public
        return self

    def build(self) -> SmartPlaylistDefinition:
        """Build and return the SmartPlaylistDefinition."""
        return self._definition
