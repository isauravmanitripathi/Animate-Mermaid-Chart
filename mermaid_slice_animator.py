#!/usr/bin/env python3
"""
Mermaid Slice Animator - Creates an animation from a pre-rendered Mermaid diagram
by slicing it into components and revealing them sequentially.
"""

import os
import sys
import json
import logging
import argparse
import subprocess
import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Union, Set
from PIL import Image, ImageDraw, ImageFont
import re
import math

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class DiagramElement:
    """Represents a node or edge in the diagram"""
    id: str
    type: str  # 'node', 'edge', 'label'
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    element_order: int = 0
    source_element: Optional[str] = None  # For edges, the source node ID
    target_element: Optional[str] = None  # For edges, the target node ID
    
@dataclass
class AnimationConfig:
    """Configuration for animation settings"""
    width: int = 1920
    height: int = 1080
    fps: int = 30
    frame_delay: float = 0.5  # Seconds between adding elements
    fade_duration: float = 0.3  # Seconds for each element to fade in
    background_color: str = "white"
    output_folder: str = "output_frames"
    output_video: str = "animation.mp4"

class MermaidSliceAnimator:
    """Main class for creating animations from pre-rendered Mermaid diagrams"""
    
    def __init__(self, config: Optional[AnimationConfig] = None):
        self.config = config or AnimationConfig()
        self.elements: Dict[str, DiagramElement] = {}
        self.element_order: List[str] = []
        self.full_image: Optional[Image.Image] = None
        self.svg_content: Optional[str] = None
        self.background_image: Optional[Image.Image] = None
        
    def render_mermaid(self, mermaid_code: str, output_prefix: str) -> Tuple[str, str]:
        """Render Mermaid code to SVG and PNG using mmdc CLI"""
        # Save Mermaid code to a temporary file
        temp_dir = tempfile.mkdtemp()
        mmd_path = os.path.join(temp_dir, "diagram.mmd")
        
        with open(mmd_path, 'w') as f:
            f.write(mermaid_code)
        
        # Define output paths
        svg_path = f"{output_prefix}.svg"
        png_path = f"{output_prefix}.png"
        
        # Execute mmdc command to generate SVG
        svg_cmd = [
            'mmdc',
            '-i', mmd_path,
            '-o', svg_path,
            '-t', 'neutral',
            '-b', 'transparent'
        ]
        
        try:
            logger.info("Generating SVG with Mermaid CLI...")
            subprocess.run(svg_cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Mermaid CLI error for SVG: {e.stderr.decode()}")
            raise RuntimeError("Failed to generate SVG with Mermaid CLI")
        
        # Execute mmdc command to generate PNG with higher resolution
        png_cmd = [
            'mmdc',
            '-i', mmd_path,
            '-o', png_path,
            '-t', 'neutral',
            '-b', 'transparent',
            '-w', '2000',  # Set a large width for high resolution
            '-H', '3000'   # Set a large height for high resolution
        ]
        
        try:
            logger.info("Generating PNG with Mermaid CLI...")
            subprocess.run(png_cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Mermaid CLI error for PNG: {e.stderr.decode()}")
            raise RuntimeError("Failed to generate PNG with Mermaid CLI")
            
        # Cleanup temporary directory
        shutil.rmtree(temp_dir)
        
        return svg_path, png_path
        
    def parse_svg_elements(self, svg_path: str) -> None:
        """Parse SVG to extract diagram elements and their positions"""
        # Load SVG content
        with open(svg_path, 'r') as f:
            self.svg_content = f.read()
        
        # Parse SVG using ElementTree
        tree = ET.parse(svg_path)
        root = tree.getroot()
        
        # Extract SVG namespace if present
        ns = {}
        ns_match = re.match(r'{(.*)}', root.tag)
        if ns_match:
            svg_ns = ns_match.group(1)
            ns['svg'] = svg_ns
        
        # Find all node elements (typically rectangles, ellipses, polygons)
        node_elements = []
        
        # Helper function to get namespace-aware tag
        def nstag(tag):
            if ns:
                return f"{{{ns['svg']}}}{tag}"
            return tag
        
        # Find all group elements that might contain nodes
        groups = root.findall(f".//{nstag('g')}")
        node_id_counter = 0
        edge_id_counter = 0
        
        # Extract elements from the SVG
        for group in groups:
            # Check if this is a node group (class="node")
            class_attr = group.get('class', '')
            
            if 'node' in class_attr:
                # This is a node
                node_id = f"node_{node_id_counter}"
                node_id_counter += 1
                
                # Find the node shape (rect, ellipse, polygon)
                rect = group.find(f".//{nstag('rect')}")
                ellipse = group.find(f".//{nstag('ellipse')}")
                polygon = group.find(f".//{nstag('polygon')}")
                
                # Extract bounding box
                if rect is not None:
                    x = float(rect.get('x', 0))
                    y = float(rect.get('y', 0))
                    width = float(rect.get('width', 0))
                    height = float(rect.get('height', 0))
                    bbox = (int(x), int(y), int(width), int(height))
                    
                elif ellipse is not None:
                    cx = float(ellipse.get('cx', 0))
                    cy = float(ellipse.get('cy', 0))
                    rx = float(ellipse.get('rx', 0))
                    ry = float(ellipse.get('ry', 0))
                    bbox = (int(cx - rx), int(cy - ry), int(rx * 2), int(ry * 2))
                    
                elif polygon is not None:
                    # For polygons, we need to find min/max coordinates
                    points_str = polygon.get('points', '')
                    point_pairs = points_str.strip().split(' ')
                    
                    # Parse point coordinates
                    points = []
                    for pp in point_pairs:
                        if ',' in pp:
                            x, y = pp.split(',')
                            points.append((float(x), float(y)))
                    
                    # Find bounding box
                    if points:
                        min_x = min(p[0] for p in points)
                        min_y = min(p[1] for p in points)
                        max_x = max(p[0] for p in points)
                        max_y = max(p[1] for p in points)
                        
                        bbox = (int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y))
                    else:
                        # Fallback for malformed polygons
                        bbox = (0, 0, 10, 10)
                else:
                    # Fallback for unknown shape
                    bbox = (0, 0, 10, 10)
                
                # Add node to elements
                self.elements[node_id] = DiagramElement(
                    id=node_id,
                    type='node',
                    bbox=bbox
                )
                
            elif 'edge' in class_attr:
                # This is an edge
                edge_id = f"edge_{edge_id_counter}"
                edge_id_counter += 1
                
                # Find the path element for the edge
                path = group.find(f".//{nstag('path')}")
                
                if path is not None:
                    # For edges, get the bounding box that encompasses the path
                    # Find the path's bounding box from its d attribute
                    d_attr = path.get('d', '')
                    
                    # Extract all numeric values from the path data
                    numbers = re.findall(r'[-+]?\d*\.\d+|\d+', d_attr)
                    
                    if len(numbers) >= 4:  # Need at least 2 points (x,y pairs)
                        # Convert to floats
                        numbers = [float(n) for n in numbers]
                        
                        # Group into x,y pairs
                        points = [(numbers[i], numbers[i+1]) for i in range(0, len(numbers) - 1, 2)]
                        
                        # Find bounding box
                        min_x = min(p[0] for p in points)
                        min_y = min(p[1] for p in points)
                        max_x = max(p[0] for p in points)
                        max_y = max(p[1] for p in points)
                        
                        bbox = (int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y))
                    else:
                        # Fallback for malformed paths
                        bbox = (0, 0, 10, 10)
                else:
                    # Fallback if no path found
                    bbox = (0, 0, 10, 10)
                
                # Extract source and target node information if available
                # Mermaid edges typically have data attributes or markers
                # This is simplified - in a real scenario, you'd need to parse 
                # Mermaid-specific SVG structure to find source/target
                
                # Add edge to elements
                self.elements[edge_id] = DiagramElement(
                    id=edge_id,
                    type='edge',
                    bbox=bbox
                )
        
        # After extracting all elements, determine element order based on vertical position
        # (top-to-bottom for TD or BT diagrams)
        elements_with_position = [(elem_id, elem) for elem_id, elem in self.elements.items()]
        
        # Sort by y position (for TD/BT diagrams)
        elements_with_position.sort(key=lambda x: x[1].bbox[1])
        
        # Assign element order
        for i, (elem_id, _) in enumerate(elements_with_position):
            self.elements[elem_id].element_order = i
            self.element_order.append(elem_id)
            
    def load_full_image(self, png_path: str) -> None:
        """Load the full diagram image from PNG"""
        try:
            self.full_image = Image.open(png_path).convert("RGBA")
            
            # Create background image
            self.background_image = Image.new(
                "RGBA", 
                self.full_image.size, 
                self.config.background_color
            )
            
            logger.info(f"Loaded image with dimensions: {self.full_image.size}")
        except Exception as e:
            logger.error(f"Error loading PNG: {str(e)}")
            raise RuntimeError(f"Failed to load PNG from {png_path}")
    
    def create_animation_frames(self) -> None:
        """Create animation frames with progressive element reveal"""
        if not self.full_image:
            raise ValueError("No full image loaded. Call load_full_image() first.")
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.config.output_folder):
            os.makedirs(self.config.output_folder)
        
        # Calculate total frames
        element_count = len(self.element_order)
        frames_per_element = int(self.config.frame_delay * self.config.fps)
        fade_frames = int(self.config.fade_duration * self.config.fps)
        total_frames = element_count * frames_per_element
        
        logger.info(f"Creating {total_frames} frames for {element_count} elements...")
        
        # Start with empty canvas
        base_image = Image.new(
            "RGBA", 
            self.full_image.size, 
            self.config.background_color
        )
        
        frame_count = 0
        active_elements = []
        
        # For each frame in the animation
        for element_idx in range(element_count + 1):  # +1 to show the complete diagram at the end
            # Determine which elements are active for this frame
            if element_idx < element_count:
                active_elements.append(self.element_order[element_idx])
            
            # Create frames for this element transition
            for transition_frame in range(frames_per_element):
                # Create a new frame image
                frame = base_image.copy()
                
                # Add all fully revealed elements
                for elem_id in active_elements[:-1] if active_elements else []:
                    elem = self.elements[elem_id]
                    x, y, w, h = elem.bbox
                    
                    # Crop the element from the full image
                    element_img = self.full_image.crop((x, y, x + w, y + h))
                    
                    # Paste onto the frame with transparency
                    frame.paste(element_img, (x, y), element_img)
                
                # Add the currently fading-in element
                if active_elements and element_idx < element_count:
                    # Last element in the active list is fading in
                    elem_id = active_elements[-1]
                    elem = self.elements[elem_id]
                    x, y, w, h = elem.bbox
                    
                    # Calculate fade progress
                    if fade_frames > 0:
                        fade_progress = min(transition_frame / fade_frames, 1.0)
                    else:
                        fade_progress = 1.0
                    
                    # Crop the element from the full image
                    element_img = self.full_image.crop((x, y, x + w, y + h))
                    
                    # Apply fade effect by adjusting alpha
                    if fade_progress < 1.0:
                        # Create a mask with the desired alpha
                        alpha = int(fade_progress * 255)
                        mask = Image.new('L', element_img.size, alpha)
                        
                        # Apply mask
                        element_img.putalpha(mask)
                    
                    # Paste onto the frame with transparency
                    frame.paste(element_img, (x, y), element_img)
                
                # Save the frame
                frame_path = os.path.join(
                    self.config.output_folder, 
                    f"frame_{frame_count:04d}.png"
                )
                
                # Convert to RGB for compatibility
                frame_rgb = Image.new("RGB", frame.size, self.config.background_color)
                frame_rgb.paste(frame, (0, 0), frame)
                
                frame_rgb.save(frame_path, quality=95, optimize=True)
                frame_count += 1
                
                # Progress update every 10 frames
                if frame_count % 10 == 0:
                    logger.info(f"Progress: {frame_count} frames generated...")
        
        logger.info(f"Generated {frame_count} frames in {self.config.output_folder}")
    
    def create_video(self) -> None:
        """Create video from animation frames using ffmpeg"""
        # Check if frames exist
        if not os.path.exists(self.config.output_folder):
            raise FileNotFoundError(f"Output folder not found: {self.config.output_folder}")
        
        frame_pattern = os.path.join(self.config.output_folder, "frame_%04d.png")
        
        # Combine frames into video using ffmpeg
        logger.info("Creating video with ffmpeg...")
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-framerate', str(self.config.fps),
            '-i', frame_pattern,
            '-c:v', 'libx264',
            '-preset', 'slow',
            '-crf', '18',
            '-pix_fmt', 'yuv420p',
            self.config.output_video
        ]
        
        try:
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            logger.info(f"Animation saved to {self.config.output_video}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise RuntimeError("Failed to create video with FFmpeg")

def create_mermaid_animation(mermaid_code: str, output_prefix: str = "diagram", config: Optional[AnimationConfig] = None):
    """Create an animated video from Mermaid code"""
    # Initialize configuration
    if not config:
        config = AnimationConfig()
    
    # Initialize animator
    animator = MermaidSliceAnimator(config)
    
    # Step 1: Render Mermaid diagram to SVG and PNG
    svg_path, png_path = animator.render_mermaid(mermaid_code, output_prefix)
    
    # Step 2: Parse SVG to extract elements
    animator.parse_svg_elements(svg_path)
    
    # Step 3: Load the full rendered image
    animator.load_full_image(png_path)
    
    # Step 4: Create animation frames
    animator.create_animation_frames()
    
    # Step 5: Compile frames into video
    animator.create_video()
    
    logger.info(f"Animation created successfully: {config.output_video}")

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description='Create animated videos from Mermaid diagrams')
    parser.add_argument('input_file', help='Input Mermaid (.mmd) file path')
    parser.add_argument('-o', '--output', default='animation.mp4', help='Output video file path')
    parser.add_argument('--fps', type=int, default=30, help='Frames per second')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between elements (seconds)')
    parser.add_argument('--fade', type=float, default=0.3, help='Fade-in duration for elements (seconds)')
    
    args = parser.parse_args()
    
    # Read input file
    try:
        with open(args.input_file, 'r') as f:
            mermaid_code = f.read()
    except FileNotFoundError:
        logger.error(f"File not found: {args.input_file}")
        return 1
    except Exception as e:
        logger.error(f"Error reading input file: {str(e)}")
        return 1
    
    # Create animation config
    config = AnimationConfig(
        fps=args.fps,
        frame_delay=args.delay,
        fade_duration=args.fade,
        output_video=args.output
    )
    
    # Generate animation
    try:
        create_mermaid_animation(mermaid_code, "diagram", config)
        return 0
    except Exception as e:
        logger.error(f"Error creating animation: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())