from typing import Dict, List
from .operation import Operation
from .dependency import Dependency
from .enums import DependencyType

class ParameterDependencyAnalyzer:
    """Analyze parameter-wise dependencies (producer-consumer)"""
    
    def __init__(self, operations: List[Operation]):
        self.operations = operations
        self.dependencies: List[Dependency] = []
    
    def analyze(self) -> List[Dependency]:
        """Find all parameter-wise dependencies"""
        dependencies = []
        
        # Build producer-consumer maps
        producers: Dict[str, List[Operation]] = {}
        consumers: Dict[str, List[Operation]] = {}
        
        for op in self.operations:
            for param in op.produces:
                if param not in producers:
                    producers[param] = []
                producers[param].append(op)
            
            for param in op.consumes:
                if param not in consumers:
                    consumers[param] = []
                consumers[param].append(op)
        
        # Match producers with consumers
        for param_name in producers:
            if param_name in consumers:
                for producer in producers[param_name]:
                    for consumer in consumers[param_name]:
                        if producer != consumer:
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
        
        # Fuzzy matching for similar parameter names
        dependencies.extend(self._fuzzy_parameter_matching(producers, consumers))
        
        self.dependencies = dependencies
        return dependencies
    
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
                                   producers: Dict[str, List[Operation]], 
                                   consumers: Dict[str, List[Operation]]) -> List[Dependency]:
        """Find dependencies using fuzzy parameter name matching"""
        dependencies = []
        
        # Common parameter name variations
        variations = {
            'id': ['ID', 'Id', '_id', 'identifier'],
            'user_id': ['userId', 'user_ID', 'userID', 'uid'],
            'username': ['user_name', 'userName', 'login', 'user'],
            # Add more variations
        }
        
        for prod_param, prod_ops in producers.items():
            for cons_param, cons_ops in consumers.items():
                if prod_param != cons_param:
                    # Check if they're variations of the same parameter
                    if self._are_parameter_variants(prod_param, cons_param, variations):
                        for producer in prod_ops:
                            for consumer in cons_ops:
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