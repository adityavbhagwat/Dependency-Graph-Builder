"""
Graph statistics & benchmarking utilities.

Performs detailed analysis of an in-memory DependencyGraph (networkx.DiGraph).
This version estimates memory/size by walking the actual Python objects attached
to nodes and edges (Operation, Dependency, primitive attributes), rather than
relying on json serialization which may fail for non-serializable objects.
"""
from typing import Dict, Any, Optional, Set
import time
import json
import pickle
import statistics
import os
import sys

import networkx as nx

class GraphStatistics:
    def __init__(self, heavy_node_limit: int = 2000):
        self.heavy_node_limit = heavy_node_limit

    def generate_report(self, graph, output_dir: Optional[str] = None) -> Dict[str, Any]:
        report: Dict[str, Any] = {}
        nxg = getattr(graph, "graph", graph)  # accept DependencyGraph or raw nx graph

        start_total = time.time()
        num_nodes = nxg.number_of_nodes()
        num_edges = nxg.number_of_edges()
        is_dag = nx.is_directed_acyclic_graph(nxg) if num_nodes > 0 else False

        report['basic'] = {
            'num_nodes': num_nodes,
            'num_edges': num_edges,
            'is_dag': bool(is_dag),
            'directed': nxg.is_directed()
        }

        # connected components
        try:
            if nxg.is_directed():
                comps = list(nx.weakly_connected_components(nxg))
            else:
                comps = list(nx.connected_components(nxg))
            report['components'] = {
                'count': len(comps),
                'largest_size': max((len(c) for c in comps), default=0)
            }
        except Exception:
            report['components'] = {'count': None, 'largest_size': None}

        # degree stats
        try:
            in_degs = [d for _, d in nxg.in_degree()] if nxg.is_directed() else [d for _, d in nxg.degree()]
            out_degs = [d for _, d in nxg.out_degree()] if nxg.is_directed() else in_degs

            def stats_list(vals):
                if not vals:
                    return {'min':0,'max':0,'mean':0.0,'median':0.0,'stdev':0.0}
                return {
                    'min': int(min(vals)),
                    'max': int(max(vals)),
                    'mean': float(statistics.mean(vals)),
                    'median': float(statistics.median(vals)),
                    'stdev': float(statistics.pstdev(vals))
                }
            report['degree'] = {'in': stats_list(in_degs), 'out': stats_list(out_degs)}
        except Exception:
            report['degree'] = {'in': None, 'out': None}

        # longest path for DAGs
        if is_dag:
            t0 = time.time()
            try:
                lp_len = nx.dag_longest_path_length(nxg)
                lp = nx.dag_longest_path(nxg)
            except Exception:
                lp_len = None
                lp = None
            report['longest_path'] = {'length': lp_len, 'example': lp}
            report.setdefault('_timings', {})['longest_path_sec'] = time.time() - t0
        else:
            report['longest_path'] = {'length': None, 'example': None}

        # centrality (skip if too large)
        if num_nodes <= self.heavy_node_limit:
            t0 = time.time()
            try:
                bet = nx.betweenness_centrality(nxg)
                top_bet = sorted(bet.items(), key=lambda kv: kv[1], reverse=True)[:10]
            except Exception:
                top_bet = []
            report.setdefault('_timings', {})['betweenness_sec'] = time.time() - t0

            t0 = time.time()
            try:
                degc = nx.degree_centrality(nxg)
                top_deg = sorted(degc.items(), key=lambda kv: kv[1], reverse=True)[:10]
            except Exception:
                top_deg = []
            report.setdefault('_timings', {})['degree_centrality_sec'] = time.time() - t0

            report['centrality'] = {'betweenness_top': top_bet, 'degree_top': top_deg}
        else:
            report['centrality'] = {'betweenness_top': f"skipped (>{self.heavy_node_limit})",
                                    'degree_top': f"skipped (>{self.heavy_node_limit})"}

        # Estimate in-memory size by walking objects attached to nodes/edges.
        # Use a recursive estimator that sums sizes of primitive values and container contents.
        seen_ids: Set[int] = set()

        def estimate_size(obj) -> int:
            """Recursively estimate memory footprint (bytes) of Python object graph reachable from obj."""
            obj_id = id(obj)
            if obj_id in seen_ids:
                return 0
            seen_ids.add(obj_id)

            # Primitives
            if obj is None:
                return 0
            if isinstance(obj, (bool, int, float)):
                return sys.getsizeof(obj)
            if isinstance(obj, str):
                return len(obj.encode('utf-8')) + sys.getsizeof(obj)
            # Bytes
            if isinstance(obj, (bytes, bytearray)):
                return len(obj) + sys.getsizeof(obj)
            # Containers
            if isinstance(obj, (list, tuple, set, frozenset)):
                size = sys.getsizeof(obj)
                for item in obj:
                    try:
                        size += estimate_size(item)
                    except Exception:
                        try:
                            size += sys.getsizeof(item)
                        except Exception:
                            size += 0
                return size
            if isinstance(obj, dict):
                size = sys.getsizeof(obj)
                for k, v in obj.items():
                    size += estimate_size(k)
                    size += estimate_size(v)
                return size
            # Objects: try to inspect __dict__ or dataclass fields
            try:
                # If object exposes __dict__, walk that
                if hasattr(obj, '__dict__'):
                    size = sys.getsizeof(obj)
                    for k, v in vars(obj).items():
                        size += estimate_size(k)
                        size += estimate_size(v)
                    return size
            except Exception:
                pass
            # Fallback to string representation
            try:
                s = str(obj)
                return len(s.encode('utf-8')) + sys.getsizeof(obj)
            except Exception:
                return sys.getsizeof(obj)

        # Compute per-node attribute sizes
        node_attr_sizes = []
        node_id_sizes = []
        node_field_counts = []
        for node_id, data in nxg.nodes(data=True):
            seen_ids.clear()  # avoid cross-node deduplication for clearer per-node breakdown
            size = 0
            # node id (string)
            try:
                size_node_id = estimate_size(node_id)
                size += size_node_id
            except Exception:
                size_node_id = 0
            # attributes dict
            try:
                size_attrs = estimate_size(data)
                # count fields if it's a mapping
                fld_count = len(data) if isinstance(data, dict) else 0
            except Exception:
                size_attrs = 0
                fld_count = 0
            size += size_attrs
            node_attr_sizes.append(size)
            node_id_sizes.append(size_node_id)
            node_field_counts.append(fld_count)

        total_nodes_bytes = sum(node_attr_sizes)
        avg_node_bytes = int(statistics.mean(node_attr_sizes)) if node_attr_sizes else 0
        avg_node_id_bytes = int(statistics.mean(node_id_sizes)) if node_id_sizes else 0
        avg_fields_per_node = float(statistics.mean(node_field_counts)) if node_field_counts else 0.0

        # Compute per-edge attribute sizes
        edge_attr_sizes = []
        edge_field_counts = []
        for u, v, data in nxg.edges(data=True):
            seen_ids.clear()
            size = 0
            try:
                size += estimate_size(u)
            except Exception:
                pass
            try:
                size += estimate_size(v)
            except Exception:
                pass
            try:
                size += estimate_size(data)
                efc = len(data) if isinstance(data, dict) else 0
            except Exception:
                efc = 0
            size += 0
            edge_attr_sizes.append(size)
            edge_field_counts.append(efc)

        total_edges_bytes = sum(edge_attr_sizes)
        avg_edge_bytes = int(statistics.mean(edge_attr_sizes)) if edge_attr_sizes else 0
        avg_fields_per_edge = float(statistics.mean(edge_field_counts)) if edge_field_counts else 0.0

        # Print per-node & per-edge breakdown with reasoning before totals
        print("\n--- Per-node and per-edge memory breakdown (estimated) ---")
        print(f"Average per-node bytes (includes node id + attributes): {avg_node_bytes} bytes")
        print(f"  - Avg node-id bytes: {avg_node_id_bytes} bytes (string length + object overhead)")
        print(f"  - Avg number of attribute fields per node: {avg_fields_per_node:.2f}")
        print("  Reasoning:")
        print("    * node-id: stored as Python object (usually str) => bytes = utf-8 length + object overhead.")
        print("    * attributes: dictionary object overhead + sizes of keys and values recursively.")
        print("    * Operation-like attribute objects contribute: object header + per-field sizes (operation_id, path, method, params, annotations).")
        print("    * Lists/maps stored in attributes are walked recursively and their element sizes included.")
        print()
        print(f"Average per-edge bytes (includes edge endpoints + attributes): {avg_edge_bytes} bytes")
        print(f"  - Avg number of attribute fields per edge: {avg_fields_per_edge:.2f}")
        print("  Reasoning:")
        print("    * edge stores references to source/target (ids) plus an attributes dict.")
        print("    * Dependency-like objects add their __dict__ fields (type, confidence, parameter mappings, flags).")
        print("    * Each container or string contributes its own memory as estimated above.")
        print("----------------------------------------------------------\n")

        # Adjacency/graph overhead heuristics
        overhead_per_node = 96   # estimate bytes for adjacency lists + metadata
        overhead_per_edge = 40   # edge record overhead
        total_overhead = num_nodes * overhead_per_node + num_edges * overhead_per_edge

        total_estimated_bytes = total_nodes_bytes + total_edges_bytes + total_overhead

        report['detailed_size_in_memory'] = {
            'nodes': {
                'count': num_nodes,
                'total_bytes': total_nodes_bytes,
                'avg_bytes_per_node': avg_node_bytes,
                'avg_node_id_bytes': avg_node_id_bytes,
                'avg_fields_per_node': avg_fields_per_node
            },
            'edges': {
                'count': num_edges,
                'total_bytes': total_edges_bytes,
                'avg_bytes_per_edge': avg_edge_bytes,
                'avg_fields_per_edge': avg_fields_per_edge
            },
            'overhead': {
                'per_node_bytes': overhead_per_node,
                'per_edge_bytes': overhead_per_edge,
                'total_overhead_bytes': total_overhead
            },
            'total_estimated_bytes': total_estimated_bytes,
            'human_readable': self._human_readable(total_estimated_bytes)
        }

        # Also attempt serialization sizes (pickle) as a secondary indicator
        t0 = time.time()
        try:
            pickled = pickle.dumps(nxg)
            pickle_size = len(pickled)
        except Exception:
            pickle_size = None
        report.setdefault('_timings', {})['pickle_serialize_sec'] = time.time() - t0
        report['serialization'] = {'pickle_bytes': pickle_size}

        # density and avg shortest path heuristic
        try:
            report['extras'] = {
                'density': nx.density(nxg)
            }
        except Exception:
            report['extras'] = {'density': None}

        report.setdefault('_timings', {})['total_sec'] = time.time() - start_total

        # Print concise summary
        self._print_summary(report)
        # Optionally write full JSON report
        if output_dir:
            try:
                os.makedirs(output_dir, exist_ok=True)
                out_path = os.path.join(output_dir, "graph_stats.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2, default=self._json_default)
            except Exception:
                pass

        return report

    def _print_summary(self, report: Dict[str, Any]):
        b = report.get('basic', {})
        ds = report.get('detailed_size_in_memory', {})
        ser = report.get('serialization', {})
        print("\n=== Dependency Graph Benchmark Report ===")
        print(f"Nodes: {b.get('num_nodes')}   Edges: {b.get('num_edges')}   DAG: {b.get('is_dag')}")
        comps = report.get('components', {})
        print(f"Components: count={comps.get('count')} largest={comps.get('largest_size')}")
        deg = report.get('degree', {})
        print(f"Degree in: {deg.get('in')} out: {deg.get('out')}")
        print("Detailed in-memory size estimate:")
        if ds:
            n = ds['nodes']
            e = ds['edges']
            ov = ds['overhead']
            print(f"  Nodes total bytes: {n.get('total_bytes')}  avg/node: {n.get('avg_bytes_per_node')}")
            print(f"  (avg node-id bytes: {n.get('avg_node_id_bytes')}  avg fields/node: {n.get('avg_fields_per_node')})")
            print(f"  Edges total bytes: {e.get('total_bytes')}  avg/edge: {e.get('avg_bytes_per_edge')}")
            print(f"  (avg fields/edge: {e.get('avg_fields_per_edge')})")
            print(f"  Overhead total bytes: {ov.get('total_overhead_bytes')}")
            print(f"  Estimated total in-memory bytes: {ds.get('total_estimated_bytes')} ({ds.get('human_readable')})")
        else:
            print("  (no detailed size data)")
        if ser.get('pickle_bytes') is not None:
            print(f"Pickle serialized size: {ser.get('pickle_bytes')} bytes")
        timings = report.get('_timings', {})
        print("Timings (s):", {k: v for k, v in timings.items() if v is not None})
        print("=== End Report ===\n")

    def _human_readable(self, num: Optional[int]) -> Optional[str]:
        if num is None:
            return None
        for unit in ['B','KB','MB','GB','TB']:
            if num < 1024:
                return f"{num:.2f}{unit}"
            num /= 1024
        return f"{num:.2f}PB"

    def _json_default(self, obj):
        try:
            return str(obj)
        except Exception:
            return None
