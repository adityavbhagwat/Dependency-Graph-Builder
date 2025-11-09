from enum import Enum

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