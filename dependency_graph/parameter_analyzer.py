from typing import Dict, List, Tuple
from .operation import Operation
from .dependency import Dependency
from .enums import DependencyType, HTTPMethod

class ParameterDependencyAnalyzer:
    """Analyze parameter-wise dependencies (producer-consumer)"""
    
    # Generic parameter names that exist across many resources and should NOT
    # create cross-resource dependencies
    GENERIC_PARAMS = {'id', 'name', 'status', 'type', 'description', 'created_at', 
                      'updated_at', 'timestamp', 'count', 'total', 'data', 'result',
                      'message', 'code', 'error', 'success', 'page', 'limit', 'offset'}
    
    def __init__(self, operations: List[Operation]):
        self.operations = operations
        self.dependencies: List[Dependency] = []
    
    def analyze(self) -> List[Dependency]:
        """Find all parameter-wise dependencies"""
        dependencies = []
        
        # Build producer-consumer maps with resource context
        # Key: (param_name, resource_type or None)
        producers: Dict[Tuple[str, str], List[Operation]] = {}
        consumers: Dict[Tuple[str, str], List[Operation]] = {}
        
        for op in self.operations:
            resource = op.resource_type or '__global__'
            
            for param in op.produces:
                key = (param, resource)
                if key not in producers:
                    producers[key] = []
                producers[key].append(op)
            
            for param in op.consumes:
                key = (param, resource)
                if key not in consumers:
                    consumers[key] = []
                consumers[key].append(op)
        
        # Match producers with consumers - ONLY within same resource or related resources
        for (param_name, prod_resource), prod_ops in producers.items():
            for (cons_param, cons_resource), cons_ops in consumers.items():
                if param_name != cons_param:
                    continue
                
                # Check if these resources should be linked
                if not self._should_link_resources(param_name, prod_resource, cons_resource):
                    continue
                    
                for producer in prod_ops:
                    for consumer in cons_ops:
                        if producer == consumer:
                            continue
                        
                        # Skip if this would create a semantically backward dependency
                        # (GET producing data for POST to consume)
                        if self._is_semantic_backward(producer, consumer):
                            continue
                            
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
        
        # Fuzzy matching - but with same resource constraints
        dependencies.extend(self._fuzzy_parameter_matching(producers, consumers))
        
        self.dependencies = dependencies
        return dependencies
    
    def _should_link_resources(self, param_name: str, prod_resource: str, cons_resource: str) -> bool:
        """
        Determine if a parameter dependency should be created between two resources.
        """
        # Same resource - always allow
        if prod_resource == cons_resource:
            return True
        
        # Generic parameters should NOT create cross-resource dependencies
        param_lower = param_name.lower()
        if param_lower in self.GENERIC_PARAMS:
            return False
        
        # Resource-specific IDs (like petId, userId, orderId) CAN link resources
        # e.g., petId from /pet can link to /store/order which uses petId
        if param_lower.endswith('id') and len(param_lower) > 2:
            # This is a specific ID like "petId", "orderId" - allow cross-resource
            return True
        
        # For other parameters, only allow if resources are related
        # (e.g., nested paths like /pet and /pet/{petId}/uploadImage)
        return False
    
    def _is_semantic_backward(self, producer: Operation, consumer: Operation) -> bool:
        """
        Check if creating producer->consumer would violate CRUD semantics.
        A GET should not be a dependency for a POST (create) on the same resource.
        """
        # Only check for same resource
        if producer.resource_type != consumer.resource_type:
            return False
        
        # GET producing for POST (create) is backward - you can't get before creating
        if producer.method == HTTPMethod.GET and consumer.method == HTTPMethod.POST:
            # Exception: if the POST is an action (like /login) not a create
            consumer_path_lower = consumer.path.lower()
            if any(action in consumer_path_lower for action in ['login', 'logout', 'search', 'find']):
                return False
            return True
        
        return False
    
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
                                   producers: Dict[Tuple[str, str], List[Operation]], 
                                   consumers: Dict[Tuple[str, str], List[Operation]]) -> List[Dependency]:
        """Find dependencies using fuzzy parameter name matching"""
        dependencies = []
        
        # Common parameter name variations
        variations = {
            'id': ['ID', 'Id', '_id', 'identifier'],
            'user_id': ['userId', 'user_ID', 'userID', 'uid'],
            'username': ['user_name', 'userName', 'login', 'user'],
            'pet_id': ['petId', 'pet_ID', 'petID'],
            'order_id': ['orderId', 'order_ID', 'orderID'],
        }
        
        for (prod_param, prod_resource), prod_ops in producers.items():
            for (cons_param, cons_resource), cons_ops in consumers.items():
                if prod_param == cons_param:
                    continue
                    
                # Only fuzzy match within same resource type
                if prod_resource != cons_resource:
                    continue
                    
                # Check if they're variations of the same parameter
                if self._are_parameter_variants(prod_param, cons_param, variations):
                    for producer in prod_ops:
                        for consumer in cons_ops:
                            if producer == consumer:
                                continue
                            # Skip semantically backward dependencies
                            if self._is_semantic_backward(producer, consumer):
                                continue
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