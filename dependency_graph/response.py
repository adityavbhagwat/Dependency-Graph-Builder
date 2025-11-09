from dataclasses import dataclass, field
from typing import Dict, Any, Set

@dataclass
class Response:
    """Represents an API response"""
    status_code: str
    schema: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, Any] = field(default_factory=dict)
    produces: Set[str] = field(default_factory=set)  # Parameters it produces