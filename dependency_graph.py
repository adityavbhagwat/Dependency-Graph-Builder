from enum import Enum
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
import networkx as nx
import time 
from collections import deque

class DependencyType(Enum):
    """Types of dependencies between operations"""
    PARAMETER_DATA = "parameter_data"      # Producer-consumer
    CRUD = "crud"                          # RESTful semantics
    AUTHENTICATION = "authentication"      # Auth requirements
    AUTHORIZATION = "authorization"        # Permission requirements
    NESTED_RESOURCE = "nested_resource"    # Path hierarchy
    WORKFLOW = "workflow"                  # Business logic
    CONSTRAINT = "constraint"              # Parameter constraints
    TRANSITIVE = "transitive"              # Inferred dependencies
    DYNAMIC = "dynamic"                    # Runtime discovered

class HTTPMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

@dataclass
class Parameter:
    """Represents an API parameter"""
    name: str
    location: str  # path, query, header, cookie, body
    type: str
    required: bool = False
    schema: Dict[str, Any] = field(default_factory=dict)
    example: Optional[Any] = None
    description: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash((self.name, self.location))

@dataclass
class Response:
    """Represents an API response"""
    status_code: str
    schema: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, Any] = field(default_factory=dict)
    produces: Set[str] = field(default_factory=set)  # Parameters it produces
    
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

class DependencyGraph:
    """Main dependency graph structure"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.operations: Dict[str, Operation] = {}
        self.dependencies: List[Dependency] = []
        
        # Indexes for fast lookup
        self.producers: Dict[str, Set[Operation]] = {}  # param_name -> operations that produce it
        self.consumers: Dict[str, Set[Operation]] = {}  # param_name -> operations that consume it
        self.resource_map: Dict[str, List[Operation]] = {}  # resource -> operations
        self.ranks: Dict[str, int] = {} # For efficient, rank-based cycle detection
        
    def add_operation(self, operation: Operation):
        """Add an operation node to the graph"""
        op_id = operation.operation_id
        if op_id in self.operations:
            return

        self.operations[op_id] = operation
        self.graph.add_node(op_id, operation=operation)
        self.ranks[op_id] = 0  # Initialize rank to 0
        
        # Update indexes
        for param in operation.produces:
            if param not in self.producers:
                self.producers[param] = set()
            self.producers[param].add(operation)
            
        for param in operation.consumes:
            if param not in self.consumers:
                self.consumers[param] = set()
            self.consumers[param].add(operation)
            
        if operation.resource_type:
            if operation.resource_type not in self.resource_map:
                self.resource_map[operation.resource_type] = []
            self.resource_map[operation.resource_type].append(operation)
    
    def add_dependency(self, dependency: Dependency) -> bool:
        """Add a dependency edge to the graph, preventing cycles efficiently. Returns True if added."""
        source_id = dependency.source.operation_id
        target_id = dependency.target.operation_id

        # Prevent self-loops
        if source_id == target_id:
            return False

        # OPTIMIZATION: Use ranks to avoid expensive path checks for forward edges.
        # An edge u->v can only form a cycle if rank(u) >= rank(v).
        if self.ranks[source_id] >= self.ranks[target_id]:
            # This is a potential back-edge, must do a full check.
            if nx.has_path(self.graph, target_id, source_id):
                return False

        # Add the edge
        self.dependencies.append(dependency)
        self.graph.add_edge(
            source_id,
            target_id,
            dependency=dependency,
            dep_type=dependency.type.value,
            weight=1.0 - dependency.confidence
        )

        # Propagate rank update if necessary
        if self.ranks[source_id] + 1 > self.ranks[target_id]:
            self._update_ranks(source_id, target_id)

        return True
    
    def _update_ranks(self, source_id: str, target_id: str):
        """Update ranks of target_id and its descendants after an edge is added."""
        
        # Set the initial rank of the target node
        self.ranks[target_id] = self.ranks[source_id] + 1
        
        # Use a queue for a traversal starting from the target.
        q = deque([target_id])
        
        while q:
            current_id = q.popleft()
            
            for successor_id in self.graph.successors(current_id):
                # A successor's rank must be greater than its parent's rank.
                if self.ranks[current_id] + 1 > self.ranks[successor_id]:
                    self.ranks[successor_id] = self.ranks[current_id] + 1
                    q.append(successor_id)

    def get_dependencies(self, operation: Operation, 
                        dep_type: Optional[DependencyType] = None) -> List[Dependency]:
        """Get all dependencies for an operation"""
        deps = [d for d in self.dependencies if d.target == operation]
        if dep_type:
            deps = [d for d in deps if d.type == dep_type]
        return deps
    
    def get_operation_sequence(self, operation: Operation) -> List[Operation]:
        """Get ordered sequence of operations needed before this one"""
        if operation.operation_id not in self.graph:
            return []
        
        # Topological sort of ancestors
        ancestors = nx.ancestors(self.graph, operation.operation_id)
        subgraph = self.graph.subgraph(ancestors | {operation.operation_id})
        
        try:
            sequence = list(nx.topological_sort(subgraph))
            return [self.operations[op_id] for op_id in sequence]
        except nx.NetworkXError:
            # Graph has cycles, use DFS
            return self._dfs_sequence(operation)
    
    def _dfs_sequence(self, operation: Operation) -> List[Operation]: ## sugest syntax fix 

        """DFS-based sequence generation (handles cycles)"""
        visited = set()
        sequence = []
        
        def dfs(op: Operation):
            if op.operation_id in visited:
                return
            visited.add(op.operation_id)
            
            deps = self.get_dependencies(op)
            for dep in deps:
                dfs(dep.source)
            
            sequence.append(op)
        
        dfs(operation)
        return sequence
    
    def detect_cycles(self) -> List[List[str]]:
        """Detect cycles in the dependency graph"""
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except:
            return []
    
    def has_path(self, source: Operation, target: Operation) -> bool:
        """Check if there's a path from source to target"""
        return nx.has_path(self.graph, source.operation_id, target.operation_id)
    
import yaml
import json
from typing import Dict, Any, List
from urllib.parse import urlparse

class OpenAPIParser:
    """Parse and extract information from OpenAPI specification"""
    
    def __init__(self, spec_path: str):
        self.spec_path = spec_path
        self.spec: Dict[str, Any] = {}
        self.operations: List[Operation] = []
        self.schemas: Dict[str, Any] = {}
        
    def parse(self) -> List[Operation]:
        """Main parsing method"""
        # Load specification
        with open(self.spec_path, 'r') as f:
            if self.spec_path.endswith('.yaml') or self.spec_path.endswith('.yml'):
                self.spec = yaml.safe_load(f)
            else:
                self.spec = json.load(f)
        
        # Extract schemas
        self.schemas = self.spec.get('components', {}).get('schemas', {})
        
        # Extract operations
        paths = self.spec.get('paths', {})
        for path, path_item in paths.items():
            for method, operation_spec in path_item.items():
                if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    operation = self._parse_operation(path, method.upper(), operation_spec)
                    self.operations.append(operation)
        
        return self.operations
    
    def _parse_operation(self, path: str, method: str, spec: Dict[str, Any]) -> Operation:
        """Parse a single operation"""
        operation_id = spec.get('operationId', f"{method}_{path.replace('/', '_')}")
        
        # Parse parameters
        parameters = []
        consumes = set()
        produces = set()
        path_params = set()
        
        for param_spec in spec.get('parameters', []):
            param = self._parse_parameter(param_spec)
            parameters.append(param)
            consumes.add(param.name)
            
            if param.location == 'path':
                path_params.add(param.name)
        
        # Parse request body
        request_body = None
        if 'requestBody' in spec:
            request_body = spec['requestBody']
            body_params = self._extract_body_parameters(request_body)
            consumes.update(body_params)
        
        # Parse responses
        responses = {}
        for status_code, response_spec in spec.get('responses', {}).items():
            response = self._parse_response(status_code, response_spec)
            responses[status_code] = response
            produces.update(response.produces)
        
        # Extract resource type
        resource_type = self._extract_resource_type(path)
        
        operation = Operation(
            operation_id=operation_id,
            path=path,
            method=HTTPMethod[method],
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            security=spec.get('security', []),
            tags=spec.get('tags', []),
            consumes=consumes,
            produces=produces,
            path_params=path_params,
            resource_type=resource_type
        )
        
        return operation
    
    def _parse_parameter(self, spec: Dict[str, Any]) -> Parameter:
        """Parse a parameter specification"""
        return Parameter(
            name=spec.get('name', ''),
            location=spec.get('in', ''),
            type=spec.get('schema', {}).get('type', 'string'),
            required=spec.get('required', False),
            schema=spec.get('schema', {}),
            example=spec.get('example'),
            description=spec.get('description'),
            constraints={
                'minimum': spec.get('schema', {}).get('minimum'),
                'maximum': spec.get('schema', {}).get('maximum'),
                'pattern': spec.get('schema', {}).get('pattern'),
                'enum': spec.get('schema', {}).get('enum'),
                'minLength': spec.get('schema', {}).get('minLength'),
                'maxLength': spec.get('schema', {}).get('maxLength'),
            }
        )
    
    def _parse_response(self, status_code: str, spec: Dict[str, Any]) -> Response:
        """Parse a response specification"""
        produces = set()
        schema = {}
        
        content = spec.get('content', {})
        for media_type, media_spec in content.items():
            if 'schema' in media_spec:
                schema = media_spec['schema']
                # Extract producible parameters from schema
                produces.update(self._extract_schema_properties(schema))
        
        return Response(
            status_code=status_code,
            schema=schema,
            headers=spec.get('headers', {}),
            produces=produces
        )
    
    def _extract_schema_properties(self, schema: Dict[str, Any], prefix: str = '') -> Set[str]:
        """Recursively extract property names from schema"""
        properties = set()
        
        # Handle $ref
        if '$ref' in schema:
            ref_path = schema['$ref'].split('/')[-1]
            if ref_path in self.schemas:
                return self._extract_schema_properties(self.schemas[ref_path], prefix)
        
        # Handle properties
        if 'properties' in schema:
            for prop_name, prop_schema in schema['properties'].items():
                full_name = f"{prefix}.{prop_name}" if prefix else prop_name
                properties.add(full_name)
                
                # Recurse for nested objects
                if prop_schema.get('type') == 'object':
                    properties.update(
                        self._extract_schema_properties(prop_schema, full_name)
                    )
        
        # Handle arrays
        if schema.get('type') == 'array' and 'items' in schema:
            properties.update(
                self._extract_schema_properties(schema['items'], prefix)
            )
        
        return properties
    
    def _extract_body_parameters(self, request_body: Dict[str, Any]) -> Set[str]:
        """Extract parameter names from request body"""
        parameters = set()
        
        content = request_body.get('content', {})
        for media_type, media_spec in content.items():
            if 'schema' in media_spec:
                parameters.update(
                    self._extract_schema_properties(media_spec['schema'])
                )
        
        return parameters
    
    def _extract_resource_type(self, path: str) -> Optional[str]:
        """Extract resource type from path"""
        # Remove path parameters
        path_clean = path.split('{')[0].rstrip('/')
        
        # Get last segment
        segments = [s for s in path_clean.split('/') if s]
        if segments:
            return segments[-1]
        
        return None
    
class ParameterDependencyAnalyzer:
    """Analyze parameter-wise dependencies (producer-consumer)"""
    
    def __init__(self, operations: List[Operation]):
        self.operations = operations
        self.dependencies: List[Dependency] = []
    
    def analyze(self) -> List[Dependency]:
        """Find all parameter-wise dependencies"""
        dependencies = []
        
        # Build producer-consumer maps
        producers: Dict[str, List[Operation]] = {}
        consumers: Dict[str, List[Operation]] = {}
        
        for op in self.operations:
            for param in op.produces:
                if param not in producers:
                    producers[param] = []
                producers[param].append(op)
            
            for param in op.consumes:
                if param not in consumers:
                    consumers[param] = []
                consumers[param].append(op)
        
        # Match producers with consumers
        for param_name in producers:
            if param_name in consumers:
                for producer in producers[param_name]:
                    for consumer in consumers[param_name]:
                        if producer != consumer:
                            dep = Dependency(
                                source=producer,
                                target=consumer,
                                type=DependencyType.PARAMETER_DATA,
                                parameter_mapping={param_name: param_name},
                                confidence=self._calculate_confidence(producer, consumer, param_name),
                                reason=f"Parameter '{param_name}' produced by {producer.operation_id} "
                                       f"and consumed by {consumer.operation_id}"
                            )
                            dependencies.append(dep)
        
        # Fuzzy matching for similar parameter names
        dependencies.extend(self._fuzzy_parameter_matching(producers, consumers))
        
        self.dependencies = dependencies
        return dependencies
    
    def _calculate_confidence(self, producer: Operation, consumer: Operation, param: str) -> float:
        """Calculate confidence score for a dependency"""
        confidence = 1.0
        
        # Reduce confidence if producer can produce multiple values for same param
        producer_responses = [r for r in producer.responses.values() if param in r.produces]
        if len(producer_responses) > 1:
            confidence *= 0.8
        
        # Check if parameter is required in consumer
        consumer_param = next((p for p in consumer.parameters if p.name == param), None)
        if consumer_param and not consumer_param.required:
            confidence *= 0.7
        
        # Check type compatibility
        # ... (implement type checking logic)
        
        return confidence
    
    def _fuzzy_parameter_matching(self, 
                                   producers: Dict[str, List[Operation]], 
                                   consumers: Dict[str, List[Operation]]) -> List[Dependency]:
        """Find dependencies using fuzzy parameter name matching"""
        dependencies = []
        
        # Common parameter name variations
        variations = {
            'id': ['ID', 'Id', '_id', 'identifier'],
            'user_id': ['userId', 'user_ID', 'userID', 'uid'],
            'username': ['user_name', 'userName', 'login', 'user'],
            # Add more variations
        }
        
        for prod_param, prod_ops in producers.items():
            for cons_param, cons_ops in consumers.items():
                if prod_param != cons_param:
                    # Check if they're variations of the same parameter
                    if self._are_parameter_variants(prod_param, cons_param, variations):
                        for producer in prod_ops:
                            for consumer in cons_ops:
                                dep = Dependency(
                                    source=producer,
                                    target=consumer,
                                    type=DependencyType.PARAMETER_DATA,
                                    parameter_mapping={prod_param: cons_param},
                                    confidence=0.6,  # Lower confidence for fuzzy matching
                                    reason=f"Fuzzy match: '{prod_param}' -> '{cons_param}'"
                                )
                                dependencies.append(dep)
        
        return dependencies
    
    def _are_parameter_variants(self, param1: str, param2: str, 
                                variations: Dict[str, List[str]]) -> bool:
        """Check if two parameter names are likely variants"""
        # Normalize
        p1 = param1.lower().replace('_', '').replace('-', '')
        p2 = param2.lower().replace('_', '').replace('-', '')
        
        # Check direct variation
        for base, variants in variations.items():
            normalized_variants = [v.lower().replace('_', '').replace('-', '') for v in variants]
            if p1 in normalized_variants and p2 in normalized_variants:
                return True
        
        # Levenshtein distance
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, p1, p2).ratio()
        return similarity > 0.8
        

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


class ConstraintDependencyAnalyzer:
    """Analyze constraint-based dependencies"""
    
    def __init__(self, operations: List[Operation]):
        self.operations = operations
        self.dependencies: List[Dependency] = []
    
    def analyze(self) -> List[Dependency]:
        """Find constraint-based dependencies"""
        dependencies = []
        
        # Analyze enum constraints
        dependencies.extend(self._analyze_enum_constraints())
        
        # Analyze range constraints
        dependencies.extend(self._analyze_range_constraints())
        
        # Analyze pattern constraints
        dependencies.extend(self._analyze_pattern_constraints())
        
        # Analyze conditional schemas (oneOf, anyOf, allOf)
        dependencies.extend(self._analyze_conditional_schemas())
        
        self.dependencies = dependencies
        return dependencies
    
    def _analyze_enum_constraints(self) -> List[Dependency]:
        """Find dependencies based on enum constraints"""
        dependencies = []
        
        # Find operations that set enum values
        enum_setters: Dict[str, List[Tuple[Operation, str]]] = {}
        
        for op in self.operations:
            for param in op.parameters:
                if 'enum' in param.constraints and param.constraints['enum']:
                    key = f"{op.resource_type}.{param.name}"
                    if key not in enum_setters:
                        enum_setters[key] = []
                    enum_setters[key].append((op, param.name))
        
        # Find operations that depend on these enum values
        for key, setters in enum_setters.items():
            resource_type, param_name = key.split('.')
            
            for op in self.operations:
                if op.resource_type == resource_type:
                    for setter_op, setter_param in setters:
                        if setter_op != op:
                            dep = Dependency(
                                source=setter_op,
                                target=op,
                                type=DependencyType.CONSTRAINT,
                                confidence=0.6,
                                constraint=f"enum:{param_name}",
                                reason=f"Parameter {param_name} has enum constraint"
                            )
                            dependencies.append(dep)
        
        return dependencies
    
    def _analyze_range_constraints(self) -> List[Dependency]:
        """Find dependencies based on range constraints"""
        # Similar to enum but for numeric ranges
        return []
    
    def _analyze_pattern_constraints(self) -> List[Dependency]:
        """Find dependencies based on pattern constraints"""
        # Regex pattern matching for parameters
        return []
    
    def _analyze_conditional_schemas(self) -> List[Dependency]:
        """Find dependencies based on oneOf/anyOf/allOf"""
        # Complex schema conditional logic
        return []


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
    
class DependencyGraphBuilder:
    """Main builder for constructing the dependency graph"""
    
    def __init__(self, spec_path: str):
        self.spec_path = spec_path
        self.parser = OpenAPIParser(spec_path)
        self.graph = DependencyGraph()
        self.operations: List[Operation] = []
        
    def build(self) -> DependencyGraph:
        """Main method to build the dependency graph"""
        print("Step 1: Parsing OpenAPI specification...")
        self.operations = self.parser.parse()
        print(f"  Found {len(self.operations)} operations")
        
        print("\nStep 2: Adding operations to graph...")
        for op in self.operations:
            self.graph.add_operation(op)
        
        print("\nStep 3: Analyzing dependencies...")
        all_dependencies = []
        
        # Parameter-wise dependencies
        print("  - Parameter-wise dependencies...")
        param_analyzer = ParameterDependencyAnalyzer(self.operations)
        param_deps = param_analyzer.analyze()
        all_dependencies.extend(param_deps)
        print(f"    Found {len(param_deps)} dependencies")
        
        # CRUD dependencies
        print("  - CRUD dependencies...")
        crud_analyzer = CRUDDependencyAnalyzer(self.operations)
        crud_deps = crud_analyzer.analyze()
        all_dependencies.extend(crud_deps)
        print(f"    Found {len(crud_deps)} dependencies")
        
        # Logical dependencies
        print("  - Logical dependencies...")
        logical_analyzer = LogicalDependencyAnalyzer(self.operations)
        logical_deps = logical_analyzer.analyze()
        all_dependencies.extend(logical_deps)
        print(f"    Found {len(logical_deps)} dependencies")
        
        # Nested resource dependencies
        print("  - Nested resource dependencies...")
        nested_analyzer = NestedResourceAnalyzer(self.operations)
        nested_deps = nested_analyzer.analyze()
        all_dependencies.extend(nested_deps)
        print(f"    Found {len(nested_deps)} dependencies")
        
        # Constraint dependencies
        print("  - Constraint dependencies...")
        constraint_analyzer = ConstraintDependencyAnalyzer(self.operations)
        constraint_deps = constraint_analyzer.analyze()
        all_dependencies.extend(constraint_deps)
        print(f"    Found {len(constraint_deps)} dependencies")
        
        print("\nStep 4: Resolving conflicts and adding to graph...")
        resolved_deps = self._resolve_conflicts(all_dependencies)
        
        # Sort dependencies by confidence (highest first) to prioritize adding stronger dependencies.
        resolved_deps.sort(key=lambda d: d.confidence, reverse=True)
        
        print(f"  Adding from {len(resolved_deps)} potential dependencies, ensuring no cycles are created...")
        added_count = 0
        for dep in resolved_deps:
            if self.graph.add_dependency(dep):
                added_count += 1
        
        print(f"  Successfully added {added_count} dependencies to form a Directed Acyclic Graph (DAG).")
        
        print("\nStep 5: Computing transitive dependencies...")
        transitive_analyzer = TransitiveDependencyAnalyzer(self.graph)
        transitive_deps = transitive_analyzer.analyze()
        for dep in transitive_deps:
            self.graph.add_dependency(dep)
        print(f"  Found {len(transitive_deps)} transitive dependencies")
        
        # print("\nStep 6: Optimizing graph...")
        # self._optimize_graph()
        
        return self.graph
    
    def _resolve_conflicts(self, dependencies: List[Dependency]) -> List[Dependency]:
        """Resolve conflicting dependencies"""
        # Group by source-target pair
        dep_map: Dict[Tuple[str, str], List[Dependency]] = {}
        
        for dep in dependencies:
            key = (dep.source.operation_id, dep.target.operation_id)
            if key not in dep_map:
                dep_map[key] = []
            dep_map[key].append(dep)
        
        resolved = []
        
        for key, deps in dep_map.items():
            if len(deps) == 1:
                resolved.append(deps[0])
            else:
                # Multiple dependencies between same operations
                # Keep the one with highest confidence, or merge
                merged = self._merge_dependencies(deps)
                resolved.append(merged)
        
        return resolved
    
    def _merge_dependencies(self, deps: List[Dependency]) -> Dependency:
        """Merge multiple dependencies into one"""
        # Sort by confidence
        deps_sorted = sorted(deps, key=lambda d: d.confidence, reverse=True)
        
        # Use highest confidence dependency as base
        base = deps_sorted[0]
        
        # Merge parameter mappings
        for dep in deps_sorted[1:]:
            base.parameter_mapping.update(dep.parameter_mapping)
        
        # Combine reasons
        reasons = [d.reason for d in deps if d.reason]
        base.reason = "; ".join(reasons)
        
        return base
    
    def _optimize_graph(self):
        """Optimize the dependency graph"""
        # Detect and handle cycles first, as transitive reduction requires a DAG
        print("  - Detecting cycles...")
        cycles = self.graph.detect_cycles()
        if cycles:
            print(f"    Warning: Found {len(cycles)} cycles")
            for cycle in cycles[:5]:  # Show first 5
                print(f"      {' -> '.join(cycle)}")
            # Option: break cycles by removing lowest confidence edge
            self._break_cycles(cycles)

        # Remove transitive edges (transitive reduction)
        print("  - Transitive reduction...")
        original_edges = self.graph.graph.number_of_edges()
        run_transitive_reduction = False
        
        # This is computationally expensive for large graphs
        # Use approximation for large graphs
        if run_transitive_reduction and len(self.graph.operations) < 100:
            reduced_graph = nx.transitive_reduction(self.graph.graph)
            # Copy node attributes
            for node in self.graph.graph.nodes():
                reduced_graph.nodes[node].update(self.graph.graph.nodes[node])
            # Copy edge attributes for remaining edges
            for u, v in reduced_graph.edges():
                if self.graph.graph.has_edge(u, v):
                    reduced_graph.edges[u, v].update(self.graph.graph.edges[u, v])
            
            self.graph.graph = reduced_graph
            print(f"    Reduced from {original_edges} to {self.graph.graph.number_of_edges()} edges")
        
        
    def _break_cycles(self, cycles: List[List[str]]):
        """Break cycles by removing lowest confidence edges"""
        for cycle in cycles:
            # Find edge with lowest confidence in cycle
            min_confidence = float('inf')
            edge_to_remove = None
            
            for i in range(len(cycle)):
                u = cycle[i]
                v = cycle[(i + 1) % len(cycle)]
                
                if self.graph.graph.has_edge(u, v):
                    edge_data = self.graph.graph.edges[u, v]
                    dep = edge_data.get('dependency')
                    
                    if dep and dep.confidence < min_confidence:
                        min_confidence = dep.confidence
                        edge_to_remove = (u, v)
            
            # Remove the edge
            if edge_to_remove:
                self.graph.graph.remove_edge(*edge_to_remove)
                print(f"    Broke cycle by removing edge {edge_to_remove}")

class DynamicDependencyManager:
    """Manage dynamic updates to the dependency graph based on runtime feedback"""
    
    def __init__(self, graph: DependencyGraph):
        self.graph = graph
        self.execution_history: List[Dict[str, Any]] = []
        self.failure_threshold = 10  # From NAUTILUS paper
    
    def record_execution(self, operation: Operation, success: bool, 
                        response: Dict[str, Any], parameters: Dict[str, Any]):
        """Record execution result for learning"""
        record = {
            'operation': operation,
            'success': success,
            'response': response,
            'parameters': parameters,
            'timestamp': time.time()
        }
        self.execution_history.append(record)
        
        if success:
            self._handle_successful_execution(operation, response, parameters)
        else:
            self._handle_failed_execution(operation, response, parameters)
    
    def _handle_successful_execution(self, operation: Operation, 
                                     response: Dict[str, Any], 
                                     parameters: Dict[str, Any]):
        """Update graph based on successful execution"""
        # Update operation annotations
        if 'success' not in operation.annotations:
            operation.annotations['success'] = True
            operation.annotations['successful_params'] = parameters.copy()
        
        # Discover new produced parameters from response
        new_params = self._extract_parameters_from_response(response)
        if new_params - operation.produces:
            print(f"  Discovered new produced parameters for {operation.operation_id}: {new_params - operation.produces}")
            operation.produces.update(new_params)
            
            # Update producer index
            for param in new_params:
                if param not in self.graph.producers:
                    self.graph.producers[param] = set()
                self.graph.producers[param].add(operation)
            
            # Create new dependencies with consumers
            self._create_new_parameter_dependencies(operation, new_params)
        
        # Update dependency confidence
        deps = self.graph.get_dependencies(operation)
        for dep in deps:
            dep.success_count += 1
            dep.verified = True
            # Increase confidence
            dep.confidence = min(1.0, dep.confidence * 1.1)
    
    def _handle_failed_execution(self, operation: Operation, 
                                 response: Dict[str, Any], 
                                 parameters: Dict[str, Any]):
        """Update graph based on failed execution"""
        # Update dependency failure counts
        deps = self.graph.get_dependencies(operation)
        for dep in deps:
            dep.failure_count += 1
            
            # Remove dependency if it fails too many times
            if dep.failure_count >= self.failure_threshold:
                print(f"  Removing unreliable dependency: {dep.source.operation_id} -> {dep.target.operation_id}")
                self.graph.graph.remove_edge(dep.source.operation_id, dep.target.operation_id)
                self.graph.dependencies.remove(dep)
            else:
                # Decrease confidence
                dep.confidence = max(0.1, dep.confidence * 0.9)
    
    def _extract_parameters_from_response(self, response: Dict[str, Any]) -> Set[str]:
        """Extract parameter names from actual response"""
        params = set()
        
        def extract_recursive(obj, prefix=''):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    params.add(full_key)
                    extract_recursive(value, full_key)
            elif isinstance(obj, list) and obj:
                extract_recursive(obj[0], prefix)
        
        extract_recursive(response)
        return params
    
    def _create_new_parameter_dependencies(self, producer: Operation, new_params: Set[str]):
        """Create dependencies for newly discovered parameters"""
        for param in new_params:
            if param in self.graph.consumers:
                for consumer in self.graph.consumers[param]:
                    if producer != consumer:
                        dep = Dependency(
                            source=producer,
                            target=consumer,
                            type=DependencyType.DYNAMIC,
                            confidence=0.8,
                            parameter_mapping={param: param},
                            reason=f"Dynamically discovered: {param} produced by {producer.operation_id}"
                        )
                        self.graph.add_dependency(dep)
    
    def discover_parameter_aliases(self):
        """Discover parameter aliases from execution history"""
        # Analyze successful executions to find parameters that must have same value
        
        # Group executions by operation sequence
        sequences: Dict[str, List[Dict]] = {}
        
        for i, record in enumerate(self.execution_history):
            if record['success']:
                # Get preceding operations
                sequence_key = self._get_sequence_key(i)
                if sequence_key not in sequences:
                    sequences[sequence_key] = []
                sequences[sequence_key].append(record)
        
        # Look for parameter value patterns
        for seq_key, records in sequences.items():
            self._analyze_parameter_patterns(records)
    
    def _get_sequence_key(self, index: int) -> str:
        """Get sequence identifier for execution at index"""
        # Look back at recent operations
        lookback = 5
        start = max(0, index - lookback)
        ops = [self.execution_history[i]['operation'].operation_id 
               for i in range(start, index + 1)]
        return '->'.join(ops)
    
    def _analyze_parameter_patterns(self, records: List[Dict]):
        """Analyze parameter value patterns across operations"""
        if len(records) < 2:
            return
        
        # Compare parameter values across operations
        for i in range(len(records) - 1):
            for j in range(i + 1, len(records)):
                rec1, rec2 = records[i], records[j]
                
                params1 = rec1['parameters']
                params2 = rec2['parameters']
                
                # Find parameters with same values
                for p1, v1 in params1.items():
                    for p2, v2 in params2.items():
                        if p1 != p2 and v1 == v2 and v1 is not None:
                            # Potential alias
                            self._add_parameter_alias(
                                rec1['operation'], p1,
                                rec2['operation'], p2
                            )
    
    def _add_parameter_alias(self, op1: Operation, param1: str, 
                            op2: Operation, param2: str):
        """Add parameter alias annotation"""
        alias_key = 'parameter_aliases'
        
        if alias_key not in op1.annotations:
            op1.annotations[alias_key] = {}
        if alias_key not in op2.annotations:
            op2.annotations[alias_key] = {}
        
        # Cross-reference
        op1.annotations[alias_key][param1] = f"{op2.operation_id}.{param2}"
        op2.annotations[alias_key][param2] = f"{op1.operation_id}.{param1}"
        
        print(f"  Discovered alias: {op1.operation_id}.{param1} <-> {op2.operation_id}.{param2}")

class GraphAnalyzer:
    """Analyze and provide insights about the dependency graph"""
    
    def __init__(self, graph: DependencyGraph):
        self.graph = graph
    
    def analyze(self) -> Dict[str, Any]:
        """Comprehensive graph analysis"""
        analysis = {
            'basic_stats': self._basic_statistics(),
            'complexity_metrics': self._complexity_metrics(),
            'critical_paths': self._find_critical_paths(),
            'dependency_clusters': self._find_clusters(),
            'bottlenecks': self._find_bottlenecks(),
            'recommendations': self._generate_recommendations()
        }
        
        return analysis
    
    def _basic_statistics(self) -> Dict[str, Any]:
        """Basic graph statistics"""
        return {
            'num_operations': len(self.graph.operations),
            'num_dependencies': len(self.graph.dependencies),
            'num_edges': self.graph.graph.number_of_edges(),
            'graph_density': nx.density(self.graph.graph),
            'is_dag': nx.is_directed_acyclic_graph(self.graph.graph),
            'num_cycles': len(self.graph.detect_cycles()) if not nx.is_directed_acyclic_graph(self.graph.graph) else 0
        }
    
    def _complexity_metrics(self) -> Dict[str, Any]:
        """Calculate complexity metrics"""
        # Maximum depth
        if nx.is_directed_acyclic_graph(self.graph.graph):
            max_depth = nx.dag_longest_path_length(self.graph.graph)
        else:
            max_depth = -1
        
        # Average dependencies per operation
        in_degrees = [d for n, d in self.graph.graph.in_degree()]
        out_degrees = [d for n, d in self.graph.graph.out_degree()]
        
        return {
            'max_sequence_depth': max_depth,
            'avg_incoming_deps': sum(in_degrees) / len(in_degrees) if in_degrees else 0,
            'avg_outgoing_deps': sum(out_degrees) / len(out_degrees) if out_degrees else 0,
            'max_incoming_deps': max(in_degrees) if in_degrees else 0,
            'max_outgoing_deps': max(out_degrees) if out_degrees else 0
        }
    
    def _find_critical_paths(self) -> List[List[str]]:
        """Find critical paths in the graph"""
        critical_paths = []
        
        if nx.is_directed_acyclic_graph(self.graph.graph):
            # Find longest path
            try:
                longest = nx.dag_longest_path(self.graph.graph)
                critical_paths.append(longest)
            except:
                pass
        
        return critical_paths
    
    def _find_clusters(self) -> List[Set[str]]:
        """Find strongly connected components / clusters"""
        # Convert to undirected for community detection
        undirected = self.graph.graph.to_undirected()
        
        # Use networkx community detection
        try:
            from networkx.algorithms import community
            communities = community.greedy_modularity_communities(undirected)
            return [set(c) for c in communities]
        except:
            return []
    
    def _find_bottlenecks(self) -> List[str]:
        """Find bottleneck operations (high betweenness centrality)"""
        betweenness = nx.betweenness_centrality(self.graph.graph)
        
        # Get top 10% as bottlenecks
        threshold = sorted(betweenness.values(), reverse=True)[int(len(betweenness) * 0.1)]
        bottlenecks = [op_id for op_id, score in betweenness.items() if score >= threshold]
        
        return bottlenecks
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        stats = self._basic_statistics()
        
        if not stats['is_dag']:
            recommendations.append(
                f"⚠️  Graph contains {stats['num_cycles']} cycles. Consider breaking them for cleaner sequences."
            )
        
        complexity = self._complexity_metrics()
        
        if complexity['max_sequence_depth'] > 10:
            recommendations.append(
                f"⚠️  Maximum sequence depth is {complexity['max_sequence_depth']}. "
                "Very deep sequences may be fragile."
            )
        
        if complexity['max_incoming_deps'] > 5:
            recommendations.append(
                f"⚠️  Some operations have {complexity['max_incoming_deps']} dependencies. "
                "Consider simplifying complex operations."
            )
        
        bottlenecks = self._find_bottlenecks()
        if bottlenecks:
            recommendations.append(
                f"ℹ️  Found {len(bottlenecks)} bottleneck operations that many paths go through."
            )
        
        return recommendations


class GraphVisualizer:
    """Visualize the dependency graph"""
    
    def __init__(self, graph: DependencyGraph):
        self.graph = graph
    
    def export_dot(self, output_path: str):
        """Export graph to DOT format (Graphviz)"""
        import pydot
        
        dot_graph = pydot.Dot(graph_type='digraph', rankdir='TB')
        
        # Add nodes
        for op_id, op in self.graph.operations.items():
            label = f"{op.method.value} {op.path}"
            color = self._get_node_color(op)
            
            node = pydot.Node(
                op_id,
                label=label,
                shape='box',
                style='filled',
                fillcolor=color
            )
            dot_graph.add_node(node)
        
        # Add edges
        for dep in self.graph.dependencies:
            edge = pydot.Edge(
                dep.source.operation_id,
                dep.target.operation_id,
                label=dep.type.value,
                color=self._get_edge_color(dep.type)
            )
            dot_graph.add_edge(edge)
        
        dot_graph.write_raw(output_path)
        print(f"Exported DOT graph to {output_path}")
    
    def export_graphml(self, output_path: str):
        """Export to GraphML format"""
        # GraphML format does not support complex Python objects as attributes.
        # We create a sanitized copy of the graph with these objects removed for export.
        graph_to_export = self.graph.graph.copy()
        
        # Remove the 'operation' object from nodes, as it's not serializable
        for _, data in graph_to_export.nodes(data=True):
            if 'operation' in data:
                del data['operation']
        
        # Remove the 'dependency' object from edges, as it's not serializable
        for _, _, data in graph_to_export.edges(data=True):
            if 'dependency' in data:
                del data['dependency']

        try:
            nx.write_graphml(graph_to_export, output_path)
            print(f"Exported GraphML to {output_path}")
        except ImportError:
            print(f"  [WARNING] Skipping GraphML export: 'lxml' library not found. Run 'pip install lxml' to enable.")
        except TypeError as e:
            print(f"  [ERROR] Could not export to GraphML due to unsupported data types: {e}")
    
    def export_json(self, output_path: str):
       
        """Export to JSON format"""
        import json
        
        graph_data = {
            'nodes': [],
            'edges': [],
            'metadata': {
                'num_operations': len(self.graph.operations),
                'num_dependencies': len(self.graph.dependencies)
            }
        }
        
        # Add nodes
        for op_id, op in self.graph.operations.items():
            node_data = {
                'id': op_id,
                'path': op.path,
                'method': op.method.value,
                'resource_type': op.resource_type,
                'consumes': list(op.consumes),
                'produces': list(op.produces),
                'is_interesting': op.is_interesting(),
                'annotations': op.annotations
            }
            graph_data['nodes'].append(node_data)
        
        # Add edges
        for dep in self.graph.dependencies:
            edge_data = {
                'source': dep.source.operation_id,
                'target': dep.target.operation_id,
                'type': dep.type.value,
                'confidence': dep.confidence,
                'parameter_mapping': dep.parameter_mapping,
                'reason': dep.reason,
                'verified': dep.verified
            }
            graph_data['edges'].append(edge_data)
        
        with open(output_path, 'w') as f:
            json.dump(graph_data, f, indent=2)
        
        print(f"Exported JSON graph to {output_path}")
    
    def visualize_interactive(self, output_path: str = 'graph.html'):
        """Create interactive HTML visualization using vis.js"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>API Dependency Graph</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        #mynetwork {
            width: 100%;
            height: 800px;
            border: 1px solid lightgray;
        }
        .legend {
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <h1>API Dependency Graph</h1>
    <div class="legend">
        <h3>Legend</h3>
        <div><span style="color: #4CAF50;">■</span> GET Operations</div>
        <div><span style="color: #2196F3;">■</span> POST Operations</div>
        <div><span style="color: #FF9800;">■</span> PUT/PATCH Operations</div>
        <div><span style="color: #F44336;">■</span> DELETE Operations</div>
    </div>
    <div id="mynetwork"></div>
    <script type="text/javascript">
        // Graph data
        var nodes = new vis.DataSet(NODES_DATA);
        var edges = new vis.DataSet(EDGES_DATA);
        
        var container = document.getElementById('mynetwork');
        var data = {
            nodes: nodes,
            edges: edges
        };
        
        var options = {
            nodes: {
                shape: 'box',
                margin: 10,
                widthConstraint: {
                    maximum: 200
                }
            },
            edges: {
                arrows: 'to',
                smooth: {
                    type: 'cubicBezier'
                }
            },
            physics: {
                enabled: true,
                barnesHut: {
                    gravitationalConstant: -2000,
                    springConstant: 0.001,
                    springLength: 200
                }
            },
            layout: {
                hierarchical: {
                    enabled: true,
                    direction: 'UD',
                    sortMethod: 'directed'
                }
            }
        };
        
        var network = new vis.Network(container, data, options);
        
        network.on("click", function(params) {
            if (params.nodes.length > 0) {
                var nodeId = params.nodes[0];
                var node = nodes.get(nodeId);
                alert('Operation: ' + node.label + '\\n' +
                      'ID: ' + node.id + '\\n' +
                      'Consumes: ' + (node.consumes || []).join(', ') + '\\n' +
                      'Produces: ' + (node.produces || []).join(', '));
            }
        });
    </script>
</body>
</html>
        """
        
        # Prepare nodes data
        nodes_data = []
        for op_id, op in self.graph.operations.items():
            nodes_data.append({
                'id': op_id,
                'label': f"{op.method.value}\\n{op.path}",
                'color': self._get_node_color(op),
                'consumes': list(op.consumes),
                'produces': list(op.produces)
            })
        
        # Prepare edges data
        edges_data = []
        for dep in self.graph.dependencies:
            edges_data.append({
                'from': dep.source.operation_id,
                'to': dep.target.operation_id,
                'label': dep.type.value,
                'color': self._get_edge_color(dep.type),
                'title': dep.reason or ''
            })
        
        # Replace placeholders
        html_content = html_template.replace(
            'NODES_DATA', 
            json.dumps(nodes_data)
        ).replace(
            'EDGES_DATA',
            json.dumps(edges_data)
        )
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        
        print(f"Created interactive visualization at {output_path}")
    
    def _get_node_color(self, operation: Operation) -> str:
        """Get color for operation node based on HTTP method"""
        color_map = {
            HTTPMethod.GET: '#4CAF50',      # Green
            HTTPMethod.POST: '#2196F3',     # Blue
            HTTPMethod.PUT: '#FF9800',      # Orange
            HTTPMethod.PATCH: '#FF9800',    # Orange
            HTTPMethod.DELETE: '#F44336',   # Red
        }
        return color_map.get(operation.method, '#9E9E9E')
    
    def _get_edge_color(self, dep_type: DependencyType) -> str:
        """Get color for dependency edge based on type"""
        color_map = {
            DependencyType.PARAMETER_DATA: '#2196F3',
            DependencyType.CRUD: '#4CAF50',
            DependencyType.AUTHENTICATION: '#FF5722',
            DependencyType.AUTHORIZATION: '#FF5722',
            DependencyType.NESTED_RESOURCE: '#9C27B0',
            DependencyType.WORKFLOW: '#00BCD4',
            DependencyType.CONSTRAINT: '#FFC107',
            DependencyType.TRANSITIVE: '#9E9E9E',
            DependencyType.DYNAMIC: '#E91E63'
        }
        return color_map.get(dep_type, '#000000')

class AnnotationExporter:
    """Export dependency graph back to annotated OpenAPI specification"""
    
    def __init__(self, graph: DependencyGraph, original_spec: Dict[str, Any]):
        self.graph = graph
        self.original_spec = original_spec
    
    def export_annotated_spec(self, output_path: str):
        """Export OpenAPI spec with NAUTILUS-style annotations"""
        annotated_spec = self.original_spec.copy()
        
        # Add annotations to each operation
        for path, path_item in annotated_spec.get('paths', {}).items():
            for method, operation_spec in path_item.items():
                if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    operation_id = operation_spec.get('operationId', 
                                                     f"{method}_{path.replace('/', '_')}")
                    
                    if operation_id in self.graph.operations:
                        op = self.graph.operations[operation_id]
                        
                        # Add operation annotations
                        op_annotations = self._create_operation_annotations(op)
                        if op_annotations:
                            operation_spec['x-operation-annotation'] = op_annotations
                        
                        # Add parameter annotations
                        self._add_parameter_annotations(operation_spec, op)
        
        # Write annotated spec
        with open(output_path, 'w') as f:
            yaml.dump(annotated_spec, f, default_flow_style=False, sort_keys=False)
        
        print(f"Exported annotated OpenAPI specification to {output_path}")
    
    def _create_operation_annotations(self, operation: Operation) -> Dict[str, Any]:
        """Create operation-level annotations"""
        annotations = {}
        
        # Get dependencies
        deps = self.graph.get_dependencies(operation)
        
        if deps:
            dep_operations = []
            for dep in deps:
                # Only include high-confidence dependencies
                if dep.confidence >= 0.7:
                    dep_operations.append(dep.source.operation_id)
            
            if dep_operations:
                annotations['dep-operations'] = dep_operations
        
        # Check if it's a terminal operation
        if operation.annotations.get('term_operations', False):
            annotations['term-operations'] = True
        
        # Add parameter aliases
        if 'parameter_aliases' in operation.annotations:
            annotations['aliases'] = operation.annotations['parameter_aliases']
        
        return annotations
    
    def _add_parameter_annotations(self, operation_spec: Dict[str, Any], 
                                   operation: Operation):
        """Add parameter-level annotations"""
        # Annotate path parameters
        for param_spec in operation_spec.get('parameters', []):
            param_name = param_spec.get('name')
            
            # Find corresponding parameter
            param = next((p for p in operation.parameters if p.name == param_name), None)
            
            if param:
                param_annotation = self._create_parameter_annotation(param, operation)
                if param_annotation:
                    param_spec['x-parameter-annotation'] = param_annotation
        
        # Annotate request body parameters
        if 'requestBody' in operation_spec:
            request_body = operation_spec['requestBody']
            content = request_body.get('content', {})
            
            for media_type, media_spec in content.items():
                if 'schema' in media_spec:
                    schema = media_spec['schema']
                    if 'properties' in schema:
                        for prop_name, prop_spec in schema['properties'].items():
                            param_annotation = self._create_parameter_annotation_by_name(
                                prop_name, operation
                            )
                            if param_annotation:
                                prop_spec['x-parameter-annotation'] = param_annotation
    
    def _create_parameter_annotation(self, parameter: Parameter, 
                                     operation: Operation) -> Dict[str, Any]:
        """Create parameter-level annotation"""
        annotation = {
            'strategy': {
                'Example': parameter.example is not None,
                'Dynamic': parameter.name in operation.consumes,
                'Success': operation.annotations.get('success', False),
                'Mutation': 1.0 if parameter.constraints else 0.5
            }
        }
        
        # Add aliases
        if 'parameter_aliases' in operation.annotations:
            if parameter.name in operation.annotations['parameter_aliases']:
                annotation['alias'] = [operation.annotations['parameter_aliases'][parameter.name]]
        
        return annotation
    
    def _create_parameter_annotation_by_name(self, param_name: str, 
                                            operation: Operation) -> Dict[str, Any]:
        """Create parameter annotation by name (for body parameters)"""
        annotation = {
            'strategy': {
                'Example': True,  # Assume examples exist in schema
                'Dynamic': param_name in operation.consumes,
                'Success': operation.annotations.get('success', False),
                'Mutation': 0.5
            }
        }
        
        return annotation
    
import time
from typing import Optional

class CompleteDependencyGraphBuilder:
    """
    Complete algorithm for building and maintaining a dependency graph
    from OpenAPI specifications with dynamic updates
    """
    
    def __init__(self, spec_path: str, enable_dynamic_updates: bool = False):
        self.spec_path = spec_path
        self.enable_dynamic_updates = enable_dynamic_updates
        
        # Core components
        self.parser: Optional[OpenAPIParser] = None
        self.graph: Optional[DependencyGraph] = None
        self.dynamic_manager: Optional[DynamicDependencyManager] = None
        self.analyzer: Optional[GraphAnalyzer] = None
        self.visualizer: Optional[GraphVisualizer] = None
        
    def build_complete_graph(self) -> DependencyGraph:
        """
        Main algorithm to build complete dependency graph
        
        Steps:
        1. Parse OpenAPI specification
        2. Build static dependency graph
        3. Optimize and analyze
        4. (Optional) Enable dynamic updates
        5. Export results
        """
        
        print("=" * 80)
        print("DEPENDENCY GRAPH BUILDER")
        print("=" * 80)
        
        start_time = time.time()
        
        # Step 1: Build initial static graph
        print("\n[PHASE 1] Building Static Dependency Graph")
        print("-" * 80)
        builder = DependencyGraphBuilder(self.spec_path)
        self.graph = builder.build()
        
        # Step 2: Analyze graph
        # print("\n[PHASE 2] Analyzing Dependency Graph")
        # print("-" * 80)
        # self.analyzer = GraphAnalyzer(self.graph)
        # analysis = self.analyzer.analyze()
        
        # self._print_analysis(analysis)
        
        # Step 3: Setup dynamic updates if enabled
        if self.enable_dynamic_updates:
            print("\n[PHASE 3] Enabling Dynamic Dependency Management")
            print("-" * 80)
            self.dynamic_manager = DynamicDependencyManager(self.graph)
            print("  ✓ Dynamic updates enabled")
            print("  ℹ️  Use record_execution() to update graph based on runtime feedback")
        
        # Step 4: Create visualizer
        self.visualizer = GraphVisualizer(self.graph)
        
        elapsed = time.time() - start_time
        print("\n" + "=" * 80)
        print(f"✓ Graph building completed in {elapsed:.2f} seconds")
        print("=" * 80)
        
        return self.graph
    
    def _print_analysis(self, analysis: Dict[str, Any]):
        """Print analysis results"""
        print("\nBasic Statistics:")
        for key, value in analysis['basic_stats'].items():
            print(f"  {key}: {value}")
        
        print("\nComplexity Metrics:")
        for key, value in analysis['complexity_metrics'].items():
            print(f"  {key}: {value:.2f}")
        
        if analysis['critical_paths']:
            print("\nCritical Paths:")
            for i, path in enumerate(analysis['critical_paths'][:3], 1):
                print(f"  {i}. {' -> '.join(path)}")
        
        if analysis['bottlenecks']:
            print(f"\nBottleneck Operations: {len(analysis['bottlenecks'])}")
            for op_id in analysis['bottlenecks'][:5]:
                print(f"  - {op_id}")
        
        if analysis['recommendations']:
            print("\nRecommendations:")
            for rec in analysis['recommendations']:
                print(f"  {rec}")
    
    def export_all_formats(self, output_dir: str = './output'):
        """Export graph in all available formats"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        print("\n[EXPORT] Exporting dependency graph...")
        
        # Export annotated OpenAPI spec
        parser = OpenAPIParser(self.spec_path)
        original_spec = parser.spec if hasattr(parser, 'spec') else {}
        
        exporter = AnnotationExporter(self.graph, original_spec)
        exporter.export_annotated_spec(f"{output_dir}/annotated_spec.yaml")
        
        # Export visualizations
        self.visualizer.export_json(f"{output_dir}/graph.json")
        self.visualizer.export_graphml(f"{output_dir}/graph.graphml")
        self.visualizer.export_dot(f"{output_dir}/graph.dot")
        self.visualizer.visualize_interactive(f"{output_dir}/graph.html")
        
        print(f"\n✓ All exports completed in {output_dir}/")
    
    def get_operation_sequence(self, operation_id: str) -> List[Operation]:
        """Get the complete operation sequence for a given operation"""
        if operation_id not in self.graph.operations:
            raise ValueError(f"Operation {operation_id} not found")
        
        operation = self.graph.operations[operation_id]
        return self.graph.get_operation_sequence(operation)
    
    def simulate_execution(self, operation_id: str, success: bool, 
                          response: Dict[str, Any], parameters: Dict[str, Any]):
        """Simulate operation execution for dynamic learning"""
        if not self.enable_dynamic_updates:
            raise RuntimeError("Dynamic updates not enabled")
        
        if operation_id not in self.graph.operations:
            raise ValueError(f"Operation {operation_id} not found")
        
        operation = self.graph.operations[operation_id]
        self.dynamic_manager.record_execution(operation, success, response, parameters)
    
    def get_dependency_types_summary(self) -> Dict[DependencyType, int]:
        """Get summary of dependency types in the graph"""
        summary = {}
        for dep in self.graph.dependencies:
            if dep.type not in summary:
                summary[dep.type] = 0
            summary[dep.type] += 1
        return summary


# ============================================================================
# MAIN ALGORITHM
# ============================================================================

def build_dependency_graph_from_openapi(
    spec_path: str,
    enable_dynamic: bool = False,
    export_results: bool = True,
    output_dir: str = './output'
) -> DependencyGraph:
    """
    Main algorithm to build dependency graph from OpenAPI specification
    
    Args:
        spec_path: Path to OpenAPI specification (YAML or JSON)
        enable_dynamic: Enable dynamic dependency updates
        export_results: Export graph in multiple formats
        output_dir: Directory for output files
        
    Returns:
        DependencyGraph: Complete dependency graph with all relationships
        
    Algorithm Steps:
    ----------------
    1. PARSE OpenAPI Specification
       - Load YAML/JSON
       - Extract operations, parameters, schemas
       - Validate specification
       
    2. BUILD Static Dependencies
       a. Parameter-wise dependencies (producer-consumer)
          - Exact name matching
          - Fuzzy name matching
          - Type compatibility checking
       
       b. CRUD dependencies
          - Resource identification
          - Method-based relationships
          - Path hierarchy analysis
       
       c. Logical dependencies
          - Authentication requirements
          - Authorization patterns
          - Business workflow patterns
       
       d. Nested resource dependencies
          - URL path hierarchy
          - Parent-child relationships
       
       e. Constraint dependencies
          - Enum constraints
          - Range constraints
          - Pattern constraints
       
       f. Transitive dependencies
          - Compute transitive closure
          - Prune redundant edges
    
    3. RESOLVE Conflicts
       - Merge duplicate dependencies
       - Prioritize by confidence
       - Handle contradictions
    
    4. OPTIMIZE Graph
       - Transitive reduction
       - Cycle detection and breaking
       - Path simplification
    
    5. ANALYZE Graph
       - Complexity metrics
       - Critical paths
       - Bottleneck identification
       - Quality recommendations
    
    6. (Optional) ENABLE Dynamic Updates
       - Runtime feedback integration
       - Parameter alias discovery
       - Confidence adjustment
       - New dependency discovery
    
    7. EXPORT Results
       - Annotated OpenAPI spec
       - Multiple visualization formats
       - Analysis reports
    
    Dependency Types Extracted:
    ---------------------------
    1. PARAMETER_DATA: Producer-consumer relationships
    2. CRUD: RESTful semantic relationships
    3. AUTHENTICATION: Auth requirements
    4. AUTHORIZATION: Permission requirements
    5. NESTED_RESOURCE: URL hierarchy
    6. WORKFLOW: Business logic sequences
    7. CONSTRAINT: Parameter constraints
    8. TRANSITIVE: Inferred relationships
    9. DYNAMIC: Runtime discovered
    
    Time Complexity:
    ----------------
    - Parsing: O(n) where n = number of operations
    - Parameter matching: O(n²) in worst case
    - CRUD analysis: O(n²) per resource type
    - Transitive closure: O(n³) for Floyd-Warshall
    - Optimization: O(n³) for transitive reduction
    - Overall: O(n³) for complete algorithm
    
    Space Complexity:
    -----------------
    - Graph storage: O(n + e) where e = number of edges
    - Indexes: O(n * p) where p = avg parameters per operation
    - Overall: O(n * p + e)
    """
    
    # Initialize builder
    builder = CompleteDependencyGraphBuilder(spec_path)
    
    # Build complete graph
    graph = builder.build_complete_graph()
    
    # Export if requested
    if export_results:
        builder.export_all_formats(output_dir)
    
    # Print dependency summary
    print("\nDependency Types Summary:")
    summary = builder.get_dependency_types_summary()
    for dep_type, count in sorted(summary.items(), key=lambda x: x[1], reverse=True):
        print(f"  {dep_type.value}: {count}")
    
    return graph
# Example 1: Basic usage
def example_basic():
    """Basic dependency graph building"""
    graph = build_dependency_graph_from_openapi(
        spec_path='api_spec.yaml',
        enable_dynamic=False,
        export_results=True
    )
    
    # Get sequence for specific operation
    sequence = graph.get_operation_sequence(graph.operations['createUser'])
    print("\nOperation Sequence:")
    for op in sequence:
        print(f"  {op.method.value} {op.path}")


# Example 2: With dynamic updates
def example_dynamic():
    """Building graph with dynamic updates"""
    builder = CompleteDependencyGraphBuilder(
        spec_path='api_spec.yaml',
        enable_dynamic_updates=True
    )
    
    graph = builder.build_complete_graph()
    
    # Simulate API execution
    builder.simulate_execution(
        operation_id='createUser',
        success=True,
        response={'id': 123, 'admin_token': 'abc123'},
        parameters={'username': 'test', 'email': 'test@example.com'}
    )
    
    # Graph automatically updates with new discovered parameters
    builder.export_all_formats()


# Example 3: Custom analysis
def example_analysis():
    """Custom graph analysis"""
    builder = CompleteDependencyGraphBuilder('api_spec.yaml')
    graph = builder.build_complete_graph()
    
    # Find all authentication dependencies
    auth_deps = [d for d in graph.dependencies 
                 if d.type == DependencyType.AUTHENTICATION]
    
    print(f"Found {len(auth_deps)} authentication dependencies")
    
    # Find operations requiring most dependencies
    dep_counts = {}
    for op in graph.operations.values():
        deps = graph.get_dependencies(op)
        dep_counts[op.operation_id] = len(deps)
    
    most_complex = sorted(dep_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\nMost Complex Operations:")
    for op_id, count in most_complex:
        print(f"  {op_id}: {count} dependencies")


# Example 4: Interactive exploration
def example_interactive():
    """Interactive graph exploration"""
    graph = build_dependency_graph_from_openapi('api_spec.yaml')
    
    while True:
        op_id = input("\nEnter operation ID (or 'quit'): ")
        if op_id == 'quit':
            break
        
        if op_id not in graph.operations:
            print("Operation not found")
            continue
        
        op = graph.operations[op_id]
        print(f"\nOperation: {op.method.value} {op.path}")
        print(f"Consumes: {', '.join(op.consumes)}")
        print(f"Produces: { ', '.join(op.produces)}")
        
        deps = graph.get_dependencies(op)
        if deps:
            print(f"\nDependencies ({len(deps)}):")
            for dep in deps:
                print(f"  ← {dep.source.operation_id} ({dep.type.value}, confidence: {dep.confidence:.2f})")
                print(f"     {dep.reason}")
        
        sequence = graph.get_operation_sequence(op)
        print(f"\nExecution Sequence ({len(sequence)} steps):")
        for i, seq_op in enumerate(sequence, 1):
            print(f"  {i}. {seq_op.method.value} {seq_op.path}")


if __name__ == '__main__':
    # Run examples
    print("Example 1: Basic Usage")
    print("=" * 80)
    example_basic()
    
    print("\n\nExample 3: Custom Analysis")
    print("=" * 80)
    example_analysis()