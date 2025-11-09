from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from .enums import DependencyType
from .operation import Operation

@dataclass(slots=True)
class Dependency:
    """
    Represents a dependency between two operations.
    It is memory-optimized but captures all necessary analytical data.
    """
    source: Operation
    target: Operation
    type: DependencyType
    reason: str = ""
    confidence: float = 1.0
    parameter_mapping: Dict[str, str] = field(default_factory=dict)
    constraint: Optional[Any] = None
    
    # THE FIX IS HERE:
    # Add the 'verified' field back. This is used by the AnnotationExporter
    # and DynamicDependencyManager to track runtime feedback.
    verified: Optional[bool] = None

    def get_graph_summary(self) -> Dict[str, Any]:
        """
        Returns a lightweight dictionary summary for graph edge attributes.
        Includes constraint and verification info if present.
        """
        summary = {
            "type": self.type.value,
            "confidence": self.confidence,
            "reason": self.reason
        }
        if self.constraint:
            summary['constraint'] = str(self.constraint)
        
        if self.verified is not None:
            summary['verified'] = self.verified
            
        return summary