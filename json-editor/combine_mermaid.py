#!/usr/bin/env python3
"""
Mermaid Diagram Combiner

This script combines all the standalone mermaid diagrams from a processed JSON file
into a single .mmd file with proper ordering and structure.

Usage:
    python combine_mermaid.py input_json_file.json [output_mmd_file.mmd]

If no output file is specified, the script will create one based on the input filename.
"""

import json
import os
import sys
import re
from datetime import datetime

def extract_header_style_and_content(mermaid_code):
    """Extract header, style definitions, and content from mermaid code."""
    header = []
    style_lines = []
    content_lines = []
    
    lines = mermaid_code.split('\n')
    
    # Track whether we've seen the header yet
    header_found = False
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            continue
        
        # Capture header (graph TD or flowchart)
        if stripped.startswith('graph ') or stripped.startswith('flowchart '):
            header.append(line)
            header_found = True
            continue
        
        # Capture style definitions
        if stripped.startswith('classDef '):
            style_lines.append(line)
            continue
        
        # If we've seen the header, add everything else to content
        if header_found:
            # Skip comment lines that might be describing the diagram structure
            if stripped.startswith('%%') and any(term in stripped.lower() for term in 
                                              ['structure', 'pattern', 'follow', 'rule']):
                continue
            
            # Remove parentheses from node labels
            if '[' in line and ']' in line:
                # Remove parentheses
                line = re.sub(r'\(.*?\)', '', line)
                
                # Handle node identifiers with spaces in node definitions
                def fix_node_identifier(match):
                    # Remove spaces from node identifier
                    node_id = match.group(1).replace(' ', '')
                    node_label = match.group(2)
                    return f"{node_id}[{node_label}]"
                
                # Fix node definitions with spaces
                line = re.sub(r'(\w+\s+\w+)\[([^\]]+)\]', fix_node_identifier, line)
            
            # Handle node identifiers with spaces in connections
            def fix_connection_identifier(match):
                # Remove spaces from node identifier
                node_id = match.group(1).replace(' ', '')
                rest_of_line = match.group(2)
                return f"{node_id}{rest_of_line}"
            
            # Fix connections with spaced identifiers
            line = re.sub(r'(\w+\s+\w+)(\s*-->|\s*--o|\s*\.\.\.)(?=\s*)', fix_connection_identifier, line)
            line = re.sub(r'(-->|--o|\.\.\.)\s*(\w+\s+\w+)(?=\s*\|)', 
                          lambda m: f"{m.group(1)} {m.group(2).replace(' ', '')}", line)
            
            content_lines.append(line)
    
    return header, style_lines, content_lines

def combine_mermaid_diagrams(json_data):
    """Combine all mermaid diagrams from the JSON data."""
    all_headers = []
    all_style_lines = []
    all_content_sections = []
    
    # Process each chapter
    for chapter in json_data:
        chapter_name = chapter.get("chapter_name", "Unknown Chapter")
        section_name = chapter.get("section_name", "")
        
        # Add chapter heading as a comment
        chapter_comment = f"\n%% Chapter: {chapter_name}"
        if section_name:
            chapter_comment += f" - {section_name}"
        all_content_sections.append(chapter_comment)
        
        # Process each section's mermaid diagram
        for section in chapter.get("mermaid_test", []):
            # Find the mermaid diagram field (format could be mermaid_diagram_N, complete_mermaid_N, or mermaid_code_N)
            diagram_key = None
            for key in section:
                if key.startswith("mermaid_diagram_") or key.startswith("complete_mermaid_") or key.startswith("mermaid_code_"):
                    diagram_key = key
                    break
            
            # If still not found, try the legacy format with mermaid_additions
            if not diagram_key:
                for key in section:
                    if key.startswith("mermaid_additions_"):
                        diagram_key = key
                        break
            
            if not diagram_key:
                print(f"Warning: No mermaid code found in section")
                continue
                
            mermaid_code = section[diagram_key]
            
            # Skip if it's an error message
            if isinstance(mermaid_code, str) and mermaid_code.startswith("Error:"):
                print(f"Warning: Skipping section with error: {mermaid_code}")
                continue
                
            # Extract header, style, and content
            header, styles, content = extract_header_style_and_content(mermaid_code)
            
            # Add any new header (only collect unique headers)
            for h in header:
                if h not in all_headers:
                    all_headers.append(h)
            
            # Add any new style lines (only collect unique styles)
            for s in styles:
                if s not in all_style_lines:
                    all_style_lines.append(s)
            
            # Add section number as a comment
            section_num = diagram_key.split("_")[-1]
            section_content = [f"\n%% Section {section_num}"]
            section_content.extend(content)
            
            all_content_sections.append("\n".join(section_content))
    
    # Combine everything in the right order
    combined_lines = []
    
    # Add header (only take the first one)
    if all_headers:
        combined_lines.append(all_headers[0])
    else:
        # Default header if none found
        combined_lines.append("graph TD")
    
    # Add all style definitions
    combined_lines.extend(all_style_lines)
    
    # Add a spacer
    combined_lines.append("")
    
    # Add all content sections
    combined_lines.append("\n".join(all_content_sections))
    
    return '\n'.join(combined_lines)

def main():
    # Check if input file is provided
    if len(sys.argv) < 2:
        print("Error: Input JSON file is required.")
        print(f"Usage: python {os.path.basename(__file__)} input_json_file.json [output_mmd_file.mmd]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # Determine output file name
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        base_filename = os.path.splitext(os.path.basename(input_file))[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"{base_filename}_combined_{timestamp}.mmd"
    
    print(f"Reading processed JSON from: {input_file}")
    
    try:
        # Read the input JSON
        with open(input_file, 'r') as f:
            data = json.load(f)
        
        # Combine all mermaid diagrams
        combined_mermaid = combine_mermaid_diagrams(data)
        
        # Write the combined mermaid to the output file
        with open(output_file, 'w') as f:
            f.write(combined_mermaid)
        
        print(f"Combined Mermaid diagram saved to: {output_file}")
        print(f"You can visualize this file using Mermaid Live Editor or any Mermaid-compatible tool.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()