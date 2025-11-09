import yaml
import json
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urlparse
from .operation import Operation
from .parameter import Parameter
from .response import Response
from .enums import HTTPMethod

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
        with open(self.spec_path, 'r',encoding='utf-8') as f:
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