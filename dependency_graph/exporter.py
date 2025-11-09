import yaml
from typing import Dict, Any
from .core import DependencyGraph
from .parameter import Parameter
from .operation import Operation

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