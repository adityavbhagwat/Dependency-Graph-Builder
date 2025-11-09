import time
from typing import Dict, Any, Set, List
from .core import DependencyGraph
from .operation import Operation
from .dependency import Dependency
from .enums import DependencyType

class DynamicDependencyManager:
    """Manage dynamic updates to the dependency graph based on runtime feedback"""
    
    def __init__(self, graph: DependencyGraph):
        self.graph = graph
        self.execution_history: List[Dict[str, Any]] = []
        self.failure_threshold = 10  # From NAUTILUS paper
    
    def record_execution(self, operation: Operation, success: bool, 
                        response: Dict[str, Any], parameters: Dict[str, Any]):
        """Record execution result for learning"""
        record = {
            'operation': operation,
            'success': success,
            'response': response,
            'parameters': parameters,
            'timestamp': time.time()
        }
        self.execution_history.append(record)
        
        if success:
            self._handle_successful_execution(operation, response, parameters)
        else:
            self._handle_failed_execution(operation, response, parameters)
    
    def _handle_successful_execution(self, operation: Operation, 
                                     response: Dict[str, Any], 
                                     parameters: Dict[str, Any]):
        """Update graph based on successful execution"""
        # Update operation annotations
        if 'success' not in operation.annotations:
            operation.annotations['success'] = True
            operation.annotations['successful_params'] = parameters.copy()
        
        # Discover new produced parameters from response
        new_params = self._extract_parameters_from_response(response)
        if new_params - operation.produces:
            print(f"  Discovered new produced parameters for {operation.operation_id}: {new_params - operation.produces}")
            operation.produces.update(new_params)
            
            # Update producer index
            for param in new_params:
                if param not in self.graph.producers:
                    self.graph.producers[param] = set()
                self.graph.producers[param].add(operation)
            
            # Create new dependencies with consumers
            self._create_new_parameter_dependencies(operation, new_params)
        
        # Update dependency confidence
        deps = self.graph.get_dependencies(operation)
        for dep in deps:
            dep.success_count += 1
            dep.verified = True
            # Increase confidence
            dep.confidence = min(1.0, dep.confidence * 1.1)
    
    def _handle_failed_execution(self, operation: Operation, 
                                 response: Dict[str, Any], 
                                 parameters: Dict[str, Any]):
        """Update graph based on failed execution"""
        # Update dependency failure counts
        deps = self.graph.get_dependencies(operation)
        for dep in deps:
            dep.failure_count += 1
            
            # Remove dependency if it fails too many times
            if dep.failure_count >= self.failure_threshold:
                print(f"  Removing unreliable dependency: {dep.source.operation_id} -> {dep.target.operation_id}")
                self.graph.graph.remove_edge(dep.source.operation_id, dep.target.operation_id)
                self.graph.dependencies.remove(dep)
            else:
                # Decrease confidence
                dep.confidence = max(0.1, dep.confidence * 0.9)
    
    def _extract_parameters_from_response(self, response: Dict[str, Any]) -> Set[str]:
        """Extract parameter names from actual response"""
        params = set()
        
        def extract_recursive(obj, prefix=''):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    params.add(full_key)
                    extract_recursive(value, full_key)
            elif isinstance(obj, list) and obj:
                extract_recursive(obj[0], prefix)
        
        extract_recursive(response)
        return params
    
    def _create_new_parameter_dependencies(self, producer: Operation, new_params: Set[str]):
        """Create dependencies for newly discovered parameters"""
        for param in new_params:
            if param in self.graph.consumers:
                for consumer in self.graph.consumers[param]:
                    if producer != consumer:
                        dep = Dependency(
                            source=producer,
                            target=consumer,
                            type=DependencyType.DYNAMIC,
                            confidence=0.8,
                            parameter_mapping={param: param},
                            reason=f"Dynamically discovered: {param} produced by {producer.operation_id}"
                        )
                        self.graph.add_dependency(dep)
    
    def discover_parameter_aliases(self):
        """Discover parameter aliases from execution history"""
        # Analyze successful executions to find parameters that must have same value
        
        # Group executions by operation sequence
        sequences: Dict[str, List[Dict]] = {}
        
        for i, record in enumerate(self.execution_history):
            if record['success']:
                # Get preceding operations
                sequence_key = self._get_sequence_key(i)
                if sequence_key not in sequences:
                    sequences[sequence_key] = []
                sequences[sequence_key].append(record)
        
        # Look for parameter value patterns
        for seq_key, records in sequences.items():
            self._analyze_parameter_patterns(records)
    
    def _get_sequence_key(self, index: int) -> str:
        """Get sequence identifier for execution at index"""
        # Look back at recent operations
        lookback = 5
        start = max(0, index - lookback)
        ops = [self.execution_history[i]['operation'].operation_id 
               for i in range(start, index + 1)]
        return '->'.join(ops)
    
    def _analyze_parameter_patterns(self, records: List[Dict]):
        """Analyze parameter value patterns across operations"""
        if len(records) < 2:
            return
        
        # Compare parameter values across operations
        for i in range(len(records) - 1):
            for j in range(i + 1, len(records)):
                rec1, rec2 = records[i], records[j]
                
                params1 = rec1['parameters']
                params2 = rec2['parameters']
                
                # Find parameters with same values
                for p1, v1 in params1.items():
                    for p2, v2 in params2.items():
                        if p1 != p2 and v1 == v2 and v1 is not None:
                            # Potential alias
                            self._add_parameter_alias(
                                rec1['operation'], p1,
                                rec2['operation'], p2
                            )
    
    def _add_parameter_alias(self, op1: Operation, param1: str, 
                            op2: Operation, param2: str):
        """Add parameter alias annotation"""
        alias_key = 'parameter_aliases'
        
        if alias_key not in op1.annotations:
            op1.annotations[alias_key] = {}
        if alias_key not in op2.annotations:
            op2.annotations[alias_key] = {}
        
        # Cross-reference
        op1.annotations[alias_key][param1] = f"{op2.operation_id}.{param2}"
        op2.annotations[alias_key][param2] = f"{op1.operation_id}.{param1}"
        
        print(f"  Discovered alias: {op1.operation_id}.{param1} <-> {op2.operation_id}.{param2}")