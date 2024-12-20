# mermaid_parser.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import re
import json

class NodeType(Enum):
    DEFAULT = "default"
    SQUARE = "square"      # []
    ROUND = "round"       # ()
    CIRCLE = "circle"     # (())
    DIAMOND = "diamond"   # {}
    HEXAGON = "hexagon"   # {{}}
    STADIUM = "stadium"   # ([])

@dataclass
class ParsedNode:
    id: str
    label: str
    type: NodeType
    next_nodes: List[str] = field(default_factory=list)
    prev_nodes: List[str] = field(default_factory=list)

@dataclass
class ParsedEdge:
    from_id: str
    to_id: str
    label: str = ""
    style: str = "solid"  # solid, dotted, thick

@dataclass
class ParsedGraph:
    direction: str  # TD, LR, etc
    nodes: Dict[str, ParsedNode]
    edges: List[ParsedEdge]

class MermaidParser:
    """Parses Mermaid flowchart syntax into structured data"""
    
    def __init__(self):
        self.direction = "TD"
        self.nodes: Dict[str, ParsedNode] = {}
        self.edges: List[ParsedEdge] = []
        
    def parse(self, mermaid_code: str) -> ParsedGraph:
        lines = mermaid_code.strip().split('\n')
        self._parse_direction(lines)
        self._parse_nodes_and_edges(lines)
        return ParsedGraph(self.direction, self.nodes, self.edges)
    
    def _parse_direction(self, lines: List[str]) -> None:
        for line in lines:
            if line.strip().startswith('graph'):
                parts = line.strip().split()
                if len(parts) > 1:
                    self.direction = parts[1]
                break
    
    def _parse_node_type(self, node_text: str) -> tuple[str, str, NodeType]:
        node_text = node_text.strip()
        node_id = node_text
        label = node_text
        node_type = NodeType.DEFAULT

        if '[' in node_text and ']' in node_text:
            if node_text.startswith('[['):
                node_type = NodeType.SQUARE
                parts = node_text.split('[[')
                node_id = parts[0].strip()
                label = parts[1].strip('[]')
            else:
                node_type = NodeType.SQUARE
                parts = node_text.split('[')
                node_id = parts[0].strip()
                label = parts[1].strip('[]')
        elif '(' in node_text and ')' in node_text:
            if node_text.startswith('(('):
                node_type = NodeType.CIRCLE
                parts = node_text.split('((')
                node_id = parts[0].strip()
                label = parts[1].strip('())')
            else:
                node_type = NodeType.ROUND
                parts = node_text.split('(')
                node_id = parts[0].strip()
                label = parts[1].strip(')')
        elif '{' in node_text and '}' in node_text:
            if node_text.startswith('{{'):
                node_type = NodeType.HEXAGON
                parts = node_text.split('{{')
                node_id = parts[0].strip()
                label = parts[1].strip('}}')
            else:
                node_type = NodeType.DIAMOND
                parts = node_text.split('{')
                node_id = parts[0].strip()
                label = parts[1].strip('}')
                
        node_id = node_id.strip().strip('"').strip("'")
        return node_id, label, node_type
    
    def _parse_nodes_and_edges(self, lines: List[str]) -> None:
        for line in lines:
            if not line.strip() or line.strip().startswith('graph'):
                continue
                
            if '-->' in line:
                parts = line.strip().split('-->')
                
                # Parse source node
                from_id, from_label, from_type = self._parse_node_type(parts[0])
                if from_id not in self.nodes:
                    self.nodes[from_id] = ParsedNode(from_id, from_label, from_type)
                
                # Parse edge and target node
                edge_parts = parts[1].split('|')
                edge_label = ''
                if len(edge_parts) > 1:
                    edge_label = edge_parts[0].strip()
                    to_id, to_label, to_type = self._parse_node_type(edge_parts[-1])
                else:
                    to_id, to_label, to_type = self._parse_node_type(parts[1])
                
                if to_id not in self.nodes:
                    self.nodes[to_id] = ParsedNode(to_id, to_label, to_type)
                
                # Update node connections
                self.nodes[from_id].next_nodes.append(to_id)
                self.nodes[to_id].prev_nodes.append(from_id)
                
                # Create edge
                self.edges.append(ParsedEdge(from_id, to_id, edge_label))
    
    def to_json(self) -> str:
        """Convert parsed graph to JSON string"""
        def convert_enum(obj):
            if isinstance(obj, NodeType):
                return obj.value
            return obj.__dict__
            
        graph = ParsedGraph(self.direction, self.nodes, self.edges)
        return json.dumps(graph, default=convert_enum, indent=2)
    
    def save_json(self, filename: str) -> None:
        """Save parsed graph to JSON file"""
        with open(filename, 'w') as f:
            f.write(self.to_json())

# graph_generator.py

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import json
import math

@dataclass
class LayoutNode:
    id: str
    label: str
    type: str
    x: float = 0
    y: float = 0
    width: float = 80
    height: float = 80
    rank: int = 0
    order: int = 0

@dataclass
class LayoutEdge:
    from_id: str
    to_id: str
    label: str
    points: List[Tuple[float, float]] = None
    
@dataclass
class GraphLayout:
    nodes: Dict[str, LayoutNode]
    edges: List[LayoutEdge]
    width: float
    height: float

class SugiyamaLayoutGenerator:
    def __init__(self, width: float = 1920, height: float = 1080,
                 node_spacing: float = 150, rank_spacing: float = 250):
        self.width = width
        self.height = height
        self.node_spacing = node_spacing
        self.rank_spacing = rank_spacing
        
    def generate_layout(self, parsed_graph: ParsedGraph) -> GraphLayout:
        """Generate layout using Sugiyama algorithm"""
        # Convert parsed nodes to layout nodes
        nodes = {
            node_id: LayoutNode(
                id=node_id,
                label=node.label,
                type=node.type.value
            )
            for node_id, node in parsed_graph.nodes.items()
        }
        
        # Convert edges
        edges = [
            LayoutEdge(
                from_id=edge.from_id,
                to_id=edge.to_id,
                label=edge.label
            )
            for edge in parsed_graph.edges
        ]
        
        # Apply Sugiyama layout
        self._assign_ranks(nodes, edges)
        self._minimize_crossings(nodes, edges)
        self._assign_coordinates(nodes, edges)
        
        return GraphLayout(nodes, edges, self.width, self.height)
        
    def load_json(self, filename: str) -> GraphLayout:
        """Load layout from JSON file"""
        with open(filename, 'r') as f:
            data = json.load(f)
            # Convert JSON data to GraphLayout
            nodes = {
                node_id: LayoutNode(**node_data)
                for node_id, node_data in data['nodes'].items()
            }
            edges = [LayoutEdge(**edge_data) for edge_data in data['edges']]
            return GraphLayout(nodes, edges, data['width'], data['height'])
            
    def save_json(self, layout: GraphLayout, filename: str) -> None:
        """Save layout to JSON file"""
        data = {
            'nodes': {
                node_id: {
                    'id': node.id,
                    'label': node.label,
                    'type': node.type,
                    'x': node.x,
                    'y': node.y,
                    'width': node.width,
                    'height': node.height,
                    'rank': node.rank,
                    'order': node.order
                }
                for node_id, node in layout.nodes.items()
            },
            'edges': [
                {
                    'from_id': edge.from_id,
                    'to_id': edge.to_id,
                    'label': edge.label,
                    'points': edge.points
                }
                for edge in layout.edges
            ],
            'width': layout.width,
            'height': layout.height
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)