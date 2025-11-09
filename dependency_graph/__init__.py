"""
Top-level package interface. Keep same external API as previous single-file module.
"""

from .complete_builder import CompleteDependencyGraphBuilder
from .builder import DependencyGraphBuilder
from .core import DependencyGraph
from .parser import OpenAPIParser
from .dynamic_manager import DynamicDependencyManager
from .analyzer import GraphAnalyzer
from .visualizer import GraphVisualizer
from .exporter import AnnotationExporter
from .dependency import Dependency
from .operation import Operation
from .parameter import Parameter
from .response import Response
from .enums import DependencyType, HTTPMethod

def build_dependency_graph_from_openapi(
    spec_path: str,
    enable_dynamic: bool = False,
    export_results: bool = True,
    output_dir: str = './output'
) -> DependencyGraph:
    """
    Backwards-compatible wrapper to build dependency graph from OpenAPI specification.
    """
    builder = CompleteDependencyGraphBuilder(spec_path, enable_dynamic_updates=enable_dynamic)
    graph = builder.build_complete_graph()
    
    if export_results:
        builder.export_all_formats(output_dir)
    
    print("\nDependency Types Summary:")
    summary = builder.get_dependency_types_summary()
    for dep_type, count in sorted(summary.items(), key=lambda x: x[1], reverse=True):
        print(f"  {dep_type.value}: {count}")
    
    return graph