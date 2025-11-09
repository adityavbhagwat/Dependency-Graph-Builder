from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from .enums import DependencyType
from .operation import Operation

@dataclass(slots=True)
class Dependency:
    """Represents a dependency between two operations (memory-optimized with __slots__)."""
    source: Operation
    target: Operation
    type: DependencyType
    reason: str = ""
    confidence: float = 1.0
    parameter_mapping: Dict[str, str] = field(default_factory=dict)
    verified: Optional[bool] = None

    def get_summary(self) -> Dict[str, Any]:
        """Returns a lightweight dictionary summary for graph edge attributes."""
        return {
            "type": self.type.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "param_map_count": len(self.parameter_mapping)
        }