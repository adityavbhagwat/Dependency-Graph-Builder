from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class Parameter:
    """Represents an API parameter"""
    name: str
    location: str  # path, query, header, cookie, body
    type: str
    required: bool = False
    schema: Dict[str, Any] = field(default_factory=dict)
    example: Optional[Any] = None
    description: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash((self.name, self.location))