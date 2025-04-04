# layout/layout.py

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Literal
from collections import defaultdict
import logging
import json

logger = logging.getLogger(__name__)

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
    dummy: bool = False

@dataclass
class LayoutEdge:
    from_id: str
    to_id: str
    label: str = ""
    points: List[Tuple[float, float]] = field(default_factory=list)
    dummy_nodes: List[str] = field(default_factory=list)

@dataclass
class GraphLayout:
    nodes: Dict[str, LayoutNode]
    edges: List[LayoutEdge]
    width: float
    height: float
    direction: str = "TD"  # Added direction field
    ranks: Dict[int, List[str]] = field(default_factory=lambda: defaultdict(list))

class SugiyamaLayoutGenerator:
    """Implements Sugiyama's algorithm for layered graph drawing with direction support"""
    
    def __init__(self, width: float = 1920, height: float = 1080,
                 node_spacing: float = 150, rank_spacing: float = 250):
        self.width = width
        self.height = height
        self.node_spacing = node_spacing
        self.rank_spacing = rank_spacing
        self.dummy_counter = 0
        self.direction = "TD"  # Default direction

    def generate_layout(self, parsed_graph) -> GraphLayout:
        """Main method to generate layout"""
        # Get direction from parsed graph
        self.direction = parsed_graph.direction
        
        # Initialize layout
        nodes = {
            node_id: LayoutNode(
                id=node_id,
                label=node.label,
                type=node.type.value
            )
            for node_id, node in parsed_graph.nodes.items()
        }
        
        edges = [
            LayoutEdge(
                from_id=edge.from_id,
                to_id=edge.to_id,
                label=edge.label
            )
            for edge in parsed_graph.edges
        ]
        
        # Create graph layout
        layout = GraphLayout(nodes, edges, self.width, self.height, self.direction)
        
        # Apply Sugiyama algorithm steps
        self._assign_ranks(layout)
        self._normalize_edges(layout)
        self._optimize_crossings(layout)
        self._assign_coordinates(layout)
        
        return layout

    def _assign_ranks(self, layout: GraphLayout) -> None:
        """Step 1: Assign ranks to nodes using longest path layering"""
        # Find nodes with no incoming edges
        incoming_edges = {e.to_id for e in layout.edges}
        roots = [nid for nid in layout.nodes.keys() if nid not in incoming_edges]
        
        if not roots:
            roots = [next(iter(layout.nodes.keys()))]
            logger.warning(f"No root nodes found, using {roots[0]} as root")
        
        # Initialize ranks
        ranks = defaultdict(list)
        assigned = set()
        
        def assign_rank(node_id: str, rank: int) -> None:
            node = layout.nodes[node_id]
            if node_id in assigned:
                node.rank = max(node.rank, rank)
            else:
                node.rank = rank
                assigned.add(node_id)
            
            ranks[rank].append(node_id)
            
            # Process outgoing edges
            outgoing = [e for e in layout.edges if e.from_id == node_id]
            for edge in outgoing:
                if edge.to_id not in assigned:
                    assign_rank(edge.to_id, rank + 1)
        
        # Assign ranks starting from roots
        for root in roots:
            assign_rank(root, 0)
        
        layout.ranks = ranks

    def _normalize_edges(self, layout: GraphLayout) -> None:
        """Step 2: Add dummy nodes for edges spanning multiple ranks"""
        new_edges = []
        
        for edge in layout.edges:
            source = layout.nodes[edge.from_id]
            target = layout.nodes[edge.to_id]
            
            if target.rank - source.rank > 1:
                # Create dummy nodes for long edges
                current_id = edge.from_id
                dummy_nodes = []
                
                for rank in range(source.rank + 1, target.rank):
                    dummy_id = f"dummy_{self.dummy_counter}"
                    self.dummy_counter += 1
                    
                    # Create dummy node
                    layout.nodes[dummy_id] = LayoutNode(
                        id=dummy_id,
                        label="",
                        type="default",
                        rank=rank,
                        dummy=True,
                        width=10,
                        height=10
                    )
                    layout.ranks[rank].append(dummy_id)
                    dummy_nodes.append(dummy_id)
                    
                    # Create edge to dummy node
                    new_edges.append(LayoutEdge(
                        from_id=current_id,
                        to_id=dummy_id
                    ))
                    current_id = dummy_id
                
                # Connect last dummy to target
                new_edges.append(LayoutEdge(
                    from_id=current_id,
                    to_id=edge.to_id
                ))
                
                # Store dummy nodes in original edge
                edge.dummy_nodes = dummy_nodes
            else:
                new_edges.append(edge)
        
        layout.edges = new_edges

    def _optimize_crossings(self, layout: GraphLayout) -> None:
        """Step 3: Minimize edge crossings between adjacent ranks"""
        MAX_ITERATIONS = 24
        
        def count_crossings(rank1: List[str], rank2: List[str]) -> int:
            """Count number of edge crossings between two ranks"""
            crossings = 0
            edges1 = []
            
            for idx1, n1 in enumerate(rank1):
                for e in layout.edges:
                    if e.from_id == n1 and e.to_id in rank2:
                        pos2 = rank2.index(e.to_id)
                        edges1.append((idx1, pos2))
            
            for i, (a1, a2) in enumerate(edges1):
                for b1, b2 in edges1[i+1:]:
                    if (a1 - b1) * (a2 - b2) < 0:
                        crossings += 1
            
            return crossings

        def optimize_rank_order(rank_idx: int) -> None:
            """Optimize ordering of nodes in one rank"""
            if rank_idx not in layout.ranks:
                return
                
            current_rank = layout.ranks[rank_idx]
            best_order = current_rank.copy()
            best_crossings = float('inf')
            
            # Try different permutations
            for i in range(len(current_rank)):
                for j in range(i + 1, len(current_rank)):
                    current_rank[i], current_rank[j] = current_rank[j], current_rank[i]
                    
                    crossings = 0
                    if rank_idx > 0:
                        crossings += count_crossings(
                            layout.ranks[rank_idx - 1], current_rank)
                    if rank_idx + 1 in layout.ranks:
                        crossings += count_crossings(
                            current_rank, layout.ranks[rank_idx + 1])
                    
                    if crossings < best_crossings:
                        best_crossings = crossings
                        best_order = current_rank.copy()
                    else:
                        current_rank[i], current_rank[j] = current_rank[j], current_rank[i]
            
            layout.ranks[rank_idx] = best_order
        
        # Iterate multiple times to improve layout
        for _ in range(MAX_ITERATIONS):
            for rank_idx in layout.ranks.keys():
                optimize_rank_order(rank_idx)

    def _assign_coordinates(self, layout: GraphLayout) -> None:
        """Step 4: Assign final x,y coordinates based on graph direction"""
        max_rank = max(layout.ranks.keys())
        
        # Calculate usable area (with margins)
        MARGIN = 100
        usable_width = self.width - (2 * MARGIN)
        usable_height = self.height - (2 * MARGIN)
        
        # Calculate spacing based on direction
        if layout.direction in ["TD", "BT"]:  # Top-down or Bottom-up
            rank_spacing = usable_height / (max_rank + 1)
            max_nodes_in_rank = max(len(nodes) for nodes in layout.ranks.values())
            node_spacing = min(self.node_spacing, usable_width / (max_nodes_in_rank + 1))
            
            for rank, nodes in layout.ranks.items():
                # For TD: y increases with rank
                y = MARGIN + (rank + 1) * rank_spacing if layout.direction == "TD" else \
                    self.height - (MARGIN + (rank + 1) * rank_spacing)
                
                # Center nodes horizontally
                total_width = (len(nodes) - 1) * node_spacing
                start_x = MARGIN + (usable_width - total_width) / 2
                
                for i, node_id in enumerate(nodes):
                    node = layout.nodes[node_id]
                    node.x = start_x + i * node_spacing
                    node.y = y
                    node.order = i
                    
        else:  # LR or RL (Left-to-right or Right-to-left)
            rank_spacing = usable_width / (max_rank + 1)
            max_nodes_in_rank = max(len(nodes) for nodes in layout.ranks.values())
            node_spacing = min(self.node_spacing, usable_height / (max_nodes_in_rank + 1))
            
            for rank, nodes in layout.ranks.items():
                # For LR: x increases with rank
                x = MARGIN + (rank + 1) * rank_spacing if layout.direction == "LR" else \
                    self.width - (MARGIN + (rank + 1) * rank_spacing)
                
                # Center nodes vertically
                total_height = (len(nodes) - 1) * node_spacing
                start_y = MARGIN + (usable_height - total_height) / 2
                
                for i, node_id in enumerate(nodes):
                    node = layout.nodes[node_id]
                    node.x = x
                    node.y = start_y + i * node_spacing
                    node.order = i
        
        # Adjust node positions to ensure they're within bounds
        self._adjust_node_positions(layout)
        # Route edges based on new coordinates
        self._route_edges(layout)

    def _adjust_node_positions(self, layout: GraphLayout) -> None:
        """Adjust node positions to ensure they stay within canvas bounds"""
        MARGIN = 100
        
        for node in layout.nodes.values():
            # Ensure x coordinate is within bounds
            node.x = max(MARGIN + node.width/2, 
                        min(self.width - MARGIN - node.width/2, node.x))
            # Ensure y coordinate is within bounds
            node.y = max(MARGIN + node.height/2, 
                        min(self.height - MARGIN - node.height/2, node.y))

    def _route_edges(self, layout: GraphLayout) -> None:
        """Route edges with proper curvature based on graph direction"""
        for edge in layout.edges:
            source = layout.nodes[edge.from_id]
            target = layout.nodes[edge.to_id]
            
            # Start with direct points
            points = [(source.x, source.y)]
            
            # If edge spans multiple ranks, add intermediate points
            if source.rank < target.rank - 1:
                steps = target.rank - source.rank
                for i in range(1, steps):
                    progress = i / steps
                    if layout.direction in ["TD", "BT"]:
                        x = source.x + (target.x - source.x) * progress
                        y = source.y + (target.y - source.y) * progress
                    else:  # LR, RL
                        x = source.x + (target.x - source.x) * progress
                        y = source.y + (target.y - source.y) * progress
                    points.append((x, y))
            
            points.append((target.x, target.y))
            edge.points = points

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
                    'order': node.order,
                    'dummy': node.dummy
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
            'height': layout.height,
            'direction': layout.direction
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)