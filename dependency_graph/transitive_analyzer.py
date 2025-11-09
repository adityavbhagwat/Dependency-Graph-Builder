from typing import List
from .dependency import Dependency
from .operation import Operation
from .enums import DependencyType
from .core import DependencyGraph

class TransitiveDependencyAnalyzer:
    """Analyze and compute transitive dependencies"""
    
    def __init__(self, graph: DependencyGraph):
        self.graph = graph
        self.dependencies: List[Dependency] = []
    
    def analyze(self) -> List[Dependency]:
        """Compute transitive dependencies"""
        dependencies = []
        
        # For each pair of operations, check if there's a transitive path
        operations = list(self.graph.operations.values())
        
        for i, op1 in enumerate(operations):
            for op2 in operations[i+1:]:
                if self._has_transitive_path(op1, op2):
                    # Check if direct dependency already exists
                    if not self._has_direct_dependency(op1, op2):
                        dep = Dependency(
                            source=op1,
                            target=op2,
                            type=DependencyType.TRANSITIVE,
                            confidence=0.5,
                            reason="Transitive dependency through intermediate operations"
                        )
                        dependencies.append(dep)
        
        self.dependencies = dependencies
        return dependencies
    
    def _has_transitive_path(self, op1: Operation, op2: Operation) -> bool:
        """Check if there's a transitive path between operations"""
        return self.graph.has_path(op1, op2)
    
    def _has_direct_dependency(self, op1: Operation, op2: Operation) -> bool:
        """Check if there's already a direct dependency"""
        return self.graph.graph.has_edge(op1.operation_id, op2.operation_id)