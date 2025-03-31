#!/usr/bin/env python3
"""
Mermaid Sequence Animator - Takes a folder of sequential Mermaid files (*.mmd),
renders them to images, and creates a video animation with customizable timing.
"""

import os
import sys
import argparse
import subprocess
import glob
import logging
import re
from pathlib import Path
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Create an animation from a sequence of Mermaid diagram files.'
    )
    parser.add_argument('input_folder', help='Folder containing sequential Mermaid (.mmd) files')
    parser.add_argument('-o', '--output', default='mermaid_animation.mp4',
                       help='Output video file path (default: mermaid_animation.mp4)')
    parser.add_argument('-t', '--total-time', type=float, default=10.0,
                       help='Total animation duration in seconds (default: 10.0)')
    parser.add_argument('-w', '--width', type=int, default=1920,
                       help='Canvas width in pixels (default: 1920)')
    parser.add_argument('-H', '--height', type=int, default=1080,
                       help='Canvas height in pixels (default: 1080)')
    parser.add_argument('--fps', type=int, default=30,
                       help='Frames per second (default: 30)')
    parser.add_argument('--theme', default='neutral',
                       help='Mermaid theme (default: neutral)')
    parser.add_argument('--file-pattern', default='image_*.mmd',
                       help='Pattern to match Mermaid files (default: image_*.mmd)')
    parser.add_argument('--bg-color', default='white',
                       help='Background color for final video (default: white)')
    parser.add_argument('--padding', type=int, default=50,
                       help='Padding around diagram (default: 50 pixels)')
    
    return parser.parse_args()

def find_mermaid_files(input_folder, file_pattern):
    """Find all Mermaid files in the input folder matching the pattern and sort them numerically."""
    # Get absolute path
    input_folder = os.path.abspath(input_folder)
    
    # Check if folder exists
    if not os.path.isdir(input_folder):
        logger.error(f"Input folder not found: {input_folder}")
        return []
    
    # Find all files matching the pattern
    search_pattern = os.path.join(input_folder, file_pattern)
    files = glob.glob(search_pattern)
    
    # Use natural sorting to handle image_1.mmd, image_2.mmd, ..., image_10.mmd
    def natural_sort_key(s):
        return [int(text) if text.isdigit() else text.lower() 
                for text in re.split(r'(\d+)', s)]
    
    sorted_files = sorted(files, key=natural_sort_key)
    
    logger.info(f"Found {len(sorted_files)} Mermaid files in {input_folder}")
    return sorted_files

def render_mermaid_to_image(mermaid_file, output_image, width, height, theme):
    """Render a Mermaid file to an image using mermaid-cli (mmdc) with transparent background."""
    try:
        cmd = [
            'mmdc',                    # mermaid-cli command
            '-i', mermaid_file,        # input file
            '-o', output_image,        # output file
            '-t', theme,               # theme
            '-b', 'transparent',       # transparent background
            '-w', str(width),          # width
            '-H', str(height)          # height
        ]
        
        logger.info(f"Rendering {os.path.basename(mermaid_file)} with transparent background...")
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error rendering {mermaid_file}: {e}")
        logger.error(f"Command output: {e.stdout.decode() if hasattr(e, 'stdout') else ''}")
        logger.error(f"Command error: {e.stderr.decode() if hasattr(e, 'stderr') else ''}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error rendering {mermaid_file}: {str(e)}")
        return False

def center_and_fit_image_on_canvas(input_image, output_image, canvas_width, canvas_height, bg_color, padding=50):
    """Center the input image on a canvas with specified background color, scaling down if necessary to fit."""
    try:
        # Open the input image with transparency
        img = Image.open(input_image).convert("RGBA")
        
        # Calculate maximum allowed dimensions with padding
        max_width = canvas_width - (2 * padding)
        max_height = canvas_height - (2 * padding)
        
        # Check if image needs scaling
        scale_factor = 1.0
        if img.width > max_width or img.height > max_height:
            # Calculate scale factor to fit within bounds
            width_ratio = max_width / img.width
            height_ratio = max_height / img.height
            scale_factor = min(width_ratio, height_ratio)
            
            # Calculate new dimensions
            new_width = int(img.width * scale_factor)
            new_height = int(img.height * scale_factor)
            
            logger.info(f"Scaling image from {img.width}x{img.height} to {new_width}x{new_height} (scale factor: {scale_factor:.2f})")
            
            # Resize the image
            img = img.resize((new_width, new_height), Image.LANCZOS)
        else:
            logger.info(f"Image fits within canvas at original size: {img.width}x{img.height}")
        
        # Create a new canvas with specified background color
        # Parse background color - can be name like 'white' or hex like '#FFFFFF'
        canvas = Image.new("RGBA", (canvas_width, canvas_height), bg_color)
        
        # Calculate position to center the image
        pos_x = (canvas_width - img.width) // 2
        pos_y = (canvas_height - img.height) // 2
        
        # Paste the image onto the canvas, using the alpha channel for transparency
        canvas.paste(img, (pos_x, pos_y), img)
        
        # Convert to RGB mode for better compatibility with video formats
        canvas_rgb = canvas.convert("RGB")
        canvas_rgb.save(output_image)
        
        logger.info(f"Centered image saved to {output_image} with background color: {bg_color}")
        return True
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return False

def create_video_from_images(images, output_video, fps, frame_duration):
    """Create a video from a list of images using ffmpeg."""
    try:
        # Create a temporary file list
        temp_list_file = "temp_file_list.txt"
        
        with open(temp_list_file, "w") as f:
            for img in images:
                # Calculate how many times to repeat each image to achieve desired duration
                repeat_count = max(1, int(frame_duration * fps))
                for _ in range(repeat_count):
                    f.write(f"file '{img}'\n")
                    f.write(f"duration {1/fps}\n")
            
            # Add the last image again (required by ffmpeg)
            if images:
                f.write(f"file '{images[-1]}'\n")
        
        # Run ffmpeg to create the video
        cmd = [
            'ffmpeg',
            '-y',                       # Overwrite output file
            '-f', 'concat',             # Format is concat
            '-safe', '0',               # Don't require safe filenames
            '-i', temp_list_file,       # Input file list
            '-vsync', 'vfr',            # Variable frame rate
            '-pix_fmt', 'yuv420p',      # Pixel format
            '-c:v', 'libx264',          # Codec
            output_video                # Output file
        ]
        
        logger.info("Creating video...")
        subprocess.run(cmd, check=True)
        
        # Clean up temporary file
        os.remove(temp_list_file)
        
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error creating video: {e}")
        logger.error(f"Command output: {e.stdout.decode() if hasattr(e, 'stdout') else 'None'}")
        logger.error(f"Command error: {e.stderr.decode() if hasattr(e, 'stderr') else 'None'}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating video: {str(e)}")
        return False

def main():
    """Main function."""
    args = parse_arguments()
    
    # Find all Mermaid files
    mermaid_files = find_mermaid_files(args.input_folder, args.file_pattern)
    
    if not mermaid_files:
        logger.error("No Mermaid files found. Exiting.")
        return 1
    
    # Create folders for intermediate files
    raw_images_folder = os.path.join(args.input_folder, "raw_images")
    final_images_folder = os.path.join(args.input_folder, "final_images")
    
    os.makedirs(raw_images_folder, exist_ok=True)
    os.makedirs(final_images_folder, exist_ok=True)
    
    # Render each Mermaid file to an image with transparent background
    raw_image_files = []
    for mermaid_file in mermaid_files:
        base_name = os.path.splitext(os.path.basename(mermaid_file))[0]
        output_image = os.path.join(raw_images_folder, f"{base_name}.png")
        
        if render_mermaid_to_image(mermaid_file, output_image, args.width, args.height, args.theme):
            raw_image_files.append(output_image)
        else:
            logger.warning(f"Failed to render {mermaid_file}, skipping...")
    
    if not raw_image_files:
        logger.error("No images were rendered successfully. Exiting.")
        return 1
    
    # Center and fit each image on a canvas with user-specified background color
    final_image_files = []
    for raw_image in raw_image_files:
        base_name = os.path.basename(raw_image)
        final_image = os.path.join(final_images_folder, base_name)
        
        if center_and_fit_image_on_canvas(raw_image, final_image, args.width, args.height, args.bg_color, args.padding):
            final_image_files.append(final_image)
        else:
            logger.warning(f"Failed to process {raw_image}, skipping...")
    
    if not final_image_files:
        logger.error("No images were processed successfully. Exiting.")
        return 1
    
    # Calculate frame duration based on total time and number of images
    frame_duration = args.total_time / len(final_image_files)
    logger.info(f"Each image will appear for {frame_duration:.2f} seconds")
    
    # Create video from images
    if create_video_from_images(final_image_files, args.output, args.fps, frame_duration):
        logger.info(f"Animation created successfully: {args.output}")
        logger.info(f"Total duration: {args.total_time:.2f} seconds with background color: {args.bg_color}")
        return 0
    else:
        logger.error("Failed to create animation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())