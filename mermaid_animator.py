#!/usr/bin/env python3
"""
Simple Mermaid Animator - Creates an animation from Mermaid diagrams
by progressively revealing the diagram content.
"""

import os
import sys
import subprocess
import shutil
import tempfile
import argparse
import logging
from PIL import Image, ImageDraw, ImageFont

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def render_mermaid_progressively(mermaid_code, output_dir, fps=30, 
                                delay=0.5, fade_duration=0.3):
    """
    Create a progressive animation by rendering partial Mermaid diagrams.
    
    This approach directly uses Mermaid CLI to render incrementally larger
    portions of the diagram, ensuring perfect rendering at each step.
    """
    # Create temp directory for frames
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Split the mermaid code into lines
    lines = mermaid_code.strip().split('\n')
    
    # Find the header line (contains flowchart TD, graph LR, etc.)
    header_line = None
    content_lines = []
    
    for line in lines:
        if line.strip().startswith(('flowchart', 'graph')):
            header_line = line
        else:
            content_lines.append(line)
    
    if not header_line:
        header_line = "flowchart TD"  # Default if not found
    
    # Calculate total frames
    frames_per_step = int(fps * delay)
    total_steps = len(content_lines)
    
    logger.info(f"Creating animation with {total_steps} steps...")
    
    frame_count = 0
    
    # For each step, render incrementally more of the diagram
    for step in range(total_steps + 1):  # +1 to show complete diagram at the end
        # Create the partial mermaid code
        if step == 0:
            # Just the header for first frame
            partial_code = header_line
        else:
            # Header plus first 'step' content lines
            partial_code = header_line + '\n' + '\n'.join(content_lines[:step])
        
        # Create a temporary file for this step's mermaid code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(partial_code)
        
        # Create output path for this step's image
        output_path = os.path.join(output_dir, f"step_{step:04d}.png")
        
        # Run mermaid-cli to render this step
        try:
            cmd = [
                'mmdc',
                '-i', temp_file_path,
                '-o', output_path,
                '-t', 'neutral',
                '-b', 'white'
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Rendered step {step}/{total_steps}")
            
            # If the file wasn't created or is empty, create a blank image
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                img = Image.new('RGB', (800, 600), 'white')
                img.save(output_path)
                logger.warning(f"Created blank image for step {step}")
            
            # Create multiple frames for this step (to control animation speed)
            img = Image.open(output_path)
            
            # For each frame in this step
            for frame in range(frames_per_step):
                frame_path = os.path.join(output_dir, f"frame_{frame_count:04d}.png")
                img.save(frame_path)
                frame_count += 1
            
        except Exception as e:
            logger.error(f"Error rendering step {step}: {str(e)}")
            # Create a blank image as fallback
            img = Image.new('RGB', (800, 600), 'white')
            img.save(output_path)
            
            # Create frames for this step
            for frame in range(frames_per_step):
                frame_path = os.path.join(output_dir, f"frame_{frame_count:04d}.png")
                img.save(frame_path)
                frame_count += 1
        
        # Clean up temporary file
        os.unlink(temp_file_path)
    
    logger.info(f"Created {frame_count} frames in {output_dir}")
    return frame_count

def create_video_from_frames(frames_dir, output_file, fps=30):
    """Create a video from the animation frames"""
    frame_pattern = os.path.join(frames_dir, "frame_%04d.png")
    
    # Use ffmpeg to create video
    try:
        cmd = [
            'ffmpeg',
            '-y',
            '-framerate', str(fps),
            '-i', frame_pattern,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            output_file
        ]
        
        subprocess.run(cmd, check=True)
        logger.info(f"Created video: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error creating video: {str(e)}")
        return False

def create_animation(mermaid_code, output_file, fps=30, delay=0.5, fade_duration=0.3):
    """Create a Mermaid diagram animation"""
    # Create temporary directory for frames
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Render progressive frames
        render_mermaid_progressively(
            mermaid_code, 
            temp_dir, 
            fps=fps, 
            delay=delay, 
            fade_duration=fade_duration
        )
        
        # Create video from frames
        create_video_from_frames(temp_dir, output_file, fps=fps)
        
        logger.info(f"Animation created successfully: {output_file}")
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir)

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description='Create animated Mermaid diagrams')
    parser.add_argument('input_file', help='Input Mermaid (.mmd) file path')
    parser.add_argument('-o', '--output', default='animation.mp4', help='Output video file path')
    parser.add_argument('--fps', type=int, default=30, help='Frames per second')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between steps (seconds)')
    parser.add_argument('--fade', type=float, default=0.3, help='Fade-in duration (seconds)')
    
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
    
    # Create animation
    try:
        create_animation(
            mermaid_code,
            args.output,
            fps=args.fps,
            delay=args.delay,
            fade_duration=args.fade
        )
        return 0
    except Exception as e:
        logger.error(f"Error creating animation: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())