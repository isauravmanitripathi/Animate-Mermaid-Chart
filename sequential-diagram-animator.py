#!/usr/bin/env python3
"""
Sequential Diagram Animator - Creates an animation with one element per frame
"""

import os
import sys
import subprocess
import tempfile
import argparse
import logging
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def render_mermaid_elements(mermaid_file, output_dir):
    """Render each element in the Mermaid diagram individually"""
    # Read the Mermaid file
    with open(mermaid_file, 'r') as f:
        mermaid_code = f.read()
    
    # Split the code into lines
    lines = mermaid_code.strip().split('\n')
    
    # Find the header (flowchart/graph directive)
    header = None
    content_lines = []
    
    for line in lines:
        if line.strip().startswith(('flowchart', 'graph')):
            header = line
        elif line.strip():
            content_lines.append(line)
    
    if not header:
        header = "flowchart TD"  # Default if no header found
    
    # Create output directories
    elements_dir = os.path.join(output_dir, "elements")
    frames_dir = os.path.join(output_dir, "frames")
    
    os.makedirs(elements_dir, exist_ok=True)
    os.makedirs(frames_dir, exist_ok=True)
    
    # Render each line as a separate diagram
    for i, line in enumerate(content_lines):
        # Create a temporary file for this element
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as temp_file:
            temp_file_path = temp_file.name
            # Write header and just this one line
            temp_file.write(f"{header}\n{line}")
        
        try:
            # Set output path for this element
            element_png = os.path.join(elements_dir, f"element_{i+1:02d}.png")
            
            # Render using mermaid-cli
            cmd = [
                'mmdc',                       # mermaid-cli
                '-i', temp_file_path,         # input file
                '-o', element_png,            # output file
                '-t', 'neutral',              # theme
                '-b', 'transparent',          # transparent background
                '-w', '1920',                 # width
                '-H', '1080'                  # height
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Rendered element {i+1}: {line.strip()} to {element_png}")
        
        except Exception as e:
            logger.error(f"Error rendering element {i+1}: {str(e)}")
        
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    return {
        'elements_count': len(content_lines),
        'elements_dir': elements_dir,
        'frames_dir': frames_dir
    }

def create_frames(elements_dir, frames_dir, fps=30, duration=1.0):
    """Create animation frames with each element on a white background"""
    # List all element files
    element_files = sorted([f for f in os.listdir(elements_dir) if f.startswith("element_") and f.endswith(".png")])
    
    if not element_files:
        logger.error("No element files found")
        return 0
    
    # Create a white background
    background = Image.new('RGBA', (1920, 1080), (255, 255, 255, 255))
    
    # Calculate frames per element
    frames_per_element = int(fps * duration)
    frame_count = 0
    
    # For each element
    for i, element_file in enumerate(element_files):
        element_path = os.path.join(elements_dir, element_file)
        
        try:
            # Open the element image
            element_img = Image.open(element_path).convert('RGBA')
            
            # Create a new background for this element
            frame = background.copy()
            
            # Paste the element onto the background
            frame.paste(element_img, (0, 0), element_img)
            
            # Convert to RGB for compatibility
            frame_rgb = Image.new('RGB', frame.size, (255, 255, 255))
            frame_rgb.paste(frame, (0, 0), frame)
            
            # Save multiple frames for this element (for duration)
            for j in range(frames_per_element):
                frame_path = os.path.join(frames_dir, f"frame_{frame_count:04d}.png")
                frame_rgb.save(frame_path)
                frame_count += 1
                
            logger.info(f"Created {frames_per_element} frames for element {i+1}")
            
        except Exception as e:
            logger.error(f"Error creating frames for element {i+1}: {str(e)}")
    
    return frame_count

def create_video(frames_dir, output_file, fps=30):
    """Create a video from the animation frames"""
    try:
        # Check if frames exist
        frame_pattern = os.path.join(frames_dir, "frame_%04d.png")
        
        # Use ffmpeg to create video
        cmd = [
            'ffmpeg',
            '-y',                       # Overwrite output file
            '-framerate', str(fps),     # Frames per second
            '-i', frame_pattern,        # Input pattern
            '-c:v', 'libx264',          # Codec
            '-pix_fmt', 'yuv420p',      # Pixel format
            '-profile:v', 'high',       # Profile
            '-crf', '18',               # Quality (0-51, lower is better)
            '-preset', 'slow',          # Encoding preset
            output_file
        ]
        
        subprocess.run(cmd, check=True)
        logger.info(f"Created video: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error creating video: {str(e)}")
        return False

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Create an animation with one diagram element per frame'
    )
    parser.add_argument('input_file', help='Input Mermaid (.mmd) file path')
    parser.add_argument('-o', '--output', default='diagram_animation.mp4',
                       help='Output video file path')
    parser.add_argument('--fps', type=int, default=30,
                       help='Frames per second')
    parser.add_argument('--duration', type=float, default=1.0,
                       help='Duration to show each element (seconds)')
    parser.add_argument('--temp-dir', default='temp_animation',
                       help='Temporary directory for intermediate files')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.temp_dir, exist_ok=True)
    
    try:
        # Step 1: Render individual elements
        logger.info("Rendering individual diagram elements...")
        result = render_mermaid_elements(args.input_file, args.temp_dir)
        
        if result['elements_count'] == 0:
            logger.error("No elements were rendered")
            return 1
        
        # Step 2: Create animation frames
        logger.info("Creating animation frames...")
        frame_count = create_frames(
            result['elements_dir'],
            result['frames_dir'],
            fps=args.fps,
            duration=args.duration
        )
        
        if frame_count == 0:
            logger.error("No frames were created")
            return 1
        
        # Step 3: Create video
        logger.info("Creating video...")
        if create_video(result['frames_dir'], args.output, fps=args.fps):
            logger.info(f"Animation created successfully: {args.output}")
            return 0
        else:
            logger.error("Failed to create video")
            return 1
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())