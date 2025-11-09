from typing import Dict, List
from .operation import Operation
from .dependency import Dependency
from .enums import DependencyType, HTTPMethod

class CRUDDependencyAnalyzer:
    """Analyze CRUD-based dependencies"""
    
    def __init__(self, operations: List[Operation]):
        self.operations = operations
        self.dependencies: List[Dependency] = []
    
    def analyze(self) -> List[Dependency]:
        """Find CRUD dependencies"""
        dependencies = []
        
        # Group operations by resource type
        resource_ops: Dict[str, List[Operation]] = {}
        for op in self.operations:
            if op.resource_type:
                if op.resource_type not in resource_ops:
                    resource_ops[op.resource_type] = []
                resource_ops[op.resource_type].append(op)
        
        # For each resource, establish CRUD dependencies
        for resource, ops in resource_ops.items():
            # Separate by HTTP method
            creates = [op for op in ops if op.method == HTTPMethod.POST]
            reads = [op for op in ops if op.method == HTTPMethod.GET]
            updates = [op for op in ops if op.method in [HTTPMethod.PUT, HTTPMethod.PATCH]]
            deletes = [op for op in ops if op.method == HTTPMethod.DELETE]
            
            # CREATE → READ
            for create in creates:
                for read in reads:
                    if self._is_crud_related(create, read):
                        dep = Dependency(
                            source=create,
                            target=read,
                            type=DependencyType.CRUD,
                            confidence=0.9,
                            reason=f"CRUD: Must create {resource} before reading"
                        )
                        dependencies.append(dep)
            
            # CREATE → UPDATE
            for create in creates:
                for update in updates:
                    if self._is_crud_related(create, update):
                        dep = Dependency(
                            source=create,
                            target=update,
                            type=DependencyType.CRUD,
                            confidence=0.9,
                            reason=f"CRUD: Must create {resource} before updating"
                        )
                        dependencies.append(dep)
            
            # CREATE → DELETE
            for create in creates:
                for delete in deletes:
                    if self._is_crud_related(create, delete):
                        dep = Dependency(
                            source=create,
                            target=delete,
                            type=DependencyType.CRUD,
                            confidence=0.9,
                            reason=f"CRUD: Must create {resource} before deleting"
                        )
                        dependencies.append(dep)
            
            # READ → UPDATE (optional, less certain)
            for read in reads:
                for update in updates:
                    if self._is_crud_related(read, update):
                        dep = Dependency(
                            source=read,
                            target=update,
                            type=DependencyType.CRUD,
                            confidence=0.6,
                            reason=f"CRUD: Often read {resource} before updating"
                        )
                        dependencies.append(dep)
        
        self.dependencies = dependencies
        return dependencies
    
    def _is_crud_related(self, op1: Operation, op2: Operation) -> bool:
        """Check if two operations are related in CRUD context"""
        # Same resource type
        if op1.resource_type != op2.resource_type:
            return False
        
        # Check path similarity
        # e.g., POST /users and GET /users/{id}
        path1_parts = op1.path.split('/')
        path2_parts = op2.path.split('/')
        
        # Match base path
        base1 = [p for p in path1_parts if not p.startswith('{')]
        base2 = [p for p in path2_parts if not p.startswith('{')]
        
        return base1 == base2 or set(base1).issubset(set(base2)) or set(base2).issubset(set(base1))