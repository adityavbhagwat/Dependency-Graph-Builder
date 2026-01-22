import os
import sys
import time
from io import StringIO
from typing import Optional, Dict, Any
from .builder import DependencyGraphBuilder
from .dynamic_manager import DynamicDependencyManager
from .analyzer import GraphAnalyzer
from .visualizer import GraphVisualizer
from .exporter import AnnotationExporter
from .core import DependencyGraph
from .parser import OpenAPIParser
from .stats import GraphStatistics


class TeeOutput:
    """
    A file-like object that writes to both the original stdout and a StringIO buffer.
    This allows capturing output while still displaying it to the console.
    """
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout
        self.buffer = StringIO()
    
    def write(self, text):
        self.original_stdout.write(text)
        self.buffer.write(text)
    
    def flush(self):
        self.original_stdout.flush()
    
    def get_captured_output(self) -> str:
        return self.buffer.getvalue()


class CompleteDependencyGraphBuilder:
    """
    Complete algorithm for building and maintaining a dependency graph
    from OpenAPI specifications with dynamic updates
    """
    
    def __init__(self, spec_path: str, enable_dynamic_updates: bool = False):
        self.spec_path = spec_path
        self.enable_dynamic_updates = enable_dynamic_updates
        
        # Core components
        self.parser: Optional[OpenAPIParser] = None
        self.graph: Optional[DependencyGraph] = None
        self.builder: Optional[DependencyGraphBuilder] = None  # Store builder for stats
        self.dynamic_manager: Optional[DynamicDependencyManager] = None
        self.analyzer: Optional[GraphAnalyzer] = None
        self.visualizer: Optional[GraphVisualizer] = None
        
        # Output capture
        self._captured_output: str = ""
        self._tee_output: Optional[TeeOutput] = None
        
    def build_complete_graph(self) -> DependencyGraph:
        """
        Main algorithm to build complete dependency graph
        
        Steps:
        1. Parse OpenAPI specification
        2. Build static dependency graph
        3. Optimize and analyze
        4. (Optional) Enable dynamic updates
        5. Export results
        """
        
        # Start capturing output
        self._start_output_capture()
        
        try:
            print("=" * 80)
            print("DEPENDENCY GRAPH BUILDER")
            print("=" * 80)
            
            start_time = time.time()
            
            # Step 1: Build initial static graph
            print("\n[PHASE 1] Building Static Dependency Graph")
            print("-" * 80)
            self.builder = DependencyGraphBuilder(self.spec_path)
            self.graph = self.builder.build()
            
            # Step 2: Analyze graph
            # print("\n[PHASE 2] Analyzing Dependency Graph")
            # print("-" * 80)
            # self.analyzer = GraphAnalyzer(self.graph)
            # analysis = self.analyzer.analyze()
            
            # self._print_analysis(analysis)
            
            # Step 3: Setup dynamic updates if enabled
            if self.enable_dynamic_updates:
                print("\n[PHASE 3] Enabling Dynamic Dependency Management")
                print("-" * 80)
                self.dynamic_manager = DynamicDependencyManager(self.graph)
                print("  ✓ Dynamic updates enabled")
                print("  ℹ️  Use record_execution() to update graph based on runtime feedback")
            
            # Step 4: Create visualizer
            self.visualizer = GraphVisualizer(self.graph)
            
            elapsed = time.time() - start_time
            print("\n" + "=" * 80)
            print(f"✓ Graph building completed in {elapsed:.2f} seconds")
            print("=" * 80)
            
            return self.graph
        finally:
            # Stop capturing but don't save yet (will save during export)
            self._stop_output_capture()
    
    def _start_output_capture(self):
        """Start capturing stdout output"""
        self._tee_output = TeeOutput(sys.stdout)
        sys.stdout = self._tee_output
    
    def _stop_output_capture(self):
        """Stop capturing and append to existing output"""
        if self._tee_output:
            # Append new output to existing captured output
            self._captured_output += self._tee_output.get_captured_output()
            sys.stdout = self._tee_output.original_stdout
            self._tee_output = None
    
    def _save_stats_log(self, output_dir: str):
        """Save all captured output to a stats log file"""
        # Extract API name from spec path for the filename
        spec_name = os.path.basename(self.spec_path)
        spec_name = os.path.splitext(spec_name)[0]  # Remove extension
        
        # Create timestamp for uniqueness
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Build the stats log content
        log_content = []
        log_content.append("=" * 80)
        log_content.append(f"DEPENDENCY GRAPH BUILD LOG - {spec_name.upper()}")
        log_content.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        log_content.append("=" * 80)
        log_content.append("")
        log_content.append(self._captured_output)
        log_content.append("")
        log_content.append("=" * 80)
        log_content.append("EDGE REDUCTION PIPELINE")
        log_content.append("=" * 80)
        
        # Add edge reduction statistics
        if self.builder and hasattr(self.builder, 'build_stats'):
            stats = self.builder.build_stats
            raw = stats.get('raw_dependencies', 0)
            after_conflict = stats.get('after_conflict_resolution', 0)
            after_cycle = stats.get('after_cycle_prevention', 0)
            final = stats.get('after_transitive_reduction', 0)
            skipped_cycles = stats.get('skipped_for_cycles', 0)
            removed_reduction = stats.get('removed_by_reduction', 0)
            
            log_content.append(f"  Raw dependencies (all analyzers):     {raw}")
            log_content.append(f"  After conflict resolution:            {after_conflict}")
            log_content.append(f"  After cycle prevention:               {after_cycle}")
            log_content.append(f"  After transitive reduction (FINAL):   {final}")
            log_content.append("")
            log_content.append("  Reduction Summary:")
            conflicts_resolved = raw - after_conflict
            log_content.append(f"    - Conflicts resolved:      {conflicts_resolved} edges merged/removed")
            log_content.append(f"    - Cycles prevented:        {skipped_cycles} edges skipped")
            log_content.append(f"    - Transitive reduction:    {removed_reduction} redundant edges removed")
            if raw > 0:
                reduction_pct = ((raw - final) / raw) * 100
                log_content.append(f"    - Total reduction:         {reduction_pct:.1f}% ({raw} → {final})")
            
            # Breakdown by analyzer
            by_analyzer = stats.get('by_analyzer', {})
            if by_analyzer:
                log_content.append("")
                log_content.append("  By Analyzer:")
                for analyzer, count in sorted(by_analyzer.items(), key=lambda x: x[1], reverse=True):
                    log_content.append(f"    - {analyzer}: {count}")
        else:
            log_content.append("  (Build statistics not available)")
        
        log_content.append("")
        log_content.append("=" * 80)
        log_content.append("DEPENDENCY TYPES SUMMARY")
        log_content.append("=" * 80)
        
        # Add dependency types summary
        summary = self.get_dependency_types_summary()
        for dep_type, count in sorted(summary.items(), key=lambda x: x[1], reverse=True):
            log_content.append(f"  {dep_type.value}: {count}")
        
        log_content.append("")
        log_content.append("=" * 80)
        log_content.append("OPERATION SEQUENCES (Sample)")
        log_content.append("=" * 80)
        
        # Add sample operation sequences
        interesting_ops = [op for op in self.graph.operations.values() if op.is_interesting()]
        for op in interesting_ops[:5]:  # Show top 5 interesting operations
            sequence = self.graph.get_operation_sequence(op)
            log_content.append(f"\nTo execute: {op.method.value} {op.path}")
            log_content.append("  Prerequisites:")
            if len(sequence) > 1:
                for i, seq_op in enumerate(sequence[:-1], 1):
                    log_content.append(f"    {i}. {seq_op.method.value} {seq_op.path}")
            else:
                log_content.append("    (No dependencies - can execute directly)")
        
        log_content.append("")
        log_content.append("=" * 80)
        log_content.append("END OF LOG")
        log_content.append("=" * 80)
        
        # Write to file
        stats_filename = f"build_stats.txt"
        stats_path = os.path.join(output_dir, stats_filename)
        
        with open(stats_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_content))
        
        print(f"Saved build statistics to {stats_path}")
    
    def _print_analysis(self, analysis: Dict[str, Any]):
        """Print analysis results"""
        print("\nBasic Statistics:")
        for key, value in analysis['basic_stats'].items():
            print(f"  {key}: {value}")
        
        print("\nComplexity Metrics:")
        for key, value in analysis['complexity_metrics'].items():
            print(f"  {key}: {value:.2f}")
        
        if analysis['critical_paths']:
            print("\nCritical Paths:")
            for i, path in enumerate(analysis['critical_paths'][:3], 1):
                print(f"  {i}. {' -> '.join(path)}")
        
        if analysis['bottlenecks']:
            print(f"\nBottleneck Operations: {len(analysis['bottlenecks'])}")
            for op_id in analysis['bottlenecks'][:5]:
                print(f"  - {op_id}")
        
        if analysis['recommendations']:
            print("\nRecommendations:")
            for rec in analysis['recommendations']:
                print(f"  {rec}")
    
    def export_all_formats(self, output_dir: str = './output'):
        """Export graph in all available formats"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Start capturing export output
        self._start_output_capture()
        
        try:
            print("\n[EXPORT] Exporting dependency graph...")
            
            # Export annotated OpenAPI spec
            parser = OpenAPIParser(self.spec_path)
            original_spec = parser.spec if hasattr(parser, 'spec') else {}
            
            exporter = AnnotationExporter(self.graph, original_spec)
            exporter.export_annotated_spec(f"{output_dir}/annotated_spec.yaml")
            
            # Export visualizations
            self.visualizer.export_json(f"{output_dir}/graph.json")
            self.visualizer.export_graphml(f"{output_dir}/graph.graphml")
            self.visualizer.export_dot(f"{output_dir}/graph.dot")
            self.visualizer.visualize_interactive(f"{output_dir}/graph.html")
            
            print(f"\n✓ All exports completed in {output_dir}/")
            
            # Generate and capture graph statistics
            print("\n[STATS] Generating graph statistics...")
            stats = GraphStatistics()
            stats.generate_report(self.graph, output_dir)
            
        finally:
            # Stop capturing and append to existing output
            self._stop_output_capture()
        
        # Save all captured output to a stats text file
        self._save_stats_log(output_dir)
    
    def get_operation_sequence(self, operation_id: str):
        """Get the complete operation sequence for a given operation"""
        if operation_id not in self.graph.operations:
            raise ValueError(f"Operation {operation_id} not found")
        
        operation = self.graph.operations[operation_id]
        return self.graph.get_operation_sequence(operation)
    
    def simulate_execution(self, operation_id: str, success: bool, 
                          response: dict, parameters: dict):
        """Simulate operation execution for dynamic learning"""
        if not self.enable_dynamic_updates:
            raise RuntimeError("Dynamic updates not enabled")
        
        if operation_id not in self.graph.operations:
            raise ValueError(f"Operation {operation_id} not found")
        
        operation = self.graph.operations[operation_id]
        self.dynamic_manager.record_execution(operation, success, response, parameters)
    
    def get_dependency_types_summary(self):
        """Get summary of dependency types in the graph"""
        from .dependency import Dependency
        summary = {}
        for dep in self.graph.dependencies:
            if dep.type not in summary:
                summary[dep.type] = 0
            summary[dep.type] += 1
        return summary