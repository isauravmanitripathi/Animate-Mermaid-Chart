"""
MermaidAnimator: A library for creating animated diagrams from Mermaid syntax
"""

from parser.parser import MermaidParser
from layout.layout import SugiyamaLayoutGenerator
from PIL import Image, ImageDraw, ImageFont
import os
import shutil
from math import sin, cos, atan2, pi, tan
import subprocess
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Union
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

@dataclass
class Edge:
    """Represents an edge between nodes"""
    start_node: str
    end_node: str
    label: str
    start_pos: Optional[Tuple[float, float]] = None
    end_pos: Optional[Tuple[float, float]] = None

@dataclass
class AnimationConfig:
    """Configuration for animation settings"""
    width: int = 1920
    height: int = 1080
    fps: int = 30
    node_spacing: int = 200
    layer_spacing: int = 300
    animation_duration: float = 2.0
    background_color: str = "white"
    node_color: str = "white"
    edge_color: str = "black"
    text_color: str = "black"
    line_width: int = 3
    font_size: int = 20

class MermaidAnimator:
    """Main class for parsing Mermaid syntax and generating animations"""
    
    def __init__(self, config: Optional[AnimationConfig] = None):
        self.config = config or AnimationConfig()
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.layers: Dict[int, List[str]] = defaultdict(list)
        self._setup_font()
        
    def _setup_font(self):
        """Initialize font for text rendering"""
        try:
            self.font = ImageFont.truetype("Arial.ttf", self.config.font_size)
        except OSError:
            logger.warning("Arial font not found, using default font")
            self.font = ImageFont.load_default()

    def parse_mermaid(self, mermaid_code: str) -> None:
        """Parse Mermaid graph syntax and create internal representation"""
        lines = mermaid_code.strip().split('\n')
        self._parse_nodes_and_edges(lines)
        self._calculate_layout()
        
    def _parse_nodes_and_edges(self, lines: List[str]) -> None:
        """Parse nodes and edges from Mermaid code lines"""
        # Skip empty lines and find the graph declaration
        start_idx = 0
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('graph'):
                start_idx = i + 1
                break

        # Process remaining lines
        for line in lines[start_idx:]:
            line = line.strip()
            if not line or '-->' not in line:
                continue
                
            parts = line.split('-->')
            
            # Parse start node
            start_node = self._parse_node(parts[0])
            
            # Parse end node and edge label
            end_parts = parts[1].split('|')
            if len(end_parts) > 1:
                # Handle edge with label
                if len(end_parts) >= 2:
                    edge_label = end_parts[0].strip().strip('"').strip("'")
                    end_node_text = end_parts[-1].strip()
                else:
                    edge_label = ''
                    end_node_text = end_parts[0].strip()
            else:
                # No label
                edge_label = ''
                end_node_text = parts[1].strip()
                
            end_node = self._parse_node(end_node_text)
            
            # Add edge
            self.edges.append(Edge(
                start_node=start_node.id,
                end_node=end_node.id,
                label=edge_label
            ))
            start_node = self._parse_node(parts[0].strip())
            
            # Handle edge labels
            end_parts = parts[1].split('|')
            edge_label = ''
            if len(end_parts) > 1:
                edge_label = end_parts[1].strip()
                end_node = self._parse_node(end_parts[-1].strip())
            else:
                end_node = self._parse_node(parts[1].strip())
                
            self.edges.append(Edge(
                start_node=start_node.id,
                end_node=end_node.id,
                label=edge_label
            ))

    def _parse_node(self, node_text: str) -> Node:
        """Parse node text and create Node object"""
        node_text = node_text.strip()
        
        # Default values
        node_id = node_text
        node_label = node_text
        node_type = 'default'
        
        # Parse different node types
        if '[' in node_text and ']' in node_text:
            parts = node_text.split('[', 1)
            node_id = parts[0].strip()
            node_label = parts[1].split(']')[0].strip()
            node_type = 'square'
        elif '(' in node_text and ')' in node_text:
            parts = node_text.split('(', 1)
            node_id = parts[0].strip()
            node_label = parts[1].split(')')[0].strip()
            node_type = 'round'
        elif '{' in node_text and '}' in node_text:
            parts = node_text.split('{', 1)
            node_id = parts[0].strip()
            node_label = parts[1].split('}')[0].strip()
            node_type = 'diamond'
            
        # Clean up node ID by removing any remaining whitespace and quotes
        node_id = node_id.strip().strip('"').strip("'")
            
        if node_id not in self.nodes:
            self.nodes[node_id] = Node(
                id=node_id,
                label=node_label,
                type=node_type
            )
            
        return self.nodes[node_id]

    def _calculate_layout(self) -> None:
        """Calculate hierarchical layout of nodes"""
        # Find root nodes (nodes with no incoming edges)
        incoming_edges = {edge.end_node for edge in self.edges}
        root_nodes = [node_id for node_id in self.nodes if node_id not in incoming_edges]
        
        if not root_nodes:
            # If no clear root, use the first node in the graph
            root_nodes = [next(iter(self.nodes.keys()))]
            logger.warning(f"No root nodes found, using {root_nodes[0]} as root")
        
        # Assign layers using BFS
        visited = set()
        current_layer = root_nodes
        layer = 0
        
        logger.info(f"Starting layout with root nodes: {root_nodes}")
        
        while current_layer:
            self.layers[layer] = current_layer
            for node_id in current_layer:
                self.nodes[node_id].layer = layer
                visited.add(node_id)
            
            next_layer = []
            for edge in self.edges:
                if edge.start_node in current_layer and edge.end_node not in visited:
                    next_layer.append(edge.end_node)
            
            current_layer = list(set(next_layer))
            layer += 1
            
        self._assign_positions()

    def _assign_positions(self) -> None:
        """Assign x,y coordinates to nodes based on their layer"""
        max_layer = max(self.layers.keys())
        
        for layer_num, layer_nodes in self.layers.items():
            x = (layer_num + 1) * self.config.layer_spacing
            
            if len(layer_nodes) == 1:
                y = self.config.height / 2
                self.nodes[layer_nodes[0]].position = (x, y)
            else:
                total_height = (len(layer_nodes) - 1) * self.config.node_spacing
                start_y = (self.config.height - total_height) / 2
                
                for i, node_id in enumerate(layer_nodes):
                    y = start_y + i * self.config.node_spacing
                    self.nodes[node_id].position = (x, y)
        
        # Update edge positions
        for edge in self.edges:
            edge.start_pos = self.nodes[edge.start_node].position
            edge.end_pos = self.nodes[edge.end_node].position

    def _create_frame(self, time: float, frame_number: int, temp_dir: str) -> str:
        """Create a single frame of the animation"""
        img = Image.new('RGB', (self.config.width, self.config.height), 
                       self.config.background_color)
        draw = ImageDraw.Draw(img)
        
        # Draw edges first
        for edge in self.edges:
            if edge.start_pos and edge.end_pos:  # Only draw edges with positions
                start_layer = self.nodes[edge.start_node].layer
                progress = max(0, min(1, (time - start_layer) / self.config.animation_duration))
                
                if progress > 0:
                    self._draw_edge(draw, edge, progress)
        
        # Draw non-dummy nodes
        for node in self.nodes.values():
            if node.label:  # Skip dummy nodes (they have empty labels)
                progress = max(0, min(1, (time - node.layer) / self.config.animation_duration))
                if progress > 0:
                    self._draw_node(draw, node, progress)
        
        frame_path = os.path.join(temp_dir, f"frame_{frame_number:04d}.png")
        img.save(frame_path, quality=95, optimize=True)
        return frame_path

    def _draw_node(self, draw: ImageDraw, node: Node, progress: float) -> None:
        """Draw a node with animation progress and contained text"""
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
        
        # Draw node shape based on type
        if node.type == 'diamond':
            points = [
                (x, y - h/2),
                (x + w/2, y),
                (x, y + h/2),
                (x - w/2, y)
            ]
            # Draw fill first
            draw.polygon(points, fill=self.config.node_color)
            # Draw outline as multiple lines
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
        
        if progress > 0.5:  # Draw text after node is mostly visible
            # Calculate text position to stay within node bounds
            if len(node.label) > 20:  # Wrap long text
                words = node.label.split()
                lines = []
                current_line = []
                current_width = 0
                
                # Word wrap algorithm
                for word in words:
                    word_bbox = draw.textbbox((0, 0), word + " ", font=self.font)
                    word_width = word_bbox[2] - word_bbox[0]
                    
                    if current_width + word_width <= w - PADDING * 2:
                        current_line.append(word)
                        current_width += word_width
                    else:
                        if current_line:
                            lines.append(" ".join(current_line))
                        current_line = [word]
                        current_width = word_width
                
                if current_line:
                    lines.append(" ".join(current_line))
                
                # Draw wrapped text
                total_height = len(lines) * text_height
                start_y = y - total_height/2
                
                for i, line in enumerate(lines):
                    line_bbox = draw.textbbox((0, 0), line, font=self.font)
                    line_width = line_bbox[2] - line_bbox[0]
                    text_x = x - line_width/2
                    text_y = start_y + i * text_height
                    draw.text((text_x, text_y), line,
                            fill=self.config.text_color,
                            font=self.font)
            else:
                # Draw single line text
                text_x = x - text_width/2
                text_y = y - text_height/2
                draw.text((text_x, text_y), node.label,
                         fill=self.config.text_color,
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
        
        draw.line([start[0], start[1], current_x, current_y], 
                 fill=self.config.edge_color, 
                 width=self.config.line_width)
        
        # Draw arrow head
        if progress > 0.9:
            self._draw_arrow_head(draw, start, end)
        
        # Draw edge label
        if edge.label and progress > 0.5:
            self._draw_edge_label(draw, edge.label, start, end)

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

    def _draw_arrow_head(self, draw: ImageDraw, start: Tuple[float, float], 
                        end: Tuple[float, float]) -> None:
        """Draw arrow head at the end of an edge"""
        arrow_size = 15
        angle = atan2(end[1] - start[1], end[0] - start[0])
        
        ax1 = end[0] - arrow_size * cos(angle - pi/6)
        ay1 = end[1] - arrow_size * sin(angle - pi/6)
        ax2 = end[0] - arrow_size * cos(angle + pi/6)
        ay2 = end[1] - arrow_size * sin(angle + pi/6)
        
        draw.polygon([(end[0], end[1]), (ax1, ay1), (ax2, ay2)], 
                    fill=self.config.edge_color)

    def _draw_text(self, draw: ImageDraw, text: str, position: Tuple[float, float]) -> None:
        """Draw text centered at position"""
        x, y = position
        text_bbox = draw.textbbox((0, 0), text, font=self.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        text_x = x - text_width/2
        text_y = y - text_height/2
        draw.text((text_x, text_y), text, 
                 fill=self.config.text_color, 
                 font=self.font)

    def _draw_edge_label(self, draw: ImageDraw, label: str, 
                        start: Tuple[float, float], 
                        end: Tuple[float, float]) -> None:
        """Draw label on edge with background"""
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2 - 15
        
        text_bbox = draw.textbbox((0, 0), label, font=self.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        label_x = mid_x - text_width/2
        label_y = mid_y - text_height/2
        
        # Draw white background for label
        padding = 5
        draw.rectangle([
            label_x - padding,
            label_y - padding,
            label_x + text_width + padding,
            label_y + text_height + padding
        ], fill=self.config.background_color)
        
        draw.text((label_x, label_y), label, 
                 fill=self.config.text_color, 
                 font=self.font)

    def create_animation(self, output_filename: str = "animation.mp4") -> None:
        """Create the final animation video"""
        temp_dir = "output_frames"
        
        # Setup temporary directory for frames
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        try:
            # Calculate total animation duration
            max_layer = max(node.layer for node in self.nodes.values())
            total_duration = (max_layer + 1) * self.config.animation_duration
            
            # Generate frames
            total_frames = int(total_duration * self.config.fps)
            logger.info(f"Generating {total_frames} frames...")
            
            for frame in range(total_frames):
                t = frame / self.config.fps
                self._create_frame(t, frame, temp_dir)
                
                if frame % 10 == 0:  # Progress update every 10 frames
                    logger.info(f"Progress: {frame}/{total_frames} frames")
            
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
                    'layer': node.layer
                } for node_id, node in self.nodes.items()
            },
            'edges': [
                {
                    'start_node': edge.start_node,
                    'end_node': edge.end_node,
                    'label': edge.label,
                    'start_pos': edge.start_pos,
                    'end_pos': edge.end_pos
                } for edge in self.edges
            ],
            'config': {
                'width': self.config.width,
                'height': self.config.height,
                'fps': self.config.fps,
                'node_spacing': self.config.node_spacing,
                'layer_spacing': self.config.layer_spacing,
                'animation_duration': self.config.animation_duration
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
                layer=node_data['layer']
            )
            
        # Reconstruct edges
        for edge_data in layout_data['edges']:
            animator.edges.append(Edge(
                start_node=edge_data['start_node'],
                end_node=edge_data['end_node'],
                label=edge_data['label'],
                start_pos=tuple(edge_data['start_pos']) if edge_data['start_pos'] else None,
                end_pos=tuple(edge_data['end_pos']) if edge_data['end_pos'] else None
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
        animation_duration=2.0,
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
    animator.parse_mermaid(mermaid_code)
    
    # Optionally save layout for later use
    animator.save_layout_json("example_layout.json")
    
    # Create the animation
    animator.create_animation("example_animation.mp4")


if __name__ == "__main__":
    create_example_animation()