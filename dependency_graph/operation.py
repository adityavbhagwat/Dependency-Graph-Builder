from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from .enums import HTTPMethod
from .parameter import Parameter
from .response import Response

@dataclass
class Operation:
    """Represents a single API operation"""
    operation_id: str  # Unique identifier
    path: str
    method: HTTPMethod
    parameters: List[Parameter] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, Response] = field(default_factory=dict)
    security: List[Dict[str, List[str]]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    # Extracted information
    consumes: Set[str] = field(default_factory=set)  # Parameters it needs
    produces: Set[str] = field(default_factory=set)  # Parameters it provides
    path_params: Set[str] = field(default_factory=set)
    resource_type: Optional[str] = None  # e.g., "users", "posts"
    
    # Annotations (NAUTILUS-style)
    annotations: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.operation_id)
    
    def is_interesting(self) -> bool:
        """Check if operation is interesting for vulnerability testing"""
        return (self.method in [HTTPMethod.POST, HTTPMethod.PUT] or
                (self.method == HTTPMethod.GET and len(self.path_params) > 0))