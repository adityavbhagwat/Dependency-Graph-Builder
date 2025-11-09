from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from .operation import Operation
from .enums import DependencyType

@dataclass
class Dependency:
    """Represents a dependency between two operations"""
    source: Operation  # Operation that must execute first
    target: Operation  # Operation that depends on source
    type: DependencyType
    confidence: float = 1.0  # 0.0 to 1.0
    
    # Specific information based on type
    parameter_mapping: Dict[str, str] = field(default_factory=dict)  # source_param -> target_param
    constraint: Optional[str] = None
    reason: Optional[str] = None
    
    # Runtime metadata
    verified: bool = False  # Has this dependency been verified at runtime?
    success_count: int = 0
    failure_count: int = 0
    
    def __hash__(self):
        return hash((self.source.operation_id, self.target.operation_id, self.type))