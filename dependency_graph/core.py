import networkx as nx
from typing import Dict, List, Set, Optional
from .operation import Operation
from .dependency import Dependency
from .enums import DependencyType

class DependencyGraph:
    """Main dependency graph structure, optimized for memory and DAG enforcement."""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        # Store full operation objects in a registry, not on graph nodes
        self.operations: Dict[str, Operation] = {}
        self.dependencies: List[Dependency] = []
        
        # Indexes for fast lookup
        self.producers: Dict[str, Set[str]] = {}  # param_name -> operation_ids
        self.consumers: Dict[str, Set[str]] = {}  # param_name -> operation_ids
        self.resource_map: Dict[str, List[str]] = {}  # resource -> operation_ids
        
    def add_operation(self, operation: Operation):
        """Add an operation node to the graph with a lightweight summary."""
        op_id = operation.operation_id
        if self.graph.has_node(op_id):
            return
            
        self.operations[op_id] = operation
        # Store a lightweight summary on the node, not the full object
        self.graph.add_node(op_id, **operation.get_summary())
        
        # Update indexes with operation_id instead of full object
        for param in operation.produces:
            self.producers.setdefault(param, set()).add(op_id)
            
        for param in operation.consumes:
            self.consumers.setdefault(param, set()).add(op_id)
            
        if operation.resource_type:
            self.resource_map.setdefault(operation.resource_type, []).append(op_id)
    
    def add_dependency_if_acyclic(self, dependency: Dependency) -> bool:
        """
        Add a dependency edge to the graph only if it does not create a cycle.
        Returns True if the edge was added, False otherwise.
        """
        source_id = dependency.source.operation_id
        target_id = dependency.target.operation_id

        if not self.graph.has_node(source_id) or not self.graph.has_node(target_id):
            return False

        # Cycle check: an edge u->v creates a cycle if a path v->u already exists.
        if nx.has_path(self.graph, target_id, source_id):
            return False

        self.dependencies.append(dependency)
        # Store a lightweight summary on the edge
        self.graph.add_edge(
            source_id,
            target_id,
            weight=1.0 - dependency.confidence,
            **dependency.get_graph_summary()
        )
        return True
    
    def get_dependencies(self, operation: Operation, 
                        dep_type: Optional[DependencyType] = None) -> List[Dependency]:
        """Get all dependencies for an operation"""
        deps = [d for d in self.dependencies if d.target.operation_id == operation.operation_id]
        if dep_type:
            deps = [d for d in deps if d.type == dep_type]
        return deps
    
    def get_operation_sequence(self, operation: Operation) -> List[Operation]:
        """Get ordered sequence of operations needed before this one"""
        op_id = operation.operation_id
        if op_id not in self.graph:
            return []
        
        ancestors = nx.ancestors(self.graph, op_id)
        subgraph = self.graph.subgraph(ancestors | {op_id})
        
        sequence_ids = list(nx.topological_sort(subgraph))
        return [self.operations[op_id] for op_id in sequence_ids]
    
    def detect_cycles(self) -> List[List[str]]:
        """Detect cycles in the dependency graph. Should return an empty list."""
        try:
            return list(nx.simple_cycles(self.graph))
        except nx.NetworkXError:
            return []
    
    def has_path(self, source: Operation, target: Operation) -> bool:
        """Check if there's a path from source to target"""
        return nx.has_path(self.graph, source.operation_id, target.operation_id)