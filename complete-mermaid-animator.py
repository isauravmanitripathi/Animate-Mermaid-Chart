#!/usr/bin/env python3
"""
Complete Mermaid Animator - Extracts elements, creates step-by-step diagrams,
and generates a video with each step centered on a white background.
"""

import os
import sys
import subprocess
import tempfile
import argparse
import logging
import re
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def render_mermaid_to_png(mermaid_code, output_png, width=1920, height=1080):
    """Render Mermaid code directly to PNG using mermaid-cli"""
    # Create a temporary file for the Mermaid code
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as temp_file:
        temp_mmd_path = temp_file.name
        temp_file.write(mermaid_code)
    
    try:
        # Run mermaid-cli to render PNG
        cmd = [
            'mmdc',                    # mermaid-cli command
            '-i', temp_mmd_path,       # input file
            '-o', output_png,          # output file
            '-t', 'neutral',           # theme
            '-b', 'transparent',       # background
            '-w', str(width),          # width
            '-H', str(height)          # height
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"PNG rendered to {output_png}")
        return True
    except Exception as e:
        logger.error(f"Error rendering PNG: {str(e)}")
        return False
    finally:
        # Clean up temporary file
        if os.path.exists(temp_mmd_path):
            os.unlink(temp_mmd_path)

def parse_mermaid_elements(mermaid_code):
    """Parse Mermaid code to extract individual elements"""
    # Split the mermaid code into lines
    lines = mermaid_code.strip().split('\n')
    
    # Find the header line
    header_line = None
    content_lines = []
    
    for line in lines:
        if line.strip().startswith(('flowchart', 'graph')):
            header_line = line
        elif line.strip():  # Only add non-empty lines
            content_lines.append(line)
    
    if not header_line:
        header_line = "flowchart TD"  # Default if not found
    
    # Parse connection lines to identify nodes and edges
    nodes = {}
    edges = []
    
    for line in content_lines:
        if '-->' in line:
            match = re.match(r'([A-Za-z0-9_-]+)(?:\[.*\]|\(.*\)|{.*})?\s*-->\s*(?:\|(.*)\|)?\s*([A-Za-z0-9_-]+)(?:\[.*\]|\(.*\)|{.*})?', line)
            if match:
                from_node, edge_label, to_node = match.groups()
                
                # Store nodes and edge
                if from_node not in nodes:
                    nodes[from_node] = True
                if to_node not in nodes:
                    nodes[to_node] = True
                
                edges.append({
                    'from': from_node,
                    'to': to_node,
                    'label': edge_label.strip() if edge_label else ""
                })
    
    return {
        'header': header_line,
        'nodes': list(nodes.keys()),
        'edges': edges,
        'lines': content_lines
    }

def extract_individual_elements(mermaid_code, output_dir):
    """Extract individual elements from Mermaid code by rendering each separately"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Create subdirectories
    steps_dir = os.path.join(output_dir, "steps")
    nodes_dir = os.path.join(output_dir, "nodes")
    edges_dir = os.path.join(output_dir, "edges")
    
    os.makedirs(steps_dir, exist_ok=True)
    os.makedirs(nodes_dir, exist_ok=True)
    os.makedirs(edges_dir, exist_ok=True)
    
    # Parse the mermaid code to identify elements
    elements = parse_mermaid_elements(mermaid_code)
    header = elements['header']
    
    # First, render the full diagram for reference
    full_diagram_png = os.path.join(output_dir, "full_diagram.png")
    render_mermaid_to_png(mermaid_code, full_diagram_png)
    
    # Extract nodes
    node_count = 0
    for node_id in elements['nodes']:
        # Create a minimal diagram with just this node
        # We need to look through all content lines to find the complete node definition
        node_definition = None
        for line in elements['lines']:
            if re.search(fr'\b{node_id}\b(?:\[.*\]|\(.*\)|{{.*}})', line):
                # Extract just the node part from the line
                if '-->' in line:
                    # It's in a connection line, extract just the node part
                    parts = line.split('-->')
                    if re.search(fr'\b{node_id}\b', parts[0]):
                        node_definition = parts[0].strip()
                    elif re.search(fr'\b{node_id}\b', parts[1]):
                        node_definition = parts[1].strip()
                        # Remove any edge label
                        if '|' in node_definition:
                            node_definition = re.sub(r'\|.*\|', '', node_definition).strip()
                else:
                    # It's a standalone node definition
                    node_definition = line.strip()
                
                # Once we find it, stop looking
                if node_definition:
                    break
        
        if node_definition:
            # Create a minimal diagram with just this node
            node_diagram = f"{header}\n{node_definition}"
            node_png = os.path.join(nodes_dir, f"node_{node_id}.png")
            
            if render_mermaid_to_png(node_diagram, node_png):
                logger.info(f"Extracted node {node_id} to {node_png}")
                node_count += 1
    
    # Extract edges
    edge_count = 0
    for edge in elements['edges']:
        from_node = edge['from']
        to_node = edge['to']
        
        # Find the complete edge definition
        edge_definition = None
        for line in elements['lines']:
            if '-->' in line and re.search(fr'\b{from_node}\b', line) and re.search(fr'\b{to_node}\b', line):
                edge_definition = line.strip()
                break
        
        if edge_definition:
            # Create a minimal diagram with just this edge
            edge_diagram = f"{header}\n{edge_definition}"
            edge_png = os.path.join(edges_dir, f"edge_{from_node}_to_{to_node}.png")
            
            if render_mermaid_to_png(edge_diagram, edge_png):
                logger.info(f"Extracted edge {from_node} -> {to_node} to {edge_png}")
                edge_count += 1
    
    # Create step-by-step versions
    # Start with just the header
    current_diagram = header
    step_png = os.path.join(steps_dir, f"step_00.png")
    render_mermaid_to_png(current_diagram, step_png)
    
    # Add one line at a time
    for i, line in enumerate(elements['lines']):
        current_diagram += f"\n{line}"
        step_png = os.path.join(steps_dir, f"step_{i+1:02d}.png")
        
        if render_mermaid_to_png(current_diagram, step_png):
            logger.info(f"Created step {i+1} diagram with line: {line.strip()}")
    
    return {
        'nodes': node_count,
        'edges': edge_count,
        'steps': len(elements['lines']) + 1,
        'steps_dir': steps_dir
    }

def create_animation_from_steps(steps_dir, output_video, fps=30, duration=1.0):
    """Create an animation from existing step images"""
    # Find all step files in the directory
    step_files = sorted([f for f in os.listdir(steps_dir) if f.startswith("step_") and f.endswith(".png")])
    
    if not step_files:
        logger.error(f"No step files found in {steps_dir}")
        return False
    
    logger.info(f"Found {len(step_files)} step files")
    
    # Create a temp directory for frames
    frames_dir = os.path.join(os.path.dirname(steps_dir), "frames")
    os.makedirs(frames_dir, exist_ok=True)
    
    # Number of frames for each step
    frames_per_step = int(fps * duration)
    
    # Create a clean white background at 1080p
    background = Image.new('RGBA', (1920, 1080), (255, 255, 255, 255))
    
    # For each step, create frames
    frame_count = 0
    
    for i, step_file in enumerate(step_files):
        step_path = os.path.join(steps_dir, step_file)
        logger.info(f"Processing step {i}: {step_file}")
        
        try:
            # Open step image
            step_img = Image.open(step_path).convert('RGBA')
            
            # Calculate position to center the image
            pos_x = (background.width - step_img.width) // 2
            pos_y = (background.height - step_img.height) // 2
            
            # Start with a clean background
            frame = background.copy()
            
            # Paste step image onto background, centered
            frame.paste(step_img, (pos_x, pos_y), step_img)
            
            # Convert to RGB for compatibility
            frame_rgb = Image.new('RGB', frame.size, (255, 255, 255))
            frame_rgb.paste(frame, (0, 0), frame)
            
            # Create multiple frames for this step (for duration)
            for j in range(frames_per_step):
                frame_path = os.path.join(frames_dir, f"frame_{frame_count:04d}.png")
                frame_rgb.save(frame_path)
                frame_count += 1
                
            logger.info(f"Created {frames_per_step} frames for step {i}")
            
        except Exception as e:
            logger.error(f"Error processing step {i}: {str(e)}")
    
    if frame_count == 0:
        logger.error("No frames were created")
        return False
    
    # Create video from frames
    try:
        # Use ffmpeg to create video
        cmd = [
            'ffmpeg',
            '-y',                       # Overwrite output file
            '-framerate', str(fps),     # Frames per second
            '-i', os.path.join(frames_dir, "frame_%04d.png"),  # Input pattern
            '-c:v', 'libx264',          # Codec
            '-pix_fmt', 'yuv420p',      # Pixel format
            '-crf', '18',               # Quality (0-51, lower is better)
            '-preset', 'slow',          # Encoding preset
            output_video
        ]
        
        subprocess.run(cmd, check=True)
        logger.info(f"Created video: {output_video}")
        return True
    except Exception as e:
        logger.error(f"Error creating video: {str(e)}")
        return False

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Create an animated video from a Mermaid diagram'
    )
    parser.add_argument('input_file', help='Input Mermaid (.mmd) file path')
    parser.add_argument('-o', '--output', default='diagram_animation.mp4',
                       help='Output video file path')
    parser.add_argument('--fps', type=int, default=30,
                       help='Frames per second')
    parser.add_argument('--duration', type=float, default=1.0,
                       help='Duration to show each step (seconds)')
    parser.add_argument('--temp-dir', default='mermaid_elements',
                       help='Directory for intermediate files')
    
    args = parser.parse_args()
    
    try:
        # Read input file
        with open(args.input_file, 'r') as f:
            mermaid_code = f.read()
    except FileNotFoundError:
        logger.error(f"File not found: {args.input_file}")
        return 1
    except Exception as e:
        logger.error(f"Error reading input file: {str(e)}")
        return 1
    
    # Step 1: Extract elements and create step-by-step diagrams
    result = extract_individual_elements(mermaid_code, args.temp_dir)
    
    if result['steps'] <= 1:
        logger.error("Failed to create step-by-step diagrams")
        return 1
    
    logger.info(f"Successfully extracted {result['nodes']} nodes and {result['edges']} edges")
    logger.info(f"Created {result['steps']} step-by-step diagrams")
    
    # Step 2: Create animation from step images
    if create_animation_from_steps(
        result['steps_dir'],
        args.output,
        fps=args.fps,
        duration=args.duration
    ):
        logger.info(f"Animation created successfully: {args.output}")
        return 0
    else:
        logger.error("Failed to create animation")
        return 1

if __name__ == "__main__":
    sys.exit(main())