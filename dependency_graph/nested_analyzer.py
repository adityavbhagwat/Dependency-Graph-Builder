from typing import Dict, Any, List
from .operation import Operation
from .dependency import Dependency
from .enums import DependencyType, HTTPMethod

class NestedResourceAnalyzer:
    """Analyze nested resource dependencies"""
    
    def __init__(self, operations: List[Operation]):
        self.operations = operations
        self.dependencies: List[Dependency] = []
    
    def analyze(self) -> List[Dependency]:
        """Find nested resource dependencies"""
        dependencies = []
        
        # Build path hierarchy
        path_tree = self._build_path_tree()
        
        # For each operation, find parent operations
        for op in self.operations:
            parent_ops = self._find_parent_operations(op, path_tree)
            
            for parent_op in parent_ops:
                dep = Dependency(
                    source=parent_op,
                    target=op,
                    type=DependencyType.NESTED_RESOURCE,
                    confidence=0.85,
                    reason=f"{op.path} is nested under {parent_op.path}"
                )
                dependencies.append(dep)
        
        self.dependencies = dependencies
        return dependencies
    
    def _build_path_tree(self) -> Dict[str, Any]:
        """Build hierarchical tree of paths"""
        tree = {}
        
        for op in self.operations:
            parts = [p for p in op.path.split('/') if p]
            current = tree
            
            for part in parts:
                if part not in current:
                    current[part] = {'operations': [], 'children': {}}
                leaf_node = current[part]
                current = current[part]['children']
            
            # Store operation at leaf
            if parts:
                leaf_node['operations'].append(op)
        
        return tree
    
    def _find_parent_operations(self, operation: Operation, 
                                path_tree: Dict[str, Any]) -> List[Operation]:
        """Find parent operations in the path hierarchy"""
        parents = []
        
        path_parts = [p for p in operation.path.split('/') if p]
        
        # Check each level up the hierarchy
        for i in range(len(path_parts) - 1):
            parent_path = '/' + '/'.join(path_parts[:i+1])
            
            # Find operations that match this parent path
            for op in self.operations:
                if op.path == parent_path and op.method == HTTPMethod.POST:
                    parents.append(op)
        
        return parents