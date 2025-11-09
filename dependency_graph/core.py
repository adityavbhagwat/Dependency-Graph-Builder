import networkx as nx
from typing import Dict, List, Set, Optional
from .operation import Operation
from .dependency import Dependency
from .enums import DependencyType
from dataclasses import dataclass

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
        
    def add_operation(self, operation: Operation):
        """Add an operation node to the graph"""
        self.operations[operation.operation_id] = operation
        self.graph.add_node(operation.operation_id, operation=operation)
        
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
    
    def add_dependency(self, dependency: Dependency):
        """Add a dependency edge to the graph"""
        self.dependencies.append(dependency)
        self.graph.add_edge(
            dependency.source.operation_id,
            dependency.target.operation_id,
            dependency=dependency,
            dep_type=dependency.type.value,
            weight=1.0 - dependency.confidence
        )
    
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