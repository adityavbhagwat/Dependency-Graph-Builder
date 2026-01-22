"""
Coverage Analyzer for Dependency Graph Builder

This script analyzes the coverage and quality of dependency graphs generated
from OpenAPI specifications. It provides multiple meaningful coverage metrics
beyond simple node counting.

COVERAGE METRICS DEFINED:
========================

1. NODE COVERAGE (Basic)
   - Definition: % of API operations captured as graph nodes
   - Formula: (Operations in Graph / Operations in Spec) × 100%
   - Ideal: 100%

2. CONNECTIVITY COVERAGE
   - Definition: % of operations that are connected in the dependency graph
   - Formula: (Connected Nodes / Total Nodes) × 100%
   - Measures: How well the graph links operations together
   - Ideal: High % (except for GET-only APIs)

3. PARAMETER FLOW COVERAGE
   - Definition: % of consumed parameters that have a producer connected
   - Formula: (Consumed Params with Producers / Total Consumed Params) × 100%
   - Measures: How well parameter dependencies are captured
   - Ideal: High % indicates good data flow tracking

4. CRUD COVERAGE
   - Definition: % of expected CRUD relationships that are captured
   - Formula: (Captured CRUD Links / Expected CRUD Links) × 100%
   - Expected: For each resource with POST, should have links to GET/PUT/DELETE
   - Ideal: 100% means all CRUD relationships are properly linked

5. SEMANTIC CORRECTNESS
   - Definition: % of edges that follow correct semantic ordering
   - Formula: (Correct Orderings / Total Directional Edges) × 100%
   - Correct: POST→GET, POST→PUT, POST→DELETE, etc.
   - Ideal: High % indicates proper CRUD ordering

6. OVERALL GRAPH QUALITY SCORE
   - Definition: Weighted combination of all coverage metrics
   - Formula: Weighted average of all above metrics
   - Provides: Single score to compare graph quality

Usage:
    python coverage_analyzer.py [--output report.txt] [--verbose]
"""

import os
import json
import yaml
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field


@dataclass
class OperationStats:
    """Statistics for a single API's operations"""
    total_in_spec: int = 0
    total_in_graph: int = 0
    by_method: Dict[str, int] = field(default_factory=dict)
    

@dataclass
class DependencyStats:
    """Statistics for dependencies in a graph"""
    total_edges: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    post_to_get: int = 0
    post_to_put: int = 0
    post_to_delete: int = 0
    get_to_post: int = 0
    get_to_put: int = 0
    get_to_delete: int = 0
    

@dataclass
class GraphQuality:
    """Quality metrics for a dependency graph"""
    is_dag: bool = True
    num_components: int = 1
    isolated_nodes: int = 0
    connected_nodes: int = 0
    longest_path_length: int = 0


@dataclass
class ParameterFlowStats:
    """Statistics for parameter flow coverage"""
    total_consumed_params: int = 0
    consumed_with_producer: int = 0
    total_produced_params: int = 0
    produced_with_consumer: int = 0
    unique_param_names: Set[str] = field(default_factory=set)


@dataclass
class CRUDStats:
    """Statistics for CRUD relationship coverage"""
    total_resources: int = 0
    resources_with_create: int = 0
    expected_crud_links: int = 0
    captured_crud_links: int = 0
    missing_links: List[str] = field(default_factory=list)


@dataclass 
class CoverageMetrics:
    """All coverage metrics for an API"""
    node_coverage: float = 0.0           # % of operations captured
    connectivity_coverage: float = 0.0    # % of nodes connected
    parameter_flow_coverage: float = 0.0  # % of params with flow
    crud_coverage: float = 0.0            # % of CRUD links captured
    semantic_correctness: float = 0.0     # % of correct orderings
    overall_score: float = 0.0            # Weighted overall score


@dataclass
class APIAnalysis:
    """Complete analysis for a single API"""
    name: str
    spec_path: str
    output_dir: str
    operations: OperationStats = field(default_factory=OperationStats)
    dependencies: DependencyStats = field(default_factory=DependencyStats)
    quality: GraphQuality = field(default_factory=GraphQuality)
    param_flow: ParameterFlowStats = field(default_factory=ParameterFlowStats)
    crud_stats: CRUDStats = field(default_factory=CRUDStats)
    coverage: CoverageMetrics = field(default_factory=CoverageMetrics)
    edge_ratio: float = 0.0
    issues: List[str] = field(default_factory=list)


class CoverageAnalyzer:
    """
    Analyzes coverage of dependency graphs against OpenAPI specifications.
    Provides multiple meaningful coverage metrics.
    """
    
    # Mapping of spec files to their output directories
    SPEC_MAPPINGS = {
        'simple_api.yaml': 'output_simple_api',
        'openapi_specs/petstore.yaml': 'output_petstore_fixed',
        'user.yaml': 'output_user',
        'market.yaml': 'output_market',
        'spotify.yaml': 'output_spotify',
        'person.yaml': 'output_person',
        'project.yaml': 'output_project',
        'features.yaml': 'output_features',
        'fdic.yaml': 'output_fdic',
        'genome-nexus.yaml': 'output_genome_nexus',
        'rest-countries.yaml': 'output_rest_countries',
        'language-tool.yaml': 'output_language_tool',
        'ohsome.yaml': 'output_ohsome',
        'openapi_specs/github.json': 'output_github',
    }
    
    # Weights for overall score calculation
    METRIC_WEIGHTS = {
        'node_coverage': 0.20,
        'connectivity_coverage': 0.20,
        'parameter_flow_coverage': 0.20,
        'crud_coverage': 0.25,
        'semantic_correctness': 0.15,
    }
    
    def __init__(self, base_dir: str = '.', verbose: bool = False):
        self.base_dir = base_dir
        self.verbose = verbose
        self.analyses: List[APIAnalysis] = []
        
    def analyze_all(self) -> List[APIAnalysis]:
        """Analyze all available API specs and their graphs"""
        self.analyses = []
        
        for spec_path, output_dir in self.SPEC_MAPPINGS.items():
            full_spec_path = os.path.join(self.base_dir, spec_path)
            full_output_dir = os.path.join(self.base_dir, output_dir)
            
            if os.path.exists(full_spec_path) and os.path.exists(full_output_dir):
                analysis = self._analyze_single_api(spec_path, output_dir)
                if analysis:
                    self.analyses.append(analysis)
                    
        return self.analyses
    
    def _analyze_single_api(self, spec_path: str, output_dir: str) -> Optional[APIAnalysis]:
        """Analyze a single API spec and its generated graph"""
        full_spec_path = os.path.join(self.base_dir, spec_path)
        full_output_dir = os.path.join(self.base_dir, output_dir)
        
        api_name = os.path.splitext(os.path.basename(spec_path))[0]
        
        analysis = APIAnalysis(
            name=api_name,
            spec_path=spec_path,
            output_dir=output_dir
        )
        
        # Analyze OpenAPI spec
        spec_ops = self._count_spec_operations(full_spec_path)
        if spec_ops is None:
            return None
            
        analysis.operations.total_in_spec = sum(spec_ops.values())
        analysis.operations.by_method = spec_ops
        
        # Load graph data
        graph_data = self._load_graph_json(full_output_dir)
        stats_data = self._load_graph_stats(full_output_dir)
        
        if graph_data:
            analysis.operations.total_in_graph = len(graph_data.get('nodes', []))
            analysis.dependencies = self._analyze_dependencies(graph_data)
            analysis.param_flow = self._analyze_parameter_flow(graph_data)
            analysis.crud_stats = self._analyze_crud_coverage(graph_data)
            
        if stats_data:
            analysis.quality = self._analyze_quality(stats_data, graph_data)
            
        # Calculate all coverage metrics
        analysis.coverage = self._calculate_coverage_metrics(analysis)
        
        # Calculate edge ratio
        if analysis.operations.total_in_graph > 0:
            analysis.edge_ratio = analysis.dependencies.total_edges / analysis.operations.total_in_graph
            
        # Identify issues
        analysis.issues = self._identify_issues(analysis)
        
        return analysis
    
    def _count_spec_operations(self, spec_path: str) -> Optional[Dict[str, int]]:
        """Count operations in an OpenAPI spec by HTTP method"""
        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                if spec_path.endswith('.json'):
                    spec = json.load(f)
                else:
                    spec = yaml.safe_load(f)
                    
            ops = {'GET': 0, 'POST': 0, 'PUT': 0, 'DELETE': 0, 'PATCH': 0}
            paths = spec.get('paths', {})
            
            for path, path_item in paths.items():
                if path_item is None:
                    continue
                for method in ['get', 'post', 'put', 'delete', 'patch']:
                    if method in path_item:
                        ops[method.upper()] += 1
                        
            return ops
        except Exception as e:
            if self.verbose:
                print(f"Error reading spec {spec_path}: {e}")
            return None
    
    def _load_graph_json(self, output_dir: str) -> Optional[Dict]:
        """Load the graph.json file"""
        graph_file = os.path.join(output_dir, 'graph.json')
        try:
            with open(graph_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    def _load_graph_stats(self, output_dir: str) -> Optional[Dict]:
        """Load the graph_stats.json file"""
        stats_file = os.path.join(output_dir, 'graph_stats.json')
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    def _analyze_dependencies(self, graph_data: Dict) -> DependencyStats:
        """Analyze dependencies in the graph"""
        stats = DependencyStats()
        edges = graph_data.get('edges', [])
        nodes = {n['id']: n for n in graph_data.get('nodes', [])}
        
        stats.total_edges = len(edges)
        
        for edge in edges:
            # Count by type
            edge_type = edge.get('type', 'unknown')
            stats.by_type[edge_type] = stats.by_type.get(edge_type, 0) + 1
            
            # Check directional ordering
            src_node = nodes.get(edge.get('source'))
            tgt_node = nodes.get(edge.get('target'))
            
            if src_node and tgt_node:
                src_method = src_node.get('method', '')
                tgt_method = tgt_node.get('method', '')
                
                # Track all directional patterns
                if src_method == 'POST':
                    if tgt_method == 'GET':
                        stats.post_to_get += 1
                    elif tgt_method == 'PUT':
                        stats.post_to_put += 1
                    elif tgt_method == 'DELETE':
                        stats.post_to_delete += 1
                elif src_method == 'GET':
                    if tgt_method == 'POST':
                        stats.get_to_post += 1
                    elif tgt_method == 'PUT':
                        stats.get_to_put += 1
                    elif tgt_method == 'DELETE':
                        stats.get_to_delete += 1
                    
        return stats
    
    def _analyze_parameter_flow(self, graph_data: Dict) -> ParameterFlowStats:
        """Analyze parameter flow coverage"""
        stats = ParameterFlowStats()
        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])
        
        # Collect all produced and consumed parameters
        producers: Dict[str, Set[str]] = {}  # param -> set of operation ids
        consumers: Dict[str, Set[str]] = {}  # param -> set of operation ids
        
        for node in nodes:
            op_id = node.get('id', '')
            
            # Get produced parameters
            produced = node.get('produces', [])
            if isinstance(produced, list):
                for param in produced:
                    stats.unique_param_names.add(param)
                    if param not in producers:
                        producers[param] = set()
                    producers[param].add(op_id)
                    stats.total_produced_params += 1
            
            # Get consumed parameters
            consumed = node.get('consumes', [])
            if isinstance(consumed, list):
                for param in consumed:
                    stats.unique_param_names.add(param)
                    if param not in consumers:
                        consumers[param] = set()
                    consumers[param].add(op_id)
                    stats.total_consumed_params += 1
        
        # Check which consumed parameters have producers connected via edges
        edge_connections = set()
        for edge in edges:
            edge_connections.add((edge.get('source'), edge.get('target')))
        
        # For each consumed parameter, check if there's a producer connected
        for param, consumer_ops in consumers.items():
            if param in producers:
                producer_ops = producers[param]
                # Check if any producer is connected to any consumer
                for prod_op in producer_ops:
                    for cons_op in consumer_ops:
                        if (prod_op, cons_op) in edge_connections:
                            stats.consumed_with_producer += 1
                            break
                    else:
                        continue
                    break
        
        # Check which produced parameters have consumers connected
        for param, producer_ops in producers.items():
            if param in consumers:
                consumer_ops = consumers[param]
                for prod_op in producer_ops:
                    for cons_op in consumer_ops:
                        if (prod_op, cons_op) in edge_connections:
                            stats.produced_with_consumer += 1
                            break
                    else:
                        continue
                    break
        
        return stats
    
    def _analyze_crud_coverage(self, graph_data: Dict) -> CRUDStats:
        """Analyze CRUD relationship coverage"""
        stats = CRUDStats()
        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])
        
        # Group operations by resource type
        resources: Dict[str, Dict[str, List[str]]] = {}
        
        for node in nodes:
            resource = node.get('resource_type')
            if not resource:
                continue
                
            method = node.get('method', '')
            op_id = node.get('id', '')
            
            if resource not in resources:
                resources[resource] = {'POST': [], 'GET': [], 'PUT': [], 'DELETE': [], 'PATCH': []}
            
            if method in resources[resource]:
                resources[resource][method].append(op_id)
        
        stats.total_resources = len(resources)
        
        # Build edge set for quick lookup
        edge_set = set()
        for edge in edges:
            edge_set.add((edge.get('source'), edge.get('target')))
        
        # For each resource with POST, check CRUD links
        for resource, ops in resources.items():
            post_ops = ops.get('POST', [])
            if not post_ops:
                continue
                
            stats.resources_with_create += 1
            
            get_ops = ops.get('GET', [])
            put_ops = ops.get('PUT', []) + ops.get('PATCH', [])
            delete_ops = ops.get('DELETE', [])
            
            # Expected links: POST should link to GET, PUT, DELETE
            for post_op in post_ops:
                for get_op in get_ops:
                    stats.expected_crud_links += 1
                    if (post_op, get_op) in edge_set:
                        stats.captured_crud_links += 1
                    else:
                        stats.missing_links.append(f"{post_op} → {get_op}")
                        
                for put_op in put_ops:
                    stats.expected_crud_links += 1
                    if (post_op, put_op) in edge_set:
                        stats.captured_crud_links += 1
                    else:
                        stats.missing_links.append(f"{post_op} → {put_op}")
                        
                for del_op in delete_ops:
                    stats.expected_crud_links += 1
                    if (post_op, del_op) in edge_set:
                        stats.captured_crud_links += 1
                    else:
                        stats.missing_links.append(f"{post_op} → {del_op}")
        
        return stats
    
    def _analyze_quality(self, stats_data: Dict, graph_data: Optional[Dict]) -> GraphQuality:
        """Analyze quality metrics from stats"""
        quality = GraphQuality()
        
        basic = stats_data.get('basic', {})
        quality.is_dag = basic.get('is_dag', True)
        
        components = stats_data.get('components', {})
        quality.num_components = components.get('count', 1)
        
        longest_path = stats_data.get('longest_path', {})
        quality.longest_path_length = longest_path.get('length', 0) or 0
        
        # Calculate connected/isolated nodes
        if graph_data:
            nodes = graph_data.get('nodes', [])
            edges = graph_data.get('edges', [])
            
            connected = set()
            for edge in edges:
                connected.add(edge.get('source'))
                connected.add(edge.get('target'))
                
            quality.connected_nodes = len(connected)
            quality.isolated_nodes = len(nodes) - len(connected)
            
        return quality
    
    def _calculate_coverage_metrics(self, analysis: APIAnalysis) -> CoverageMetrics:
        """Calculate all coverage metrics"""
        metrics = CoverageMetrics()
        
        # 1. Node Coverage
        if analysis.operations.total_in_spec > 0:
            metrics.node_coverage = (
                analysis.operations.total_in_graph / analysis.operations.total_in_spec * 100
            )
        
        # 2. Connectivity Coverage
        if analysis.operations.total_in_graph > 0:
            metrics.connectivity_coverage = (
                analysis.quality.connected_nodes / analysis.operations.total_in_graph * 100
            )
        
        # 3. Parameter Flow Coverage
        if analysis.param_flow.total_consumed_params > 0:
            # Use unique parameter matching rate
            total_unique = len(analysis.param_flow.unique_param_names)
            if total_unique > 0:
                matched = analysis.param_flow.consumed_with_producer + analysis.param_flow.produced_with_consumer
                metrics.parameter_flow_coverage = min(100, (matched / total_unique) * 100)
        else:
            # No parameters to consume - consider it 100% if there are edges
            metrics.parameter_flow_coverage = 100.0 if analysis.dependencies.total_edges > 0 else 0.0
        
        # 4. CRUD Coverage
        if analysis.crud_stats.expected_crud_links > 0:
            metrics.crud_coverage = (
                analysis.crud_stats.captured_crud_links / analysis.crud_stats.expected_crud_links * 100
            )
        else:
            # No CRUD relationships expected - consider it 100%
            metrics.crud_coverage = 100.0
        
        # 5. Semantic Correctness
        # Correct: POST→GET, POST→PUT, POST→DELETE, GET→PUT, GET→DELETE
        # Incorrect: GET→POST (generally)
        correct_orderings = (
            analysis.dependencies.post_to_get +
            analysis.dependencies.post_to_put +
            analysis.dependencies.post_to_delete +
            analysis.dependencies.get_to_put +
            analysis.dependencies.get_to_delete
        )
        
        # GET→POST is questionable but may be valid for auth flows
        questionable_orderings = analysis.dependencies.get_to_post
        
        total_directional = correct_orderings + questionable_orderings
        if total_directional > 0:
            metrics.semantic_correctness = (correct_orderings / total_directional * 100)
        else:
            metrics.semantic_correctness = 100.0  # No directional edges to evaluate
        
        # 6. Overall Score (weighted average)
        metrics.overall_score = (
            self.METRIC_WEIGHTS['node_coverage'] * metrics.node_coverage +
            self.METRIC_WEIGHTS['connectivity_coverage'] * metrics.connectivity_coverage +
            self.METRIC_WEIGHTS['parameter_flow_coverage'] * metrics.parameter_flow_coverage +
            self.METRIC_WEIGHTS['crud_coverage'] * metrics.crud_coverage +
            self.METRIC_WEIGHTS['semantic_correctness'] * metrics.semantic_correctness
        )
        
        return metrics
    
    def _identify_issues(self, analysis: APIAnalysis) -> List[str]:
        """Identify potential issues in the analysis"""
        issues = []
        
        # Node coverage issues
        if analysis.coverage.node_coverage < 100:
            missing = analysis.operations.total_in_spec - analysis.operations.total_in_graph
            issues.append(f"Missing {missing} operations ({100 - analysis.coverage.node_coverage:.1f}% uncovered)")
            
        # DAG issues
        if not analysis.quality.is_dag:
            issues.append("Graph contains cycles - not a valid DAG!")
            
        # Connectivity issues
        if analysis.coverage.connectivity_coverage < 50 and analysis.operations.total_in_graph > 1:
            issues.append(f"Low connectivity: only {analysis.coverage.connectivity_coverage:.1f}% of nodes connected")
        
        # CRUD coverage issues
        if analysis.coverage.crud_coverage < 70 and analysis.crud_stats.expected_crud_links > 0:
            missing_count = analysis.crud_stats.expected_crud_links - analysis.crud_stats.captured_crud_links
            issues.append(f"CRUD coverage low: {missing_count} expected CRUD links missing ({analysis.coverage.crud_coverage:.1f}%)")
            
        # Semantic correctness issues
        if analysis.coverage.semantic_correctness < 70:
            issues.append(f"Semantic correctness low: {analysis.coverage.semantic_correctness:.1f}% - many GET→POST edges")
            
        # No dependencies
        if analysis.dependencies.total_edges == 0 and analysis.operations.total_in_graph > 1:
            issues.append("No dependencies found - graph has no edges")
        
        # Overall score warning
        if analysis.coverage.overall_score < 60:
            issues.append(f"Overall quality score low: {analysis.coverage.overall_score:.1f}/100")
            
        return issues
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate a comprehensive coverage report"""
        lines = []
        
        # Header
        lines.append("=" * 90)
        lines.append("DEPENDENCY GRAPH COVERAGE ANALYSIS REPORT")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 90)
        
        # Coverage Metrics Definitions
        lines.extend(self._generate_definitions_section())
        
        # Executive Summary
        lines.extend(self._generate_summary_section())
        
        # Coverage Metrics Table
        lines.extend(self._generate_coverage_table())
        
        # Detailed Coverage Breakdown
        lines.extend(self._generate_detailed_coverage())
        
        # Dependency Type Analysis
        lines.extend(self._generate_dependency_analysis())
        
        # Quality Assessment
        lines.extend(self._generate_quality_assessment())
        
        # Issues Section
        lines.extend(self._generate_issues_section())
        
        # Detailed Per-API Analysis
        lines.extend(self._generate_detailed_analysis())
        
        # Footer
        lines.append("")
        lines.append("=" * 90)
        lines.append("END OF REPORT")
        lines.append("=" * 90)
        
        report = "\n".join(lines)
        
        # Save to file if specified
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"Report saved to: {output_file}")
            
        return report
    
    def _generate_definitions_section(self) -> List[str]:
        """Generate coverage metric definitions"""
        lines = []
        
        lines.append("")
        lines.append("COVERAGE METRICS DEFINITIONS")
        lines.append("-" * 90)
        lines.append("""
  The following metrics provide a comprehensive view of dependency graph quality:

  1. NODE COVERAGE
     Definition: Percentage of API operations captured as graph nodes
     Formula:    (Operations in Graph / Operations in Spec) × 100%
     Ideal:      100% - all operations should be captured
     
  2. CONNECTIVITY COVERAGE  
     Definition: Percentage of operations that are connected (have edges)
     Formula:    (Connected Nodes / Total Nodes) × 100%
     Ideal:      High % - operations should be linked in dependency chains
     Note:       GET-only APIs may legitimately have 0% connectivity
     
  3. PARAMETER FLOW COVERAGE
     Definition: How well parameter dependencies are captured
     Formula:    (Parameters with matched producers/consumers) / (Total unique params) × 100%
     Ideal:      High % - consumed params should have producing operations connected
     
  4. CRUD COVERAGE
     Definition: Percentage of expected CRUD relationships that are captured
     Formula:    (Captured CRUD Links / Expected CRUD Links) × 100%
     Expected:   POST→GET, POST→PUT, POST→DELETE for each resource
     Ideal:      100% - all CRUD relationships properly linked
     
  5. SEMANTIC CORRECTNESS
     Definition: Percentage of edges following correct semantic ordering
     Formula:    (Correct orderings) / (Total directional edges) × 100%
     Correct:    POST→GET, POST→PUT, POST→DELETE, GET→PUT, GET→DELETE
     Incorrect:  GET→POST (creating data from non-existent resource)
     Ideal:      High % - proper CRUD ordering preserved
     
  6. OVERALL QUALITY SCORE
     Definition: Weighted combination of all metrics
     Weights:    Node(20%) + Connectivity(20%) + ParamFlow(20%) + CRUD(25%) + Semantic(15%)
     Ideal:      80+ is good, 90+ is excellent
""")
        
        return lines
    
    def _generate_summary_section(self) -> List[str]:
        """Generate executive summary section"""
        lines = []
        
        total_spec_ops = sum(a.operations.total_in_spec for a in self.analyses)
        total_graph_ops = sum(a.operations.total_in_graph for a in self.analyses)
        total_edges = sum(a.dependencies.total_edges for a in self.analyses)
        all_dags = all(a.quality.is_dag for a in self.analyses)
        apis_with_issues = sum(1 for a in self.analyses if a.issues)
        
        # Average metrics
        avg_node = sum(a.coverage.node_coverage for a in self.analyses) / len(self.analyses) if self.analyses else 0
        avg_conn = sum(a.coverage.connectivity_coverage for a in self.analyses) / len(self.analyses) if self.analyses else 0
        avg_param = sum(a.coverage.parameter_flow_coverage for a in self.analyses) / len(self.analyses) if self.analyses else 0
        avg_crud = sum(a.coverage.crud_coverage for a in self.analyses) / len(self.analyses) if self.analyses else 0
        avg_semantic = sum(a.coverage.semantic_correctness for a in self.analyses) / len(self.analyses) if self.analyses else 0
        avg_overall = sum(a.coverage.overall_score for a in self.analyses) / len(self.analyses) if self.analyses else 0
        
        lines.append("")
        lines.append("EXECUTIVE SUMMARY")
        lines.append("-" * 90)
        lines.append("")
        lines.append(f"  Total APIs Analyzed:          {len(self.analyses)}")
        lines.append(f"  Total Operations in Specs:    {total_spec_ops}")
        lines.append(f"  Total Operations in Graphs:   {total_graph_ops}")
        lines.append(f"  Total Dependencies:           {total_edges}")
        lines.append(f"  All Graphs are DAGs:          {'Yes' if all_dags else 'NO - CYCLES DETECTED!'}")
        lines.append(f"  APIs with Issues:             {apis_with_issues}")
        lines.append("")
        lines.append("  AVERAGE COVERAGE METRICS:")
        lines.append(f"    Node Coverage:              {avg_node:>6.1f}%")
        lines.append(f"    Connectivity Coverage:      {avg_conn:>6.1f}%")
        lines.append(f"    Parameter Flow Coverage:    {avg_param:>6.1f}%")
        lines.append(f"    CRUD Coverage:              {avg_crud:>6.1f}%")
        lines.append(f"    Semantic Correctness:       {avg_semantic:>6.1f}%")
        lines.append(f"    ─────────────────────────────────")
        lines.append(f"    OVERALL QUALITY SCORE:      {avg_overall:>6.1f}/100")
        lines.append("")
        
        return lines
    
    def _generate_coverage_table(self) -> List[str]:
        """Generate comprehensive coverage table"""
        lines = []
        
        lines.append("")
        lines.append("COVERAGE METRICS BY API")
        lines.append("-" * 90)
        lines.append("")
        
        header = "{:<16} | {:>6} | {:>6} | {:>6} | {:>6} | {:>6} | {:>8}".format(
            "API", "Node", "Conn", "Param", "CRUD", "Sem", "OVERALL"
        )
        lines.append(header)
        lines.append("-" * 90)
        
        for analysis in sorted(self.analyses, key=lambda x: x.coverage.overall_score, reverse=True):
            c = analysis.coverage
            row = "{:<16} | {:>5.1f}% | {:>5.1f}% | {:>5.1f}% | {:>5.1f}% | {:>5.1f}% | {:>7.1f}".format(
                analysis.name[:16],
                c.node_coverage,
                c.connectivity_coverage,
                c.parameter_flow_coverage,
                c.crud_coverage,
                c.semantic_correctness,
                c.overall_score
            )
            lines.append(row)
            
        lines.append("-" * 90)
        lines.append("")
        lines.append("  Legend: Node=Node Coverage, Conn=Connectivity, Param=Parameter Flow,")
        lines.append("          CRUD=CRUD Coverage, Sem=Semantic Correctness")
        lines.append("")
        
        return lines
    
    def _generate_detailed_coverage(self) -> List[str]:
        """Generate detailed coverage breakdown"""
        lines = []
        
        lines.append("")
        lines.append("DETAILED COVERAGE BREAKDOWN")
        lines.append("-" * 90)
        
        # Aggregate CRUD stats
        total_expected_crud = sum(a.crud_stats.expected_crud_links for a in self.analyses)
        total_captured_crud = sum(a.crud_stats.captured_crud_links for a in self.analyses)
        
        # Aggregate param stats
        total_consumed = sum(a.param_flow.total_consumed_params for a in self.analyses)
        total_produced = sum(a.param_flow.total_produced_params for a in self.analyses)
        
        lines.append("")
        lines.append("  CRUD Relationship Analysis:")
        lines.append(f"    Expected CRUD links:    {total_expected_crud}")
        lines.append(f"    Captured CRUD links:    {total_captured_crud}")
        lines.append(f"    Missing CRUD links:     {total_expected_crud - total_captured_crud}")
        if total_expected_crud > 0:
            lines.append(f"    CRUD Capture Rate:      {total_captured_crud/total_expected_crud*100:.1f}%")
        lines.append("")
        
        lines.append("  Parameter Flow Analysis:")
        lines.append(f"    Total consumed params:  {total_consumed}")
        lines.append(f"    Total produced params:  {total_produced}")
        lines.append("")
        
        return lines
    
    def _generate_dependency_analysis(self) -> List[str]:
        """Generate dependency type analysis"""
        lines = []
        
        # Aggregate all dependency types
        all_types: Dict[str, int] = {}
        for analysis in self.analyses:
            for dep_type, count in analysis.dependencies.by_type.items():
                all_types[dep_type] = all_types.get(dep_type, 0) + count
                
        total = sum(all_types.values())
        
        lines.append("")
        lines.append("DEPENDENCY TYPE DISTRIBUTION")
        lines.append("-" * 90)
        lines.append("")
        
        if total > 0:
            for dep_type, count in sorted(all_types.items(), key=lambda x: -x[1]):
                pct = (count / total * 100)
                bar_len = int(pct / 2)
                bar = "█" * bar_len
                lines.append(f"  {dep_type:<20} {count:>6} ({pct:>5.1f}%) {bar}")
        else:
            lines.append("  No dependencies found.")
            
        lines.append("")
        
        # Semantic ordering breakdown
        total_post_get = sum(a.dependencies.post_to_get for a in self.analyses)
        total_post_put = sum(a.dependencies.post_to_put for a in self.analyses)
        total_post_del = sum(a.dependencies.post_to_delete for a in self.analyses)
        total_get_post = sum(a.dependencies.get_to_post for a in self.analyses)
        total_get_put = sum(a.dependencies.get_to_put for a in self.analyses)
        total_get_del = sum(a.dependencies.get_to_delete for a in self.analyses)
        
        lines.append("")
        lines.append("SEMANTIC ORDERING BREAKDOWN")
        lines.append("-" * 90)
        lines.append("")
        lines.append("  Correct Orderings (Create before Use):")
        lines.append(f"    POST → GET:     {total_post_get:>6} edges")
        lines.append(f"    POST → PUT:     {total_post_put:>6} edges")
        lines.append(f"    POST → DELETE:  {total_post_del:>6} edges")
        lines.append(f"    GET → PUT:      {total_get_put:>6} edges")
        lines.append(f"    GET → DELETE:   {total_get_del:>6} edges")
        lines.append("")
        lines.append("  Potentially Incorrect Orderings:")
        lines.append(f"    GET → POST:     {total_get_post:>6} edges")
        lines.append("")
        
        if total_get_post > 0:
            lines.append("  Note: GET→POST may be valid for authentication flows or read-before-create patterns")
            lines.append("")
            
        return lines
    
    def _generate_quality_assessment(self) -> List[str]:
        """Generate quality assessment section"""
        lines = []
        
        lines.append("")
        lines.append("QUALITY ASSESSMENT")
        lines.append("-" * 90)
        lines.append("")
        
        # Calculate thresholds
        excellent = sum(1 for a in self.analyses if a.coverage.overall_score >= 90)
        good = sum(1 for a in self.analyses if 70 <= a.coverage.overall_score < 90)
        fair = sum(1 for a in self.analyses if 50 <= a.coverage.overall_score < 70)
        poor = sum(1 for a in self.analyses if a.coverage.overall_score < 50)
        
        lines.append("  QUALITY DISTRIBUTION:")
        lines.append(f"    Excellent (90+):  {excellent} APIs")
        lines.append(f"    Good (70-89):     {good} APIs")
        lines.append(f"    Fair (50-69):     {fair} APIs")
        lines.append(f"    Poor (<50):       {poor} APIs")
        lines.append("")
        
        # DAG check
        all_dags = all(a.quality.is_dag for a in self.analyses)
        if all_dags:
            lines.append("  [PASS] DAG PROPERTY: All graphs are valid Directed Acyclic Graphs")
        else:
            lines.append("  [FAIL] DAG PROPERTY: Some graphs contain cycles!")
            for a in self.analyses:
                if not a.quality.is_dag:
                    lines.append(f"         - {a.name}: Contains cycles")
                    
        # Node coverage check
        full_node_coverage = all(a.coverage.node_coverage == 100 for a in self.analyses)
        if full_node_coverage:
            lines.append("  [PASS] NODE COVERAGE: 100% of operations captured in all APIs")
        else:
            lines.append("  [WARN] NODE COVERAGE: Some operations not captured")
            
        # CRUD coverage check
        avg_crud = sum(a.coverage.crud_coverage for a in self.analyses) / len(self.analyses) if self.analyses else 0
        if avg_crud >= 80:
            lines.append(f"  [PASS] CRUD COVERAGE: Average {avg_crud:.1f}% CRUD relationships captured")
        elif avg_crud >= 50:
            lines.append(f"  [WARN] CRUD COVERAGE: Average {avg_crud:.1f}% - some relationships missing")
        else:
            lines.append(f"  [FAIL] CRUD COVERAGE: Average {avg_crud:.1f}% - many relationships missing")
        
        lines.append("")
        
        return lines
    
    def _generate_issues_section(self) -> List[str]:
        """Generate issues section"""
        lines = []
        
        apis_with_issues = [a for a in self.analyses if a.issues]
        
        lines.append("")
        lines.append("ISSUES AND WARNINGS")
        lines.append("-" * 90)
        lines.append("")
        
        if not apis_with_issues:
            lines.append("  No significant issues detected.")
        else:
            for analysis in sorted(apis_with_issues, key=lambda x: x.coverage.overall_score):
                lines.append(f"  {analysis.name} (Score: {analysis.coverage.overall_score:.1f}):")
                for issue in analysis.issues:
                    lines.append(f"    - {issue}")
                lines.append("")
                
        return lines
    
    def _generate_detailed_analysis(self) -> List[str]:
        """Generate detailed per-API analysis"""
        lines = []
        
        lines.append("")
        lines.append("DETAILED API ANALYSIS")
        lines.append("-" * 90)
        
        for analysis in sorted(self.analyses, key=lambda x: x.name):
            lines.append("")
            lines.append(f"  {analysis.name.upper()}")
            lines.append(f"  {'─' * 50}")
            lines.append(f"    Spec: {analysis.spec_path}")
            lines.append(f"    Output: {analysis.output_dir}")
            lines.append("")
            
            # Coverage Metrics
            c = analysis.coverage
            lines.append(f"    Coverage Metrics:")
            lines.append(f"      Node Coverage:         {c.node_coverage:>6.1f}%")
            lines.append(f"      Connectivity Coverage: {c.connectivity_coverage:>6.1f}%")
            lines.append(f"      Parameter Flow:        {c.parameter_flow_coverage:>6.1f}%")
            lines.append(f"      CRUD Coverage:         {c.crud_coverage:>6.1f}%")
            lines.append(f"      Semantic Correctness:  {c.semantic_correctness:>6.1f}%")
            lines.append(f"      ─────────────────────────────")
            lines.append(f"      OVERALL SCORE:         {c.overall_score:>6.1f}/100")
            lines.append("")
            
            # Operations breakdown
            lines.append(f"    Operations:")
            lines.append(f"      In Spec:  {analysis.operations.total_in_spec}")
            lines.append(f"      In Graph: {analysis.operations.total_in_graph}")
            
            by_method = analysis.operations.by_method
            methods_str = ", ".join(f"{m}:{c}" for m, c in by_method.items() if c > 0)
            lines.append(f"      By Method: {methods_str}")
            lines.append("")
            
            # Dependencies breakdown
            lines.append(f"    Dependencies:")
            lines.append(f"      Total Edges: {analysis.dependencies.total_edges}")
            lines.append(f"      Edge Ratio:  {analysis.edge_ratio:.2f}")
            
            if analysis.dependencies.by_type:
                types_str = ", ".join(f"{t}:{c}" for t, c in 
                                     sorted(analysis.dependencies.by_type.items(), key=lambda x: -x[1]))
                lines.append(f"      By Type: {types_str}")
            lines.append("")
            
            # CRUD Stats
            if analysis.crud_stats.expected_crud_links > 0:
                lines.append(f"    CRUD Relationships:")
                lines.append(f"      Expected: {analysis.crud_stats.expected_crud_links}")
                lines.append(f"      Captured: {analysis.crud_stats.captured_crud_links}")
                lines.append(f"      Missing:  {len(analysis.crud_stats.missing_links)}")
                lines.append("")
            
            # Quality metrics
            lines.append(f"    Graph Quality:")
            lines.append(f"      Is DAG: {'Yes' if analysis.quality.is_dag else 'No'}")
            lines.append(f"      Components: {analysis.quality.num_components}")
            lines.append(f"      Connected: {analysis.quality.connected_nodes}/{analysis.operations.total_in_graph}")
            lines.append(f"      Longest Path: {analysis.quality.longest_path_length}")
            
        return lines


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Analyze coverage of dependency graphs with multiple meaningful metrics"
    )
    parser.add_argument(
        '--output', '-o',
        default='coverage_report.txt',
        help='Output file for the report (default: coverage_report.txt)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--dir', '-d',
        default='.',
        help='Base directory containing specs and outputs (default: current directory)'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("DEPENDENCY GRAPH COVERAGE ANALYZER (Enhanced)")
    print("=" * 70)
    print()
    print("Analyzing multiple coverage dimensions:")
    print("  - Node Coverage (operations captured)")
    print("  - Connectivity Coverage (operations linked)")
    print("  - Parameter Flow Coverage (data dependencies)")
    print("  - CRUD Coverage (resource relationships)")
    print("  - Semantic Correctness (ordering validity)")
    print()
    
    # Run analysis
    analyzer = CoverageAnalyzer(base_dir=args.dir, verbose=args.verbose)
    
    print("Analyzing APIs...")
    analyses = analyzer.analyze_all()
    print(f"Found {len(analyses)} APIs with generated graphs")
    print()
    
    # Generate report
    print("Generating comprehensive report...")
    report = analyzer.generate_report(output_file=args.output)
    
    # Print summary to console
    avg_score = sum(a.coverage.overall_score for a in analyses) / len(analyses) if analyses else 0
    
    print()
    print("SUMMARY")
    print("-" * 50)
    print(f"  APIs Analyzed:        {len(analyses)}")
    print(f"  Average Quality Score: {avg_score:.1f}/100")
    print(f"  Report saved to:      {args.output}")
    print()
    
    # Quick grade
    if avg_score >= 90:
        print("  Grade: EXCELLENT - Dependency graphs are high quality!")
    elif avg_score >= 70:
        print("  Grade: GOOD - Most dependencies captured correctly")
    elif avg_score >= 50:
        print("  Grade: FAIR - Some improvements needed")
    else:
        print("  Grade: NEEDS WORK - Significant gaps in coverage")
    
    print()
    print("Done!")


if __name__ == "__main__":
    main()
