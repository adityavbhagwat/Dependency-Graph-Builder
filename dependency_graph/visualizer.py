import json
import os
import requests  # Add this import
import pydot
from typing import Dict, Any
from .core import DependencyGraph
from .dependency import Dependency
from .enums import DependencyType, HTTPMethod
from .operation import Operation

class GraphVisualizer:
    """Visualize the dependency graph"""
    
    def __init__(self, graph: DependencyGraph):
        self.graph = graph
    
    def export_dot(self, output_path: str):
        """Export graph to DOT format (Graphviz)"""
        dot_graph = pydot.Dot(graph_type='digraph', rankdir='TB')
        
        # Add nodes
        for op_id, op in self.graph.operations.items():
            label = f"{op.method.value} {op.path}"
            color = self._get_node_color(op)
            
            node = pydot.Node(
                op_id,
                label=label,
                shape='box',
                style='filled',
                fillcolor=color
            )
            dot_graph.add_node(node)
        
        # Add edges
        for dep in self.graph.dependencies:
            edge = pydot.Edge(
                dep.source.operation_id,
                dep.target.operation_id,
                label=dep.type.value,
                color=self._get_edge_color(dep.type)
            )
            dot_graph.add_edge(edge)
        
        dot_graph.write_raw(output_path)
        print(f"Exported DOT graph to {output_path}")
    
    def export_graphml(self, output_path: str):
        """Export to GraphML format"""
        # GraphML format does not support complex Python objects as attributes.
        # We create a sanitized copy of the graph with these objects removed for export.
        graph_to_export = self.graph.graph.copy()
        
        # Remove the 'operation' object from nodes, as it's not serializable
        for _, data in graph_to_export.nodes(data=True):
            if 'operation' in data:
                del data['operation']
        
        # Remove the 'dependency' object from edges, as it's not serializable
        for _, _, data in graph_to_export.edges(data=True):
            if 'dependency' in data:
                del data['dependency']

        try:
            import networkx as nx
            nx.write_graphml(graph_to_export, output_path)
            print(f"Exported GraphML to {output_path}")
        except ImportError:
            print(f"  [WARNING] Skipping GraphML export: 'lxml' library not found. Run 'pip install lxml' to enable.")
        except TypeError as e:
            print(f"  [ERROR] Could not export to GraphML due to unsupported data types: {e}")
    
    def export_json(self, output_path: str):
        """Export to JSON format"""
        graph_data = {
            'nodes': [],
            'edges': [],
            'metadata': {
                'num_operations': len(self.graph.operations),
                'num_dependencies': len(self.graph.dependencies)
            }
        }
        
        # Add nodes
        for op_id, op in self.graph.operations.items():
            node_data = {
                'id': op_id,
                'path': op.path,
                'method': op.method.value,
                'resource_type': op.resource_type,
                'consumes': list(op.consumes),
                'produces': list(op.produces),
                'is_interesting': op.is_interesting(),
                'annotations': op.annotations
            }
            graph_data['nodes'].append(node_data)
        
        # Add edges
        for dep in self.graph.dependencies:
            edge_data = {
                'source': dep.source.operation_id,
                'target': dep.target.operation_id,
                'type': dep.type.value,
                'confidence': dep.confidence,
                'parameter_mapping': dep.parameter_mapping,
                'reason': dep.reason,
                'verified': dep.verified
            }
            graph_data['edges'].append(edge_data)
        
        with open(output_path, 'w') as f:
            json.dump(graph_data, f, indent=2)
        
        print(f"Exported JSON graph to {output_path}")
    
    def visualize_interactive(self, output_path: str = 'graph.html'):
        """Create interactive HTML visualization using vis.js"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>API Dependency Graph</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        #mynetwork {
            width: 100%;
            height: 800px;
            border: 1px solid lightgray;
        }
        .legend {
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <h1>API Dependency Graph</h1>
    <div class="legend">
        <h3>Legend</h3>
        <div><span style="color: #4CAF50;">■</span> GET Operations</div>
        <div><span style="color: #2196F3;">■</span> POST Operations</div>
        <div><span style="color: #FF9800;">■</span> PUT/PATCH Operations</div>
        <div><span style="color: #F44336;">■</span> DELETE Operations</div>
    </div>
    <div id="mynetwork"></div>
    <script type="text/javascript">
        // Graph data
        var nodes = new vis.DataSet(NODES_DATA);
        var edges = new vis.DataSet(EDGES_DATA);
        
        var container = document.getElementById('mynetwork');
        var data = {
            nodes: nodes,
            edges: edges
        };
        
        var options = {
            nodes: {
                shape: 'box',
                margin: 10,
                widthConstraint: {
                    maximum: 200
                }
            },
            edges: {
                arrows: 'to',
                smooth: {
                    type: 'cubicBezier'
                }
            },
            physics: {
                enabled: true,
                barnesHut: {
                    gravitationalConstant: -2000,
                    springConstant: 0.001,
                    springLength: 200
                }
            },
            layout: {
                hierarchical: {
                    enabled: true,
                    direction: 'UD',
                    sortMethod: 'directed'
                }
            }
        };
        
        var network = new vis.Network(container, data, options);
        
        network.on("click", function(params) {
            if (params.nodes.length > 0) {
                var nodeId = params.nodes[0];
                var node = nodes.get(nodeId);
                alert('Operation: ' + node.label + '\\n' +
                      'ID: ' + node.id + '\\n' +
                      'Consumes: ' + (node.consumes || []).join(', ') + '\\n' +
                      'Produces: ' + (node.produces || []).join(', '));
            }
        });
    </script>
</body>
</html>
        """
        
        # Prepare nodes data
        nodes_data = []
        for op_id, op in self.graph.operations.items():
            nodes_data.append({
                'id': op_id,
                'label': f"{op.method.value}\\n{op.path}",
                'color': self._get_node_color(op),
                'consumes': list(op.consumes),
                'produces': list(op.produces)
            })
        
        # Prepare edges data
        edges_data = []
        for dep in self.graph.dependencies:
            edges_data.append({
                'from': dep.source.operation_id,
                'to': dep.target.operation_id,
                'label': dep.type.value,
                'color': self._get_edge_color(dep.type),
                'title': dep.reason or ''
            })
        
        # Replace placeholders
        html_content = html_template.replace(
            'NODES_DATA', 
            json.dumps(nodes_data)
        ).replace(
            'EDGES_DATA',
            json.dumps(edges_data)
        )
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        
        print(f"Created interactive visualization at {output_path}")
    
    def export_html(self, output_path: str):
        """Exports the graph to a self-contained HTML file."""
        nodes = []
        edges = []

        # --- NODE AND EDGE EXTRACTION LOGIC ---
        for op_id, op_data in self.graph.operation_registry.items():
            method = op_data.method.value
            color = {
                'GET': '#4CAF50',
                'POST': '#2196F3',
                'PUT': '#FF9800',
                'PATCH': '#FF9800',
                'DELETE': '#F44336'
            }.get(method, '#9E9E9E')
            
            nodes.append({
                "id": op_id,
                "label": f"{method}\n{op_data.path}",
                "color": color,
                "consumes": list(op_data.consumes),
                "produces": list(op_data.produces)
            })

        for u, v, data in self.graph.graph.edges(data=True):
            edges.append({
                "from": u,
                "to": v,
                "label": data.get('type', ''),
                "color": "#2196F3",
                "title": data.get('reason', '')
            })

        # --- THE FIX IS HERE ---
        # Download the vis.js library content to embed it directly.
        try:
            vis_js_url = "https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"
            vis_js_content = requests.get(vis_js_url).text
        except requests.RequestException as e:
            print(f"Warning: Could not download vis.js library. HTML will not be interactive. Error: {e}")
            vis_js_content = "alert('Could not load visualization library.');"

        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>API Dependency Graph</title>
    <style>
        #mynetwork {{
            width: 100%;
            height: 800px;
            border: 1px solid lightgray;
        }}
        .legend {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 5px;
        }}
    </style>
    <script type="text/javascript">
        // Embedded vis.js library
        {vis_js_content}
    </script>
</head>
<body>
    <h1>API Dependency Graph</h1>
    <div class="legend">
        <h3>Legend</h3>
        <div><span style="color: #4CAF50;">■</span> GET Operations</div>
        <div><span style="color: #2196F3;">■</span> POST Operations</div>
        <div><span style="color: #FF9800;">■</span> PUT/PATCH Operations</div>
        <div><span style="color: #F44336;">■</span> DELETE Operations</div>
    </div>
    <div id="mynetwork"></div>
    <script type="text/javascript">
        var nodes = new vis.DataSet({json.dumps(nodes)});
        var edges = new vis.DataSet({json.dumps(edges)});
        
        var container = document.getElementById('mynetwork');
        var data = {{
            nodes: nodes,
            edges: edges
        }};
        
        var options = {{
            nodes: {{
                shape: 'box',
                margin: 10,
                widthConstraint: {{
                    maximum: 200
                }}
            }},
            edges: {{
                arrows: 'to',
                smooth: {{
                    type: 'cubicBezier'
                }}
            }},
            physics: {{
                enabled: true,
                barnesHut: {{
                    gravitationalConstant: -2000,
                    springConstant: 0.001,
                    springLength: 200
                }}
            }},
            layout: {{
                hierarchical: {{
                    enabled: true,
                    direction: 'UD',
                    sortMethod: 'directed'
                }}
            }}
        }};
        
        var network = new vis.Network(container, data, options);
        
        network.on("click", function(params) {{
            if (params.nodes.length > 0) {{
                var nodeId = params.nodes[0];
                var node = nodes.get(nodeId);
                alert('Operation: ' + node.label + '\\n' +
                      'ID: ' + node.id + '\\n' +
                      'Consumes: ' + (node.consumes || []).join(', ') + '\\n' +
                      'Produces: ' + (node.produces || []).join(', '));
            }}
        }});
    </script>
</body>
</html>
"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_template)

        print(f"Created self-contained HTML visualization at {output_path}")
    
    def _get_node_color(self, operation: Operation) -> str:
        """Get color for operation node based on HTTP method"""
        color_map = {
            HTTPMethod.GET: '#4CAF50',      # Green
            HTTPMethod.POST: '#2196F3',     # Blue
            HTTPMethod.PUT: '#FF9800',      # Orange
            HTTPMethod.PATCH: '#FF9800',    # Orange
            HTTPMethod.DELETE: '#F44336',   # Red
        }
        return color_map.get(operation.method, '#9E9E9E')
    
    def _get_edge_color(self, dep_type: DependencyType) -> str:
        """Get color for dependency edge based on type"""
        color_map = {
            DependencyType.PARAMETER_DATA: '#2196F3',
            DependencyType.CRUD: '#4CAF50',
            DependencyType.AUTHENTICATION: '#FF5722',
            DependencyType.AUTHORIZATION: '#FF5722',
            DependencyType.NESTED_RESOURCE: '#9C27B0',
            DependencyType.WORKFLOW: '#00BCD4',
            DependencyType.CONSTRAINT: '#FFC107',
            DependencyType.TRANSITIVE: '#9E9E9E',
            DependencyType.DYNAMIC: '#E91E63'
        }
        return color_map.get(dep_type, '#000000')