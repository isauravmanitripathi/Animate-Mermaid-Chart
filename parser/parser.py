# parser/parser.py

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
        self.direction = "TD"  # Default direction
        self.nodes: Dict[str, ParsedNode] = {}
        self.edges: List[ParsedEdge] = []
        
    def parse(self, mermaid_code: str) -> ParsedGraph:
        """Parse Mermaid code into structured graph data"""
        lines = mermaid_code.strip().split('\n')
        self._parse_direction(lines)
        self._parse_nodes_and_edges(lines)
        return ParsedGraph(self.direction, self.nodes, self.edges)
    
    def _parse_direction(self, lines: List[str]) -> None:
        """Parse graph direction from Mermaid syntax"""
        for line in lines:
            if line.strip().startswith('graph'):
                parts = line.strip().split()
                if len(parts) > 1:
                    direction = parts[1].upper()
                    # Validate and normalize direction
                    if direction in ["TB", "TD"]:  # Top to Bottom
                        self.direction = "TD"
                    elif direction == "BT":  # Bottom to Top
                        self.direction = "BT"
                    elif direction == "LR":  # Left to Right
                        self.direction = "LR"
                    elif direction == "RL":  # Right to Left
                        self.direction = "RL"
                    else:
                        self.direction = "TD"  # Default to Top-Down
                break
    
    def _parse_node_type(self, node_text: str) -> tuple[str, str, NodeType]:
        """Parse node text to determine its type and extract id/label"""
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
        label = label.strip().strip('"').strip("'")
        return node_id, label, node_type
    
    def _parse_nodes_and_edges(self, lines: List[str]) -> None:
        """Parse nodes and edges from Mermaid code lines"""
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
                    edge_label = edge_parts[0].strip().strip('"').strip("'")
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
    
    def save_json(self, filename: str) -> None:
        """Save parsed graph to JSON file"""
        def convert_enum(obj):
            if isinstance(obj, NodeType):
                return obj.value
            return obj.__dict__
            
        graph = ParsedGraph(self.direction, self.nodes, self.edges)
        with open(filename, 'w') as f:
            json.dump(graph, default=convert_enum, indent=2, fp=f)