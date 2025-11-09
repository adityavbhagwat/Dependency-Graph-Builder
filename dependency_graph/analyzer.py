import networkx as nx
from typing import Dict, Any, List, Set
from .core import DependencyGraph
from .dependency import Dependency

class GraphAnalyzer:
    """Analyze and provide insights about the dependency graph"""
    
    def __init__(self, graph: DependencyGraph):
        self.graph = graph
    
    def analyze(self) -> Dict[str, Any]:
        """Comprehensive graph analysis"""
        analysis = {
            'basic_stats': self._basic_statistics(),
            'complexity_metrics': self._complexity_metrics(),
            'critical_paths': self._find_critical_paths(),
            'dependency_clusters': self._find_clusters(),
            'bottlenecks': self._find_bottlenecks(),
            'recommendations': self._generate_recommendations()
        }
        
        return analysis
    
    def _basic_statistics(self) -> Dict[str, Any]:
        """Basic graph statistics"""
        return {
            'num_operations': len(self.graph.operations),
            'num_dependencies': len(self.graph.dependencies),
            'num_edges': self.graph.graph.number_of_edges(),
            'graph_density': nx.density(self.graph.graph),
            'is_dag': nx.is_directed_acyclic_graph(self.graph.graph),
            'num_cycles': len(self.graph.detect_cycles()) if not nx.is_directed_acyclic_graph(self.graph.graph) else 0
        }
    
    def _complexity_metrics(self) -> Dict[str, Any]:
        """Calculate complexity metrics"""
        # Maximum depth
        if nx.is_directed_acyclic_graph(self.graph.graph):
            max_depth = nx.dag_longest_path_length(self.graph.graph)
        else:
            max_depth = -1
        
        # Average dependencies per operation
        in_degrees = [d for n, d in self.graph.graph.in_degree()]
        out_degrees = [d for n, d in self.graph.graph.out_degree()]
        
        return {
            'max_sequence_depth': max_depth,
            'avg_incoming_deps': sum(in_degrees) / len(in_degrees) if in_degrees else 0,
            'avg_outgoing_deps': sum(out_degrees) / len(out_degrees) if out_degrees else 0,
            'max_incoming_deps': max(in_degrees) if in_degrees else 0,
            'max_outgoing_deps': max(out_degrees) if out_degrees else 0
        }
    
    def _find_critical_paths(self) -> List[List[str]]:
        """Find critical paths in the graph"""
        critical_paths = []
        
        if nx.is_directed_acyclic_graph(self.graph.graph):
            # Find longest path
            try:
                longest = nx.dag_longest_path(self.graph.graph)
                critical_paths.append(longest)
            except:
                pass
        
        return critical_paths
    
    def _find_clusters(self) -> List[Set[str]]:
        """Find strongly connected components / clusters"""
        # Convert to undirected for community detection
        undirected = self.graph.graph.to_undirected()
        
        # Use networkx community detection
        try:
            from networkx.algorithms import community
            communities = community.greedy_modularity_communities(undirected)
            return [set(c) for c in communities]
        except:
            return []
    
    def _find_bottlenecks(self) -> List[str]:
        """Find bottleneck operations (high betweenness centrality)"""
        betweenness = nx.betweenness_centrality(self.graph.graph)
        
        # Get top 10% as bottlenecks
        threshold = sorted(betweenness.values(), reverse=True)[int(len(betweenness) * 0.1)]
        bottlenecks = [op_id for op_id, score in betweenness.items() if score >= threshold]
        
        return bottlenecks
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        stats = self._basic_statistics()
        
        if not stats['is_dag']:
            recommendations.append(
                f"⚠️  Graph contains {stats['num_cycles']} cycles. Consider breaking them for cleaner sequences."
            )
        
        complexity = self._complexity_metrics()
        
        if complexity['max_sequence_depth'] > 10:
            recommendations.append(
                f"⚠️  Maximum sequence depth is {complexity['max_sequence_depth']}. "
                "Very deep sequences may be fragile."
            )
        
        if complexity['max_incoming_deps'] > 5:
            recommendations.append(
                f"⚠️  Some operations have {complexity['max_incoming_deps']} dependencies. "
                "Consider simplifying complex operations."
            )
        
        bottlenecks = self._find_bottlenecks()
        if bottlenecks:
            recommendations.append(
                f"ℹ️  Found {len(bottlenecks)} bottleneck operations that many paths go through."
            )
        
        return recommendations