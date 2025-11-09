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
        
        added_count = 0
        skipped_count = 0
        for dep in resolved_deps:
            if self.graph.add_dependency_if_acyclic(dep):
                added_count += 1
            else:
                skipped_count += 1
        print(f"  Added {added_count} dependencies, skipped {skipped_count} to prevent cycles.")
        
        print("\nStep 5: Computing transitive dependencies...")
        transitive_analyzer = TransitiveDependencyAnalyzer(self.graph)
        transitive_deps = transitive_analyzer.analyze()
        
        trans_added_count = 0
        trans_skipped_count = 0
        for dep in transitive_deps:
            if self.graph.add_dependency_if_acyclic(dep):
                trans_added_count += 1
            else:
                trans_skipped_count += 1
        print(f"  Found {len(transitive_deps)} transitive dependencies. Added {trans_added_count}, skipped {trans_skipped_count}.")
        
        return self.graph
    
    def _resolve_conflicts(self, dependencies: List[Dependency]) -> List[Dependency]:
        """Resolve conflicting dependencies"""
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
                resolved.append(self._merge_dependencies(deps))
        
        # Prioritize adding high-confidence edges first
        resolved.sort(key=lambda d: d.confidence, reverse=True)
        return resolved
    
    def _merge_dependencies(self, deps: List[Dependency]) -> Dependency:
        """Merge multiple dependencies into one"""
        deps_sorted = sorted(deps, key=lambda d: d.confidence, reverse=True)
        base = deps_sorted[0]
        
        merged_params = {}
        for dep in reversed(deps_sorted):
            merged_params.update(dep.parameter_mapping)
        base.parameter_mapping = merged_params

        reasons = {d.reason for d in deps if d.reason}
        base.reason = "; ".join(sorted(list(reasons)))
        
        return base