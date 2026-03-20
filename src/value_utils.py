"""Small shared utilities for metadata value normalization and checks."""

from typing import Any, Optional, Set


def is_missing_value(
    value: Any,
    *,
    unknown_values: Optional[Set[str]] = None,
    unknown_prefix: bool = False,
    treat_empty_collections: bool = False,
) -> bool:
    """Return True when a metadata value should be treated as missing."""
    if value is None:
        return True

    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return True

        lowered = cleaned.lower()
        if unknown_prefix and lowered.startswith("unknown"):
            return True
        if unknown_values and lowered in unknown_values:
            return True
        return False

    if treat_empty_collections and isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0

    return False
