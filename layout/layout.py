# graph_generator.py

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set
import math
import json
from collections import defaultdict
import logging

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
    ranks: Dict[int, List[str]] = field(default_factory=lambda: defaultdict(list))

class SugiyamaLayoutGenerator:
    """Implements Sugiyama's algorithm for layered graph drawing"""
    
    def __init__(self, width: float = 1920, height: float = 1080,
                 node_spacing: float = 150, rank_spacing: float = 250):
        self.width = width
        self.height = height
        self.node_spacing = node_spacing
        self.rank_spacing = rank_spacing
        self.dummy_counter = 0
        
    def generate_layout(self, parsed_graph) -> GraphLayout:
        """Main method to generate layout"""
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
        layout = GraphLayout(nodes, edges, self.width, self.height)
        
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
    
    def _assign_coordinates(self, layout: GraphLayout) -> None:
        """Step 4: Assign final x,y coordinates to nodes with boundary constraints"""
        max_rank = max(layout.ranks.keys())
        
        # Calculate node dimensions including text padding
        TEXT_PADDING = 20  # Padding for text inside nodes
        
        # Calculate usable area (with margins)
        MARGIN = 100  # Margin from canvas edges
        usable_width = self.width - (2 * MARGIN)
        usable_height = self.height - (2 * MARGIN)
        
        # Calculate rank spacing based on usable width
        rank_spacing = usable_width / (max_rank + 1)
        
        # For each rank, calculate max nodes and adjust spacing
        max_nodes_in_rank = max(len(nodes) for nodes in layout.ranks.values())
        node_spacing = min(
            self.node_spacing,
            (usable_height) / (max_nodes_in_rank + 1)
        )
        
        # Assign x coordinates based on rank with margin
        for rank, nodes in layout.ranks.items():
            x = MARGIN + (rank + 1) * rank_spacing
            
            # Calculate total height needed for this rank
            total_height = (len(nodes) - 1) * node_spacing
            # Center the rank vertically
            start_y = MARGIN + (usable_height - total_height) / 2
            
            for i, node_id in enumerate(nodes):
                node = layout.nodes[node_id]
                # Set coordinates
                node.x = min(max(x, MARGIN), self.width - MARGIN)
                node.y = min(max(start_y + i * node_spacing, MARGIN), 
                           self.height - MARGIN)
                node.order = i
                
                # Adjust node size based on label length
                label_length = len(node.label) * 10  # Approximate width per character
                node.width = max(80, label_length + TEXT_PADDING * 2)
                
                # Ensure node doesn't exceed canvas
                if node.x - node.width/2 < MARGIN:
                    node.x = MARGIN + node.width/2
                if node.x + node.width/2 > self.width - MARGIN:
                    node.x = self.width - MARGIN - node.width/2
        
        # Calculate edge routing points
        self._route_edges(layout)
        
    def _route_edges(self, layout: GraphLayout) -> None:
        """Route edges avoiding node overlaps"""
        for edge in layout.edges:
            source = layout.nodes[edge.from_id]
            target = layout.nodes[edge.to_id]
            
            # Start and end points
            points = [(source.x, source.y)]
            
            # If edge spans multiple ranks, add intermediate points
            if source.rank < target.rank - 1:
                for rank in range(source.rank + 1, target.rank):
                    x = source.x + (target.x - source.x) * (rank - source.rank) / (target.rank - source.rank)
                    y = source.y + (target.y - source.y) * (rank - source.rank) / (target.rank - source.rank)
                    points.append((x, y))
            
            # Add target point
            points.append((target.x, target.y))
            
            # Store points in edge
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
                if not node.dummy  # Skip dummy nodes in output
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