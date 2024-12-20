# main.py

from animator.animator import MermaidAnimator, AnimationConfig, Node, Edge
from examples.examples import MermaidExamples
from parser.parser import MermaidParser
from layout.layout import SugiyamaLayoutGenerator
import logging

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
            edges.append(Edge(
                start_node=edge.from_id,
                end_node=edge.to_id,
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
    # Choose which example to run by uncommenting it
    
    # 1. Software Architecture
    #mermaid_code = MermaidExamples.get_software_architecture()
    #create_animated_diagram(mermaid_code, "software_architecture.mp4")
    
    # 2. Business Process
     mermaid_code = MermaidExamples.get_business_process()
     create_animated_diagram(mermaid_code, "business_process.mp4")
    
    # 3. System State
    # mermaid_code = MermaidExamples.get_system_state()
    # create_animated_diagram(mermaid_code, "system_state.mp4")
    
    # 4. Indian Economy
    # mermaid_code = MermaidExamples.get_indian_economy()
    # create_animated_diagram(mermaid_code, "indian_economy.mp4")