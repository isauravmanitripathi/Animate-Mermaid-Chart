#!/usr/bin/env python3
"""
Simple Mermaid Element Extractor - Renders individual Mermaid elements one by one.
This approach renders each node/edge individually for isolation.
"""

import os
import sys
import subprocess
import tempfile
import argparse
import logging
import re

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
            node_png = os.path.join(output_dir, f"node_{node_id}.png")
            
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
            edge_png = os.path.join(output_dir, f"edge_{from_node}_to_{to_node}.png")
            
            if render_mermaid_to_png(edge_diagram, edge_png):
                logger.info(f"Extracted edge {from_node} -> {to_node} to {edge_png}")
                edge_count += 1
    
    # Also extract step-by-step versions
    step_dir = os.path.join(output_dir, "steps")
    os.makedirs(step_dir, exist_ok=True)
    
    # Start with just the header
    current_diagram = header
    step_png = os.path.join(step_dir, f"step_00.png")
    render_mermaid_to_png(current_diagram, step_png)
    
    # Add one line at a time
    for i, line in enumerate(elements['lines']):
        current_diagram += f"\n{line}"
        step_png = os.path.join(step_dir, f"step_{i+1:02d}.png")
        
        if render_mermaid_to_png(current_diagram, step_png):
            logger.info(f"Created step {i+1} diagram with line: {line.strip()}")
    
    return {
        'nodes': node_count,
        'edges': edge_count,
        'steps': len(elements['lines']) + 1
    }

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Extract individual elements from a Mermaid diagram'
    )
    parser.add_argument('input_file', help='Input Mermaid (.mmd) file path')
    parser.add_argument('-o', '--output-dir', default='mermaid_elements',
                        help='Output directory for extracted elements')
    
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
    
    # Extract elements
    result = extract_individual_elements(mermaid_code, args.output_dir)
    
    if result['nodes'] > 0 or result['edges'] > 0:
        logger.info(f"Successfully extracted {result['nodes']} nodes and {result['edges']} edges")
        logger.info(f"Created {result['steps']} step-by-step diagrams")
        return 0
    else:
        logger.error("No elements extracted.")
        return 1

if __name__ == "__main__":
    sys.exit(main())