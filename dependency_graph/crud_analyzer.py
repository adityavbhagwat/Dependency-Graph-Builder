from typing import Dict, List
from .operation import Operation
from .dependency import Dependency
from .enums import DependencyType, HTTPMethod

class CRUDDependencyAnalyzer:
    """Analyze CRUD-based dependencies"""
    
    def __init__(self, operations: List[Operation]):
        self.operations = operations
        self.dependencies: List[Dependency] = []
    
    def _is_true_create(self, op: Operation) -> bool:
        """
        Determine if a POST operation is a true 'create' operation.
        POST on /resource is a create, POST on /resource/{id}/action is not.
        """
        if op.method != HTTPMethod.POST:
            return False
        
        # If the path has no path parameters in the last segment, it's likely a create
        # e.g., POST /pet is create, POST /pet/{petId} is update, POST /pet/{petId}/uploadImage is action
        path_parts = [p for p in op.path.split('/') if p]
        if not path_parts:
            return True
        
        last_part = path_parts[-1]
        
        # If last part is a path parameter, this is likely an update/action, not a create
        if last_part.startswith('{'):
            return False
        
        # If there's any path parameter before the last part, this might be a sub-resource action
        has_path_param = any(p.startswith('{') for p in path_parts[:-1])
        if has_path_param:
            return False
        
        return True
    
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
            # Separate by HTTP method - only true creates for POST
            creates = [op for op in ops if self._is_true_create(op)]
            reads = [op for op in ops if op.method == HTTPMethod.GET]
            updates = [op for op in ops if op.method in [HTTPMethod.PUT, HTTPMethod.PATCH]]
            deletes = [op for op in ops if op.method == HTTPMethod.DELETE]
            
            # Also treat non-create POST operations as updates (they modify existing resources)
            post_updates = [op for op in ops if op.method == HTTPMethod.POST and not self._is_true_create(op)]
            updates.extend(post_updates)
            
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