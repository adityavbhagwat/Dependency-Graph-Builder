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
from .enums import DependencyType
import networkx as nx

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
        # Prefer higher-level semantics (CRUD/auth) over raw parameter matching
        resolved_deps.sort(key=self._dependency_priority)
        print(f"  Resolved to {len(resolved_deps)} dependencies")
        
        added_count = 0
        skipped_count = 0
        for dep in resolved_deps:
            if self.graph.add_dependency_if_acyclic(dep):
                added_count += 1
            else:
                skipped_count += 1
        print(f"  Added {added_count} dependencies, skipped {skipped_count} to prevent cycles.")
        
        # print("\nStep 5: Computing transitive dependencies...")
        # transitive_analyzer = TransitiveDependencyAnalyzer(self.graph)
        # transitive_deps = transitive_analyzer.analyze()
        
        # trans_added_count = 0
        # trans_skipped_count = 0
        # for dep in transitive_deps:
        #     if self.graph.add_dependency_if_acyclic(dep):
        #         trans_added_count += 1
        #     else:
        #         trans_skipped_count += 1
        # print(f"  Found {len(transitive_deps)} transitive dependencies. Added {trans_added_count}, skipped {trans_skipped_count}.")
                # --- NEW FINAL STEP ---
        print("\nStep 5: Performing transitive reduction to remove redundant edges...")
        initial_edge_count = self.graph.graph.number_of_edges()
        
        # This is the core of the fix. nx.transitive_reduction creates a new graph
        # with all redundant (transitive) edges removed.
        reduced_graph = nx.transitive_reduction(self.graph.graph)
        
        # Replace the old graph with the new, cleaner, reduced graph.
        self.graph.graph = reduced_graph
        
        final_edge_count = self.graph.graph.number_of_edges()
        print(f"  Graph optimized. Reduced edge count from {initial_edge_count} to {final_edge_count}.")
        
        return self.graph
    
    def _resolve_conflicts(self, dependencies: List[Dependency]) -> List[Dependency]:
        """Resolve conflicting dependencies including bidirectional conflicts"""
        # First, group by same direction (source, target)
        dep_map: Dict[Tuple[str, str], List[Dependency]] = {}
        
        for dep in dependencies:
            key = (dep.source.operation_id, dep.target.operation_id)
            if key not in dep_map:
                dep_map[key] = []
            dep_map[key].append(dep)
        
        # Merge same-direction dependencies
        merged = {}
        for key, deps in dep_map.items():
            if len(deps) == 1:
                merged[key] = deps[0]
            else:
                merged[key] = self._merge_dependencies(deps)
        
        # Now resolve bidirectional conflicts (A→B vs B→A)
        resolved = self._resolve_bidirectional_conflicts(merged)
        
        return resolved
    
    def _resolve_bidirectional_conflicts(self, dep_map: Dict[Tuple[str, str], Dependency]) -> List[Dependency]:
        """
        Resolve conflicts where we have both A→B and B→A.
        Keep the one with stronger semantic type (CRUD/auth beats parameter_data).
        """
        resolved = []
        processed = set()
        
        type_priority = {
            DependencyType.CRUD: 0,
            DependencyType.AUTHENTICATION: 1,
            DependencyType.AUTHORIZATION: 1,
            DependencyType.WORKFLOW: 2,
            DependencyType.NESTED_RESOURCE: 2,
            DependencyType.CONSTRAINT: 3,
            DependencyType.PARAMETER_DATA: 4,
            DependencyType.TRANSITIVE: 5,
            DependencyType.DYNAMIC: 5,
        }
        
        for (src, tgt), dep in dep_map.items():
            if (src, tgt) in processed:
                continue
            
            reverse_key = (tgt, src)
            if reverse_key in dep_map:
                # Bidirectional conflict! Choose the better one
                reverse_dep = dep_map[reverse_key]
                
                dep_priority = type_priority.get(dep.type, 99)
                rev_priority = type_priority.get(reverse_dep.type, 99)
                
                # Lower priority number = stronger semantic meaning
                if dep_priority < rev_priority:
                    resolved.append(dep)
                elif rev_priority < dep_priority:
                    resolved.append(reverse_dep)
                else:
                    # Same type priority - use confidence
                    if dep.confidence >= reverse_dep.confidence:
                        resolved.append(dep)
                    else:
                        resolved.append(reverse_dep)
                
                processed.add((src, tgt))
                processed.add(reverse_key)
            else:
                # No conflict
                resolved.append(dep)
                processed.add((src, tgt))
        
        return resolved
    
    def _merge_dependencies(self, deps: List[Dependency]) -> Dependency:
        """Merge multiple dependencies into one, preferring stronger semantic types"""
        # Sort by type priority first (stronger semantic types first), then confidence
        type_priority = {
            DependencyType.CRUD: 0,
            DependencyType.AUTHENTICATION: 1,
            DependencyType.AUTHORIZATION: 1,
            DependencyType.WORKFLOW: 2,
            DependencyType.NESTED_RESOURCE: 2,
            DependencyType.CONSTRAINT: 3,
            DependencyType.PARAMETER_DATA: 4,
            DependencyType.TRANSITIVE: 5,
            DependencyType.DYNAMIC: 5,
        }
        
        deps_sorted = sorted(deps, key=lambda d: (type_priority.get(d.type, 99), -d.confidence))
        base = deps_sorted[0]
        
        # Take the highest confidence value
        max_confidence = max(d.confidence for d in deps)
        base.confidence = max_confidence
        
        # Merge parameter mappings
        merged_params = {}
        for dep in reversed(deps_sorted):
            merged_params.update(dep.parameter_mapping)
        base.parameter_mapping = merged_params

        # Combine reasons
        reasons = {d.reason for d in deps if d.reason}
        base.reason = "; ".join(sorted(list(reasons)))
        
        return base

    def _dependency_priority(self, dep: Dependency) -> tuple:
        """
        Sort dependencies so stronger semantic signals are added first.
        This prevents low-level parameter matches from blocking CRUD ordering.
        """
        type_priority = {
            DependencyType.CRUD: 0,
            DependencyType.AUTHENTICATION: 1,
            DependencyType.AUTHORIZATION: 1,
            DependencyType.WORKFLOW: 2,
            DependencyType.NESTED_RESOURCE: 2,
            DependencyType.CONSTRAINT: 3,
            DependencyType.PARAMETER_DATA: 4,
            DependencyType.TRANSITIVE: 5,
            DependencyType.DYNAMIC: 5,
        }
        return (type_priority.get(dep.type, 99), -dep.confidence)