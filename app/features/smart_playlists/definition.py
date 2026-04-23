"""Smart playlist definition models for Navidrome .nsp format."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Rule:
    """A single smart playlist rule with operator, field, and value."""

    operator: str
    field: str
    value: Any

    def to_nsp_dict(self) -> Dict[str, Any]:
        """Serialize to Navidrome .nsp JSON dict."""
        return {self.operator: {self.field: self.value}}


@dataclass
class SmartPlaylistDefinition:
    """Complete smart playlist definition for Navidrome NSP serialization."""

    name: str
    comment: str = ""
    public: bool = False
    all_rules: List[Rule] = field(default_factory=list)
    any_rules: List[Rule] = field(default_factory=list)
    sort: Optional[str] = None
    order: Optional[str] = None
    limit: Optional[int] = None
    limit_percent: Optional[int] = None

    def to_nsp_dict(self) -> Dict[str, Any]:
        """Serialize to Navidrome .nsp JSON dict."""
        payload: Dict[str, Any] = {
            "name": self.name,
            "comment": self.comment,
            "public": self.public,
        }
        if self.all_rules:
            payload["all"] = [r.to_nsp_dict() for r in self.all_rules]
        if self.any_rules:
            payload["any"] = [r.to_nsp_dict() for r in self.any_rules]
        if self.sort:
            payload["sort"] = self.sort
        if self.order:
            payload["order"] = self.order
        if self.limit is not None:
            payload["limit"] = self.limit
        if self.limit_percent is not None:
            payload["limitPercent"] = self.limit_percent
        return payload
