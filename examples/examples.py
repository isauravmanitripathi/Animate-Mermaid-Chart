# main.py

from parser.parser import MermaidParser
from layout.layout import SugiyamaLayoutGenerator
from animator.animator import MermaidAnimator, AnimationConfig, Node, Edge
import logging
# from mermaid_parser import MermaidParser
# from graph_generator import SugiyamaLayoutGenerator
# from mermaid_animator import MermaidAnimator, AnimationConfig, Node, Edge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_layout_to_animator(layout) -> tuple[dict[str, Node], list[Edge]]:
    """Convert layout to animator nodes and edges"""
    # Convert all nodes, including dummy nodes
    nodes = {
        node_id: Node(
            id=node_id,
            label=node.label if not getattr(node, 'dummy', False) else "",
            type=node.type,
            position=(node.x, node.y),
            layer=node.rank  # Use rank as layer
        )
        for node_id, node in layout.nodes.items()
    }
    
    # Convert edges with their calculated points
    edges = []
    for edge in layout.edges:
        if edge.points and len(edge.points) >= 2:
            # Find the real start and end nodes (non-dummy)
            real_start = edge.from_id
            real_end = edge.to_id
            
            # Work backwards to find real end node
            while getattr(layout.nodes[real_end], 'dummy', False):
                for e in layout.edges:
                    if e.from_id == real_end:
                        real_end = e.to_id
                        break
                        
            # Work forwards to find real start node
            while getattr(layout.nodes[real_start], 'dummy', False):
                for e in layout.edges:
                    if e.to_id == real_start:
                        real_start = e.from_id
                        break
            
            edges.append(Edge(
                start_node=real_start,
                end_node=real_end,
                label=edge.label,
                start_pos=edge.points[0],
                end_pos=edge.points[-1]
            ))
    
    return nodes, edges

def create_animated_diagram(mermaid_code: str, output_file: str = "animation.mp4"):
    """Create an animated diagram from Mermaid code"""
    logger.info("Step 1: Parsing Mermaid code")
    parser = MermaidParser()
    parsed_graph = parser.parse(mermaid_code)
    parser.save_json("parsed_graph.json")
    
    logger.info("Step 2: Generating layout")
    layout_generator = SugiyamaLayoutGenerator(
        width=1920,
        height=1080,
        node_spacing=150,
        rank_spacing=250
    )
    layout = layout_generator.generate_layout(parsed_graph)
    layout_generator.save_json(layout, "layout.json")
    
    logger.info("Step 3: Creating animation")
    config = AnimationConfig(
        width=1920,
        height=1080,
        fps=30,
        node_spacing=150,
        layer_spacing=250,
        animation_duration=1.5,
        background_color="white",
        node_color="white",
        edge_color="black",
        text_color="black"
    )
    
    animator = MermaidAnimator(config)
    nodes, edges = convert_layout_to_animator(layout)
    animator.nodes = nodes
    animator.edges = edges
    
    animator.create_animation(output_file)
    logger.info(f"Animation saved to {output_file}")

if __name__ == "__main__":
    # Example usage
    mermaid_code = """
	graph TD
    Idle[System Idle] --> Active{User Activity}
    Active -->|Data Request| Processing[Processing]
    Active -->|Timeout| Sleep[Sleep Mode]
    Processing --> Cache[(Check Cache)]
    Cache -->|Hit| Return[Return Data]
    Cache -->|Miss| Fetch[Fetch Data]
    Fetch --> Store[Update Cache]
    Store --> Return
    Sleep --> Idle
    Return --> Idle
    """
    
    create_animated_diagram(mermaid_code, "deployment_flow.mp4")