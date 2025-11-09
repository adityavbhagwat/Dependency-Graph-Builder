from typing import List, Tuple, Dict, Any
from .parser import OpenAPIParser
from .core import DependencyGraph
from .parameter_analyzer import ParameterDependencyAnalyzer
from .crud_analyzer import CRUDDependencyAnalyzer
from .logical_analyzer import LogicalDependencyAnalyzer
from .nested_analyzer import NestedResourceAnalyzer
from .constraint_analyzer import ConstraintDependencyAnalyzer
from .transitive_analyzer import TransitiveDependencyAnalyzer
from .dependency import Dependency

class DependencyGraphBuilder:
    """Main builder for constructing the dependency graph"""
    
    def __init__(self, spec_path: str):
        self.spec_path = spec_path
        self.parser = OpenAPIParser(spec_path)
        self.graph = DependencyGraph()
        self.operations: List = []
        
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
        print(f"  Resolved to {len(resolved_deps)} dependencies")
        
        for dep in resolved_deps:
            self.graph.add_dependency(dep)
        
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