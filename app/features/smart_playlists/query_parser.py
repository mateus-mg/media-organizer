"""Parser for expanded smart playlist query strings."""
from typing import Any, Optional

from .definition import Rule, SmartPlaylistDefinition
from .validators import validate_operator_for_field


class QueryStringParser:
    """Parse query strings into SmartPlaylistDefinition.

    Syntax:
        campo:valor              → default operator (contains for strings, is for bools/numbers)
        campo:operador:valor     → explicit operator
        campo:"valor com espaço" → quoted values
        Condições separadas por espaço = AND
    """

    def parse(self, query: str) -> SmartPlaylistDefinition:
        definition = SmartPlaylistDefinition(name="")
        terms = self._tokenize(str(query or "").strip())
        for term in terms:
            rule = self._parse_term(term)
            if rule:
                definition.all_rules.append(rule)
        return definition

    def _tokenize(self, query: str) -> list[str]:
        tokens = []
        current = ""
        in_quotes = False
        for ch in query:
            if ch == '"':
                in_quotes = not in_quotes
                current += ch
            elif ch.isspace() and not in_quotes:
                if current.strip():
                    tokens.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            tokens.append(current.strip())
        return tokens

    def _parse_term(self, term: str) -> Optional[Rule]:
        if not term:
            return None
        # Remove surrounding quotes if present
        if len(term) >= 2 and term.startswith('"') and term.endswith('"'):
            term = term[1:-1]
        parts = term.split(":")
        if len(parts) < 2:
            return None
        field = parts[0].strip()
        if len(parts) == 2:
            # campo:valor → default operator
            value = self._parse_value(parts[1])
            operator = self._default_operator(field, value)
        else:
            # campo:operador:valor
            operator = parts[1].strip()
            value = self._parse_value(":".join(parts[2:]))
        validate_operator_for_field(operator, field, value)
        return Rule(operator, field, value)

    def _parse_value(self, raw: str) -> Any:
        raw = raw.strip()
        if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        lower = raw.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        try:
            if "." in raw:
                return float(raw)
            return int(raw)
        except ValueError:
            return raw

    @staticmethod
    def _default_operator(field: str, value: Any) -> str:
        if isinstance(value, bool):
            return "is"
        if isinstance(value, (int, float)):
            return "is"
        return "contains"
