from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from .enums import HTTPMethod
from .parameter import Parameter
from .response import Response

@dataclass(slots=True)
class Operation:
    """Represents a single API operation (memory-optimized with __slots__)."""
    operation_id: str
    path: str
    method: HTTPMethod
    parameters: List[Parameter] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, Response] = field(default_factory=dict)
    security: List[Dict[str, List[str]]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    consumes: Set[str] = field(default_factory=set)
    produces: Set[str] = field(default_factory=set)
    path_params: Set[str] = field(default_factory=set)
    resource_type: Optional[str] = None
    annotations: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.operation_id)

    def get_summary(self) -> Dict[str, Any]:
        """Returns a lightweight dictionary summary for graph node attributes."""
        return {
            "method": self.method.value,
            "path": self.path,
            "resource_type": self.resource_type,
            "tags": ", ".join(self.tags) if self.tags else ""
        }

    def is_interesting(self) -> bool:
        """Check if operation is interesting for vulnerability testing"""
        return (self.method in [HTTPMethod.POST, HTTPMethod.PUT] or
                (self.method == HTTPMethod.GET and len(self.path_params) > 0))