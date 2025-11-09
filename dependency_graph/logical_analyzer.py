from typing import Dict, List
from .operation import Operation
from .dependency import Dependency
from .enums import DependencyType, HTTPMethod

class LogicalDependencyAnalyzer:
    """Analyze logical/business dependencies"""
    
    # Keywords for different dependency types
    AUTH_KEYWORDS = ['login', 'signin', 'authenticate', 'auth']
    SIGNUP_KEYWORDS = ['signup', 'register', 'create_account']
    LOGOUT_KEYWORDS = ['logout', 'signout']
    ADMIN_KEYWORDS = ['admin', 'administrator']
    
    def __init__(self, operations: List[Operation]):
        self.operations = operations
        self.dependencies: List[Dependency] = []
    
    def analyze(self) -> List[Dependency]:
        """Find logical dependencies"""
        dependencies = []
        
        # Identify special operations
        auth_ops = self._find_operations_by_keywords(self.AUTH_KEYWORDS)
        signup_ops = self._find_operations_by_keywords(self.SIGNUP_KEYWORDS)
        logout_ops = self._find_operations_by_keywords(self.LOGOUT_KEYWORDS)
        admin_ops = self._find_operations_by_keywords(self.ADMIN_KEYWORDS)
        
        # Authentication dependencies
        dependencies.extend(self._analyze_authentication_deps(auth_ops))
        
        # Signup → Login dependency
        for signup in signup_ops:
            for login in auth_ops:
                dep = Dependency(
                    source=signup,
                    target=login,
                    type=DependencyType.WORKFLOW,
                    confidence=0.8,
                    reason="Must signup before login"
                )
                dependencies.append(dep)
        
        # Logout is terminal operation
        for logout in logout_ops:
            # Mark in operation annotations
            if 'term_operations' not in logout.annotations:
                logout.annotations['term_operations'] = True
        
        # Admin operations require authentication
        for admin_op in admin_ops:
            for auth_op in auth_ops:
                dep = Dependency(
                    source=auth_op,
                    target=admin_op,
                    type=DependencyType.AUTHORIZATION,
                    confidence=0.9,
                    reason="Admin operations require authentication"
                )
                dependencies.append(dep)
        
        # Security scheme analysis
        dependencies.extend(self._analyze_security_schemes())
        
        self.dependencies = dependencies
        return dependencies
    
    def _find_operations_by_keywords(self, keywords: List[str]) -> List[Operation]:
        """Find operations matching keywords"""
        matching_ops = []
        
        for op in self.operations:
            # Check operation ID
            op_id_lower = op.operation_id.lower()
            if any(kw in op_id_lower for kw in keywords):
                matching_ops.append(op)
                continue
            
            # Check path
            path_lower = op.path.lower()
            if any(kw in path_lower for kw in keywords):
                matching_ops.append(op)
                continue
            
            # Check tags
            tags_lower = [tag.lower() for tag in op.tags]
            if any(any(kw in tag for kw in keywords) for tag in tags_lower):
                matching_ops.append(op)
        
        return matching_ops
    
    def _analyze_authentication_deps(self, auth_ops: List[Operation]) -> List[Dependency]:
        """Create authentication dependencies for protected operations"""
        dependencies = []
        
        for op in self.operations:
            # Skip auth operations themselves
            if op in auth_ops:
                continue
            
            # Check if operation has security requirements
            if op.security:
                for auth_op in auth_ops:
                    dep = Dependency(
                        source=auth_op,
                        target=op,
                        type=DependencyType.AUTHENTICATION,
                        confidence=0.95,
                        reason=f"{op.operation_id} requires authentication"
                    )
                    dependencies.append(dep)
            
            # Heuristic: operations with path parameters often need auth
            elif op.path_params and op.method != HTTPMethod.GET:
                for auth_op in auth_ops:
                    dep = Dependency(
                        source=auth_op,
                        target=op,
                        type=DependencyType.AUTHENTICATION,
                        confidence=0.7,
                        reason=f"{op.operation_id} likely requires authentication (heuristic)"
                    )
                    dependencies.append(dep)
        
        return dependencies
    
    def _analyze_security_schemes(self) -> List[Dependency]:
        """Analyze dependencies based on security schemes"""
        dependencies = []
        
        # Group operations by security requirements
        security_groups: Dict[str, List[Operation]] = {}
        
        for op in self.operations:
            if op.security:
                security_key = str(sorted([list(s.keys())[0] for s in op.security]))
                if security_key not in security_groups:
                    security_groups[security_key] = []
                security_groups[security_key].append(op)
        
        # Operations with same security requirements may have dependencies
        # This is domain-specific and can be extended
        
        return dependencies