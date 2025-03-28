#!/usr/bin/env python3
"""
Mermaid Element Extractor - Takes a Mermaid diagram, renders it as SVG,
then extracts and saves each element as a separate image.
"""

import os
import sys
import subprocess
import tempfile
import argparse
import logging
import xml.etree.ElementTree as ET
import re
from PIL import Image, ImageOps
import io

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def render_mermaid_to_svg(mermaid_code, output_svg):
    """Render Mermaid code to SVG using mermaid-cli"""
    # Create a temporary file for the Mermaid code
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as temp_file:
        temp_mmd_path = temp_file.name
        temp_file.write(mermaid_code)
    
    try:
        # Run mermaid-cli to render SVG
        cmd = [
            'mmdc',                    # mermaid-cli command
            '-i', temp_mmd_path,       # input file
            '-o', output_svg,          # output file
            '-t', 'neutral',           # theme
            '-b', 'transparent'        # background
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"SVG rendered to {output_svg}")
        return True
    except Exception as e:
        logger.error(f"Error rendering SVG: {str(e)}")
        return False
    finally:
        # Clean up temporary file
        os.unlink(temp_mmd_path)

def render_mermaid_to_png(mermaid_code, output_png):
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
            '-w', '1920',              # width
            '-H', '1080'               # height
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"PNG rendered to {output_png}")
        return True
    except Exception as e:
        logger.error(f"Error rendering PNG: {str(e)}")
        return False
    finally:
        # Clean up temporary file
        os.unlink(temp_mmd_path)

def extract_elements_by_lines(mermaid_code, output_dir):
    """Extract elements by rendering incremental versions of the diagram"""
    os.makedirs(output_dir, exist_ok=True)
    
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
    
    # First, render and save the full diagram
    full_diagram_png = os.path.join(output_dir, "full_diagram.png")
    if not render_mermaid_to_png(mermaid_code, full_diagram_png):
        logger.error("Failed to render full diagram")
        return 0
    
    # Now render each element incrementally
    element_count = 0
    
    # Save diagram header as element 0 (empty diagram)
    element_png = os.path.join(output_dir, f"element_00.png")
    if not render_mermaid_to_png(header_line, element_png):
        logger.warning("Failed to render header element")
    else:
        element_count += 1
    
    # For each content line, add it to the diagram and render
    current_diagram = header_line
    for i, line in enumerate(content_lines):
        if not line.strip():
            continue  # Skip empty lines
            
        current_diagram += '\n' + line
        element_png = os.path.join(output_dir, f"element_{element_count:02d}.png")
        
        if render_mermaid_to_png(current_diagram, element_png):
            logger.info(f"Rendered element {element_count} with line: {line.strip()}")
            element_count += 1
        else:
            logger.warning(f"Failed to render element with line: {line.strip()}")
    
    return element_count

def extract_visual_diff(output_dir):
    """Extract visual differences between consecutive diagram renders"""
    # List all element files
    files = [f for f in os.listdir(output_dir) if f.startswith("element_") and f.endswith(".png")]
    files.sort()
    
    if len(files) < 2:
        logger.warning("Not enough element files for diff extraction")
        return 0
    
    diff_count = 0
    
    # For each pair of consecutive renders, extract the difference
    for i in range(1, len(files)):
        prev_file = os.path.join(output_dir, files[i-1])
        curr_file = os.path.join(output_dir, files[i])
        
        try:
            # Open images
            prev_img = Image.open(prev_file).convert('RGBA')
            curr_img = Image.open(curr_file).convert('RGBA')
            
            # Make sure images are the same size
            if prev_img.size != curr_img.size:
                logger.warning(f"Size mismatch between {files[i-1]} and {files[i]}")
                continue
            
            # Create a new transparent image for the diff
            diff_img = Image.new('RGBA', curr_img.size, (0, 0, 0, 0))
            
            # Copy the current image
            diff_pixels = curr_img.load()
            prev_pixels = prev_img.load()
            
            # Find the bounding box of the difference
            min_x, min_y = curr_img.size
            max_x, max_y = 0, 0
            
            # Scan for differences
            for y in range(curr_img.height):
                for x in range(curr_img.width):
                    curr_pixel = diff_pixels[x, y]
                    prev_pixel = prev_pixels[x, y]
                    
                    # If pixels differ and current pixel is not transparent
                    if curr_pixel != prev_pixel and curr_pixel[3] > 0:
                        min_x = min(min_x, x)
                        min_y = min(min_y, y)
                        max_x = max(max_x, x)
                        max_y = max(max_y, y)
            
            # Add padding
            padding = 10
            min_x = max(0, min_x - padding)
            min_y = max(0, min_y - padding)
            max_x = min(curr_img.width - 1, max_x + padding)
            max_y = min(curr_img.height - 1, max_y + padding)
            
            # If meaningful difference found
            if max_x > min_x and max_y > min_y:
                # Crop the difference
                diff_region = curr_img.crop((min_x, min_y, max_x, max_y))
                
                # Save the diff
                diff_file = os.path.join(output_dir, f"diff_{diff_count:02d}.png")
                diff_region.save(diff_file)
                logger.info(f"Saved diff {diff_count} to {diff_file}")
                diff_count += 1
        
        except Exception as e:
            logger.error(f"Error processing diff between {files[i-1]} and {files[i]}: {str(e)}")
    
    return diff_count

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Extract elements from a Mermaid diagram and save as separate images'
    )
    parser.add_argument('input_file', help='Input Mermaid (.mmd) file path')
    parser.add_argument(
        '-o', '--output-dir', 
        default='diagram_elements',
        help='Output directory for extracted elements'
    )
    
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
    
    # Extract elements by rendering incremental versions
    element_count = extract_elements_by_lines(mermaid_code, args.output_dir)
    
    if element_count > 0:
        logger.info(f"Successfully extracted {element_count} incremental elements")
        
        # Extract visual diffs
        diff_count = extract_visual_diff(args.output_dir)
        if diff_count > 0:
            logger.info(f"Successfully extracted {diff_count} visual differences")
        
        return 0
    else:
        logger.error("No elements extracted.")
        return 1

if __name__ == "__main__":
    sys.exit(main())