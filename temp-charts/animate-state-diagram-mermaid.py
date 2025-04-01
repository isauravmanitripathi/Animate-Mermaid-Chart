#!/usr/bin/env python3
import os
import argparse
import re


def parse_mermaid_file(file_path):
    """Read and parse the Mermaid state diagram file."""
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Split the file into lines
    lines = content.split('\n')
    
    # Remove any empty lines
    lines = [line for line in lines if line.strip()]
    
    return lines


def is_empty_state_block(content):
    """Check if content contains an empty state block with various syntax patterns."""
    # Match standard state blocks: state X {}
    if re.search(r'state\s+\w+\s*\{\s*\}', content):
        return True
    
    # Match quoted state blocks: state "X" as Y {}
    if re.search(r'state\s+"[^"]+"\s+as\s+\w+\s*\{\s*\}', content):
        return True
    
    # Match just quoted state blocks: state "X" {}
    if re.search(r'state\s+"[^"]+"\s*\{\s*\}', content):
        return True
    
    return False


def process_diagram(lines):
    """
    Process the diagram lines and generate valid incremental diagrams.
    Returns a list of valid diagrams.
    """
    diagrams = []
    current_lines = []
    state_block_started = False
    skip_next = False
    
    for i, line in enumerate(lines):
        # Skip this line if flagged
        if skip_next:
            skip_next = False
            continue
        
        # Check if this line starts a state block
        if "state" in line and "{" in line:
            state_block_started = True
            
            # Check if this is an empty state block (ends with {}),
            # or if the next line is just a closing brace
            if line.strip().endswith("{}"):
                # Skip empty state block
                continue
            elif i + 1 < len(lines) and lines[i + 1].strip() == "}":
                # Skip both this line and the next
                skip_next = True
                continue
        
        # Add the current line
        current_lines.append(line)
        
        # Reset state block flag if needed
        if state_block_started and "}" in line:
            state_block_started = False
        
        # Create a balanced version
        temp_lines = current_lines.copy()
        open_braces = 0
        close_braces = 0
        
        for l in temp_lines:
            open_braces += l.count('{')
            close_braces += l.count('}')
        
        # Add temporary closing braces if needed
        if open_braces > close_braces:
            for _ in range(open_braces - close_braces):
                temp_lines.append('}')
        
        # Make sure we don't have empty state blocks
        content = '\n'.join(temp_lines)
        if is_empty_state_block(content):
            continue
        
        # Add to valid diagrams
        diagrams.append('\n'.join(temp_lines))
    
    return diagrams


def generate_files(diagrams, output_dir):
    """Save each diagram to a numbered file."""
    os.makedirs(output_dir, exist_ok=True)
    
    for i, diagram in enumerate(diagrams, 1):
        file_path = os.path.join(output_dir, f"image_{i}.mmd")
        with open(file_path, 'w') as file:
            file.write(diagram)
    
    return len(diagrams)


def main():
    """Main function to parse arguments and process the Mermaid file."""
    parser = argparse.ArgumentParser(description='Animate a Mermaid state diagram by creating sequential files.')
    parser.add_argument('file_path', help='Path to the Mermaid state diagram file (.mmd)')
    parser.add_argument('--output-dir', default='flowchart_sequence', help='Directory to save the sequential files')
    
    args = parser.parse_args()
    
    # Verify the input file exists
    if not os.path.isfile(args.file_path):
        print(f"Error: File {args.file_path} not found.")
        return
    
    # Parse the Mermaid file
    print(f"Parsing Mermaid file: {args.file_path}")
    lines = parse_mermaid_file(args.file_path)
    
    # Process the diagram
    print("Processing diagram...")
    diagrams = process_diagram(lines)
    
    # Generate files
    print(f"Generating sequential files in: {args.output_dir}")
    file_count = generate_files(diagrams, args.output_dir)
    
    print(f"Generated {file_count} sequential diagram files in {args.output_dir}")
    print(f"Files are named image_1.mmd through image_{file_count}.mmd")


if __name__ == "__main__":
    main()