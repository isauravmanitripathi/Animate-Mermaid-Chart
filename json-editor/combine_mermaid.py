#!/usr/bin/env python3
"""
Mermaid Additions Combiner

This script combines all the mermaid diagram additions from a processed JSON file
into a single .mmd file with proper order and structure.

Usage:
    python combine_mermaid.py input_json_file.json [output_mmd_file.mmd]

If no output file is specified, the script will create one based on the input filename.
"""

import json
import os
import sys
import re
from datetime import datetime

def extract_header_style(mermaid_additions):
    """Extract header and style definitions from mermaid code."""
    header = []
    style_lines = []
    
    lines = mermaid_additions.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('graph ') or stripped.startswith('flowchart '):
            header.append(line)
        elif stripped.startswith('classDef '):
            style_lines.append(line)
    
    return header, style_lines

def combine_mermaid_additions(json_data):
    """Combine all mermaid additions from the JSON data."""
    all_header_lines = []
    all_style_lines = []
    all_content_lines = []
    
    # Process each chapter
    for chapter in json_data:
        chapter_name = chapter.get("chapter_name", "Unknown Chapter")
        section_name = chapter.get("section_name", "")
        
        # Add chapter heading as a comment
        chapter_comment = f"\n%% Chapter: {chapter_name}"
        if section_name:
            chapter_comment += f" - {section_name}"
        all_content_lines.append(chapter_comment)
        
        # Process each section's mermaid additions
        for section in chapter.get("mermaid_test", []):
            # Find the mermaid additions field (format: mermaid_additions_N)
            additions_key = None
            for key in section:
                if key.startswith("mermaid_additions_"):
                    additions_key = key
                    break
            
            if not additions_key:
                # If we can't find mermaid_additions, look for complete_mermaid or mermaid_code
                for key in section:
                    if key.startswith("complete_mermaid_") or key.startswith("mermaid_code_"):
                        additions_key = key
                        break
            
            if not additions_key:
                print(f"Warning: No mermaid code found in section")
                continue
                
            mermaid_code = section[additions_key]
            
            # Skip if it's an error message
            if isinstance(mermaid_code, str) and mermaid_code.startswith("Error:"):
                print(f"Warning: Skipping section with error: {mermaid_code}")
                continue
                
            # Extract header and style if they exist in this section
            header, styles = extract_header_style(mermaid_code)
            
            # Add any new header lines
            for line in header:
                if line not in all_header_lines:
                    all_header_lines.append(line)
            
            # Add any new style lines
            for line in styles:
                if line not in all_style_lines:
                    all_style_lines.append(line)
            
            # Add content lines (excluding header and style)
            content_lines = []
            # Add section number as a comment
            section_num = additions_key.split("_")[-1]
            content_lines.append(f"\n%% Section {section_num}")
            
            for line in mermaid_code.split('\n'):
                stripped = line.strip()
                if (not stripped.startswith('graph ') and 
                    not stripped.startswith('flowchart ') and 
                    not stripped.startswith('classDef ')):
                    if stripped:  # Only add non-empty lines
                        content_lines.append(line)
            
            all_content_lines.extend(content_lines)
    
    # Combine everything in the right order
    combined_lines = []
    
    # Add header (only take the first one)
    if all_header_lines:
        combined_lines.append(all_header_lines[0])
    else:
        combined_lines.append("graph TD")
    
    # Add all style definitions
    combined_lines.extend(all_style_lines)
    
    # Add a spacer
    combined_lines.append("")
    
    # Add all content
    combined_lines.extend(all_content_lines)
    
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
        
        # Combine all mermaid additions
        combined_mermaid = combine_mermaid_additions(data)
        
        # Write the combined mermaid to the output file
        with open(output_file, 'w') as f:
            f.write(combined_mermaid)
        
        print(f"Combined Mermaid diagram saved to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()