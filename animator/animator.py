"""
MermaidAnimator: A library for creating animated diagrams from Mermaid syntax with sequential animation
"""

from parser.parser import MermaidParser
from layout.layout import SugiyamaLayoutGenerator
from PIL import Image, ImageDraw, ImageFont
import os
import shutil
from math import sin, cos, atan2, pi, tan
import subprocess
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Union, Set
from dataclasses import dataclass
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Node:
    """Represents a node in the diagram"""
    id: str
    label: str
    type: str  # 'default', 'square', 'round', 'diamond'
    position: Optional[Tuple[float, float]] = None
    layer: int = 0
    sequence_number: int = 0  # Added for sequential animation
    animation_start_time: float = 0.0  # When this node starts animating

@dataclass
class Edge:
    """Represents an edge between nodes"""
    start_node: str
    end_node: str
    label: str
    start_pos: Optional[Tuple[float, float]] = None
    end_pos: Optional[Tuple[float, float]] = None
    sequence_number: int = 0  # Added for sequential animation
    animation_start_time: float = 0.0  # When this edge starts animating

@dataclass
class AnimationConfig:
    """Configuration for animation settings"""
    width: int = 1920
    height: int = 1080
    fps: int = 30
    node_spacing: int = 200
    layer_spacing: int = 300
    node_animation_duration: float = 0.5  # Duration for each node animation
    edge_animation_duration: float = 0.5  # Duration for each edge animation
    node_delay: float = 0.2  # Delay before next node starts
    edge_delay: float = 0.2  # Delay before connected edge starts
    background_color: str = "white"
    node_color: str = "white"
    edge_color: str = "black"
    text_color: str = "black"
    line_width: int = 3
    font_size: int = 20

class MermaidAnimator:
    """Main class for parsing Mermaid syntax and generating sequential animations"""
    
    def __init__(self, config: Optional[AnimationConfig] = None):
        self.config = config or AnimationConfig()
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._sequence_count = 0  # Track animation sequence
        self._total_duration = 0.0  # Total animation duration
        self._setup_font()
        
    def _setup_font(self):
        """Initialize font for text rendering"""
        try:
            self.font = ImageFont.truetype("Arial.ttf", self.config.font_size)
        except OSError:
            logger.warning("Arial font not found, using default font")
            self.font = ImageFont.load_default()

    def _calculate_animation_sequence(self):
        """Calculate the sequence of node and edge animations"""
        # Reset sequence tracking
        self._sequence_count = 0
        current_time = 0.0
        processed_nodes = set()
        
        # Find root nodes (nodes with no incoming edges)
        incoming_edges = {edge.end_node for edge in self.edges}
        root_nodes = [nid for nid in self.nodes if nid not in incoming_edges]
        if not root_nodes:
            root_nodes = [next(iter(self.nodes.keys()))]
        
        # Process nodes in sequence
        nodes_to_process = root_nodes.copy()
        while nodes_to_process:
            current_node_id = nodes_to_process.pop(0)
            if current_node_id in processed_nodes:
                continue
                
            # Set node sequence and timing
            node = self.nodes[current_node_id]
            node.sequence_number = self._sequence_count
            node.animation_start_time = current_time
            self._sequence_count += 1
            processed_nodes.add(current_node_id)
            
            # Find connected edges and nodes
            connected_edges = [edge for edge in self.edges if edge.start_node == current_node_id]
            for edge in connected_edges:
                # Set edge timing slightly after node appears
                edge.sequence_number = self._sequence_count
                edge.animation_start_time = current_time + self.config.node_animation_duration + self.config.edge_delay
                self._sequence_count += 1
                
                # Queue connected node if not processed
                if edge.end_node not in processed_nodes:
                    nodes_to_process.append(edge.end_node)
            
            # Update timing for next node
            current_time += (self.config.node_animation_duration + self.config.node_delay)
        
        # Store total animation duration
        self._total_duration = current_time + self.config.node_animation_duration

    def _calculate_element_progress(self, time: float, start_time: float, duration: float) -> float:
        """Calculate animation progress for an element"""
        if time < start_time:
            return 0.0
        if time >= start_time + duration:
            return 1.0
        return (time - start_time) / duration

    def _create_frame(self, time: float, frame_number: int, temp_dir: str) -> str:
        """Create a single frame of the animation with sequential node and edge appearance"""
        img = Image.new('RGB', (self.config.width, self.config.height), 
                       self.config.background_color)
        draw = ImageDraw.Draw(img)
        
        # Process edges first (they'll be drawn behind nodes)
        for edge in self.edges:
            progress = self._calculate_element_progress(
                time, 
                edge.animation_start_time,
                self.config.edge_animation_duration
            )
            if progress > 0:
                self._draw_edge(draw, edge, progress)
        
        # Process nodes
        for node in self.nodes.values():
            progress = self._calculate_element_progress(
                time,
                node.animation_start_time,
                self.config.node_animation_duration
            )
            if progress > 0:
                self._draw_node(draw, node, progress)
        
        frame_path = os.path.join(temp_dir, f"frame_{frame_number:04d}.png")
        img.save(frame_path, quality=95, optimize=True)
        return frame_path

    def _draw_node(self, draw: ImageDraw, node: Node, progress: float) -> None:
        """Draw a node with animation progress"""
        if not node.position:
            return
            
        x, y = node.position
        
        # Calculate node size based on text
        text_bbox = draw.textbbox((0, 0), node.label, font=self.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        # Add padding around text
        PADDING = 20
        w = max(80, text_width + PADDING * 2) * progress
        h = max(80, text_height + PADDING * 2) * progress
        
        # Draw node based on type with animation
        if node.type == 'diamond':
            points = [
                (x, y - h/2),
                (x + w/2, y),
                (x, y + h/2),
                (x - w/2, y)
            ]
            draw.polygon(points, fill=self.config.node_color)
            for i in range(len(points)):
                start = points[i]
                end = points[(i + 1) % len(points)]
                draw.line([start, end], fill=self.config.edge_color, 
                         width=self.config.line_width)
                         
        elif node.type == 'round':
            left = x - w/2
            top = y - h/2
            right = x + w/2
            bottom = y + h/2
            draw.ellipse([left, top, right, bottom], 
                        outline=self.config.edge_color,
                        fill=self.config.node_color, 
                        width=self.config.line_width)
                        
        else:  # square or default
            left = x - w/2
            top = y - h/2
            right = x + w/2
            bottom = y + h/2
            draw.rectangle([left, top, right, bottom], 
                         outline=self.config.edge_color,
                         fill=self.config.node_color, 
                         width=self.config.line_width)
        
        # Draw text with fade-in effect
        if progress > 0.5:
            text_progress = min(1, (progress - 0.5) * 2)
            text_x = x - text_width/2
            text_y = y - text_height/2
            
            # Handle color conversion and alpha
            if isinstance(self.config.text_color, str):
                if self.config.text_color == "black":
                    text_color = (0, 0, 0, int(255 * text_progress))
                else:
                    text_color = (0, 0, 0, int(255 * text_progress))
            else:
                text_color = (*self.config.text_color[:3], int(255 * text_progress))
                
            draw.text((text_x, text_y), node.label,
                     fill=text_color,
                     font=self.font)

    def _draw_edge(self, draw: ImageDraw, edge: Edge, progress: float) -> None:
        """Draw an edge with animation progress"""
        if not edge.start_pos or not edge.end_pos:
            return
            
        start = self._calculate_intersection(edge.start_pos, edge.end_pos, (80, 80), True)
        end = self._calculate_intersection(edge.start_pos, edge.end_pos, (80, 80), False)
        
        # Animate line drawing
        current_x = start[0] + (end[0] - start[0]) * progress
        current_y = start[1] + (end[1] - start[1]) * progress
        
        # Draw the line
        draw.line([start[0], start[1], current_x, current_y], 
                 fill=self.config.edge_color, 
                 width=self.config.line_width)
        
        # Draw arrow head when edge is mostly drawn
        if progress > 0.8:
            arrow_progress = min(1, (progress - 0.8) * 5)
            self._draw_arrow_head(draw, (current_x, current_y), end, arrow_progress)
        
        # Draw edge label with fade in
        if edge.label and progress > 0.5:
            label_progress = min(1, (progress - 0.5) * 2)
            self._draw_edge_label(draw, edge.label, start, (current_x, current_y), label_progress)

    def _calculate_intersection(self, start_pos: Tuple[float, float], 
                              end_pos: Tuple[float, float],
                              box_size: Tuple[float, float], 
                              is_start: bool) -> Tuple[float, float]:
        """Calculate where line intersects with node boundary"""
        x1, y1 = start_pos
        x2, y2 = end_pos
        w, h = box_size
        
        angle = atan2(y2 - y1, x2 - x1)
        center = start_pos if is_start else end_pos
        
        if abs(cos(angle)) > abs(sin(angle)):
            x_offset = (w/2) * (1 if is_start else -1)
            y_offset = x_offset * tan(angle)
        else:
            y_offset = (h/2) * (1 if is_start else -1)
            x_offset = y_offset / tan(angle)
            
        return (center[0] + x_offset, center[1] + y_offset)

    def _draw_arrow_head(self, draw: ImageDraw, current: Tuple[float, float], 
                        end: Tuple[float, float], progress: float) -> None:
        """Draw arrow head with animation progress"""
        arrow_size = 15 * progress
        angle = atan2(end[1] - current[1], end[0] - current[0])
        
        ax1 = current[0] - arrow_size * cos(angle - pi/6)
        ay1 = current[1] - arrow_size * sin(angle - pi/6)
        ax2 = current[0] - arrow_size * cos(angle + pi/6)
        ay2 = current[1] - arrow_size * sin(angle + pi/6)
        
        draw.polygon([(current[0], current[1]), (ax1, ay1), (ax2, ay2)], 
                    fill=self.config.edge_color)

    def _draw_edge_label(self, draw: ImageDraw, label: str, start: Tuple[float, float], 
                        current: Tuple[float, float], progress: float) -> None:
        """Draw edge label with fade-in effect"""
        mid_x = (start[0] + current[0]) / 2
        mid_y = (start[1] + current[1]) / 2 - 15
        
        text_bbox = draw.textbbox((0, 0), label, font=self.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        label_x = mid_x - text_width/2
        label_y = mid_y - text_height/2
        
        # Draw background with fade-in
        padding = 5
        draw.rectangle([
            label_x - padding,
            label_y - padding,
            label_x + text_width + padding,
            label_y + text_height + padding
        ], fill=self.config.background_color)
        
        # Draw text with fade-in
        if isinstance(self.config.text_color, str):
            if self.config.text_color == "black":
                text_color = (0, 0, 0, int(255 * progress))
            else:
                text_color = (0, 0, 0, int(255 * progress))
        else:
            text_color = (*self.config.text_color[:3], int(255 * progress))
            
        draw.text((label_x, label_y), label, 
                 fill=text_color,
                 font=self.font)

    def create_animation(self, output_filename: str = "animation.mp4") -> None:
        """Create the final animation video with sequential appearance"""
        temp_dir = "output_frames"
        
        # Calculate animation sequence and timing
        self._calculate_animation_sequence()
        
        # Setup temporary directory for frames
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        try:
            # Calculate total frames needed
            total_frames = int(self._total_duration * self.config.fps)
            logger.info(f"Generating {total_frames} frames for {self._total_duration:.2f} seconds of animation...")
            
            for frame in range(total_frames):
                t = frame / self.config.fps
                self._create_frame(t, frame, temp_dir)
                
                if frame % 10 == 0:  # Progress update every 10 frames
                    logger.info(f"Progress: {frame}/{total_frames} frames ({(frame/total_frames*100):.1f}%)")
            
            # Combine frames into video using ffmpeg
            logger.info("Creating video with ffmpeg...")
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file if it exists
                '-framerate', str(self.config.fps),
                '-i', os.path.join(temp_dir, 'frame_%04d.png'),
                '-c:v', 'libx264',
                '-preset', 'slow',
                '-crf', '18',
                '-pix_fmt', 'yuv420p',
                output_filename
            ]
            
            try:
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
                logger.info(f"Animation saved to {output_filename}")
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg error: {e.stderr.decode()}")
                raise RuntimeError("Failed to create video with FFmpeg")
                
        finally:
            # Cleanup temporary files
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def save_layout_json(self, filename: str) -> None:
        """Save the current layout to a JSON file"""
        layout_data = {
            'nodes': {
                node_id: {
                    'label': node.label,
                    'type': node.type,
                    'position': node.position,
                    'layer': node.layer,
                    'sequence_number': node.sequence_number,
                    'animation_start_time': node.animation_start_time
                } for node_id, node in self.nodes.items()
            },
            'edges': [
                {
                    'start_node': edge.start_node,
                    'end_node': edge.end_node,
                    'label': edge.label,
                    'start_pos': edge.start_pos,
                    'end_pos': edge.end_pos,
                    'sequence_number': edge.sequence_number,
                    'animation_start_time': edge.animation_start_time
                } for edge in self.edges
            ],
            'config': {
                'width': self.config.width,
                'height': self.config.height,
                'fps': self.config.fps,
                'node_spacing': self.config.node_spacing,
                'layer_spacing': self.config.layer_spacing,
                'node_animation_duration': self.config.node_animation_duration,
                'edge_animation_duration': self.config.edge_animation_duration,
                'node_delay': self.config.node_delay,
                'edge_delay': self.config.edge_delay
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(layout_data, f, indent=2)
            
    @classmethod
    def load_layout_json(cls, filename: str) -> 'MermaidAnimator':
        """Create a new MermaidAnimator instance from a saved layout"""
        with open(filename, 'r') as f:
            layout_data = json.load(f)
            
        config = AnimationConfig(**layout_data['config'])
        animator = cls(config)
        
        # Reconstruct nodes
        for node_id, node_data in layout_data['nodes'].items():
            animator.nodes[node_id] = Node(
                id=node_id,
                label=node_data['label'],
                type=node_data['type'],
                position=tuple(node_data['position']) if node_data['position'] else None,
                layer=node_data['layer'],
                sequence_number=node_data['sequence_number'],
                animation_start_time=node_data['animation_start_time']
            )
            
        # Reconstruct edges
        for edge_data in layout_data['edges']:
            animator.edges.append(Edge(
                start_node=edge_data['start_node'],
                end_node=edge_data['end_node'],
                label=edge_data['label'],
                start_pos=tuple(edge_data['start_pos']) if edge_data['start_pos'] else None,
                end_pos=tuple(edge_data['end_pos']) if edge_data['end_pos'] else None,
                sequence_number=edge_data['sequence_number'],
                animation_start_time=edge_data['animation_start_time']
            ))
            
        return animator


def create_example_animation():
    """Create an example animation to demonstrate usage"""
    # Create custom configuration
    config = AnimationConfig(
        width=1920,
        height=1080,
        fps=30,
        node_spacing=200,
        layer_spacing=300,
        node_animation_duration=0.5,
        edge_animation_duration=0.5,
        node_delay=0.2,
        edge_delay=0.2,
        background_color="white",
        node_color="white",
        edge_color="black",
        text_color="black"
    )
    
    # Initialize animator with config
    animator = MermaidAnimator(config)
    
    # Example Mermaid code
    mermaid_code = """
    graph TD
        A[Start] --> B{Is it?}
        B -->|Yes| C[OK]
        B -->|No| D[End]
        C --> D
        C --> E[Rethink]
        E --> B
    """
    
    # Parse and create animation
    parser = MermaidParser()
    layout_generator = SugiyamaLayoutGenerator(
        width=config.width,
        height=config.height,
        node_spacing=config.node_spacing,
        rank_spacing=config.layer_spacing
    )
    
    parsed_graph = parser.parse(mermaid_code)
    layout = layout_generator.generate_layout(parsed_graph)
    
    # Convert layout to animator format
    for node_id, layout_node in layout.nodes.items():
        animator.nodes[node_id] = Node(
            id=node_id,
            label=layout_node.label,
            type=layout_node.type,
            position=(layout_node.x, layout_node.y),
            layer=layout_node.rank
        )
    
    for edge in layout.edges:
        if edge.points and len(edge.points) >= 2:
            animator.edges.append(Edge(
                start_node=edge.from_id,
                end_node=edge.to_id,
                label=edge.label,
                start_pos=edge.points[0],
                end_pos=edge.points[-1]
            ))
    
    # Create the animation
    animator.create_animation("example_animation.mp4")


if __name__ == "__main__":
    create_example_animation()