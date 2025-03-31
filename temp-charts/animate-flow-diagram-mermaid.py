import os
import argparse

def generate_mermaid_sequence(input_file, output_dir):
    """
    Generate a sequence of Mermaid diagrams by adding one line at a time.
    Handles subgraphs as complete blocks.
    Ignores comment lines starting with %%.
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    else:
        # Clear existing .mmd files to avoid confusion with previous runs
        for file in os.listdir(output_dir):
            if file.endswith('.mmd'):
                os.remove(os.path.join(output_dir, file))
    
    # Read the input file
    with open(input_file, 'r') as f:
        lines = [line.rstrip() for line in f.readlines()]
    
    # Extract the first line (flowchart declaration)
    declaration = lines[0]
    remaining_lines = lines[1:]
    
    # Initialize with just the flowchart declaration
    current_content = [declaration]
    
    # Sequence counter
    seq_num = 1
    
    # Save the first step
    with open(os.path.join(output_dir, f"image_{seq_num}.mmd"), 'w') as f:
        f.write(declaration)
    
    # Process the remaining lines
    i = 0
    while i < len(remaining_lines):
        line = remaining_lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
            
        # Skip comment lines
        if line.startswith('%%'):
            i += 1
            continue
        
        # Handle subgraph blocks
        if line.startswith('subgraph'):
            subgraph_lines = [line]
            subgraph_depth = 1
            j = i + 1
            
            # Collect all lines in this subgraph block, handling nested subgraphs
            while j < len(remaining_lines) and subgraph_depth > 0:
                subline = remaining_lines[j].strip()
                if subline.startswith('subgraph'):
                    subgraph_depth += 1
                elif subline == 'end':
                    subgraph_depth -= 1
                
                subgraph_lines.append(remaining_lines[j])
                j += 1
            
            # Add the entire subgraph as one step
            current_content.extend(subgraph_lines)
            seq_num += 1
            
            with open(os.path.join(output_dir, f"image_{seq_num}.mmd"), 'w') as f:
                f.write('\n'.join(current_content))
                
            i = j  # Move past the entire subgraph
            
        else:
            # Add a regular line
            current_content.append(line)
            seq_num += 1
            
            with open(os.path.join(output_dir, f"image_{seq_num}.mmd"), 'w') as f:
                f.write('\n'.join(current_content))
                
            i += 1
    
    # Generate README with all diagrams
    create_readme(output_dir)
    
    return seq_num

def create_readme(output_dir):
    """Create a README.md with all generated diagrams"""
    readme_path = os.path.join(output_dir, "README.md")
    
    with open(readme_path, 'w') as f:
        f.write("# Mermaid Diagram Sequence\n\n")
        f.write("This sequence of diagrams was automatically generated to show incremental building of the diagram.\n\n")
        
        # Get all image files and sort them
        image_files = sorted(
            [file for file in os.listdir(output_dir) if file.startswith('image_') and file.endswith('.mmd')],
            key=lambda x: int(x.split('_')[1].split('.')[0])
        )
        
        for image_file in image_files:
            number = image_file.split('_')[1].split('.')[0]
            f.write(f"## Diagram {number}\n\n")
            f.write(f"```mermaid\n")
            
            with open(os.path.join(output_dir, image_file), 'r') as d:
                f.write(d.read())
                
            f.write(f"\n```\n\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create a sequence of incremental Mermaid diagrams')
    parser.add_argument('input_file', help='Input Mermaid diagram file (.mmd)')
    parser.add_argument('--output-dir', '-o', default='sequence_output', help='Output directory for sequence files')
    
    args = parser.parse_args()
    
    num_steps = generate_mermaid_sequence(args.input_file, args.output_dir)
    print(f"Generated {num_steps} diagrams in {args.output_dir}")
    print(f"Created README with all diagrams: {os.path.join(args.output_dir, 'README.md')}")