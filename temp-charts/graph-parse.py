# -*- coding: utf-8 -*-
"""
Mermaid Graph Line-by-Line Parser and Animator v1.0

Parses a Mermaid graph/flowchart and creates animation frames
by adding exactly one line at a time from the original file.
"""

import re
import os
import sys
import traceback

class MermaidGraphLineParser:
    def __init__(self):
        """Initializes the parser for simple line-by-line parsing."""
        self.lines = []  # All lines from the file
        self.non_empty_lines = []  # Non-empty, non-comment-only lines
        
    def parse_file(self, filepath):
        """Reads a Mermaid file and store its lines."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.parse_content(content)
        except FileNotFoundError:
            print(f"Error: Input file not found: '{filepath}'")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file '{filepath}': {e}")
            traceback.print_exc()
            sys.exit(1)

    def parse_content(self, content):
        """Parses content by splitting into lines."""
        self.lines = content.strip().split('\n')
        
        # Store non-empty and non-comment-only lines
        self.non_empty_lines = []
        for line in self.lines:
            line_strip = line.strip()
            if line_strip and not line_strip.startswith('%%'):
                self.non_empty_lines.append(line)
        
        return {
            'line_count': len(self.lines),
            'non_empty_line_count': len(self.non_empty_lines)
        }

    def generate_animation_sequence(self, output_dir):
        """Generates animation frames by adding one line at a time."""
        # --- Setup output directory ---
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: '{output_dir}'")
        else:
            print(f"Clearing existing files in '{output_dir}'...")
            files_cleared = 0
            for file in os.listdir(output_dir):
                if file.endswith('.mmd') or file.lower() == "readme.md":
                    try:
                        os.remove(os.path.join(output_dir, file))
                        files_cleared += 1
                    except OSError as e:
                        print(f"  Warn: Could not remove {file}: {e}")
            print(f"  Cleared {files_cleared} files.")
        
        # First frame is just the graph/flowchart declaration (first line)
        if not self.lines:
            print("Error: No lines found to process.")
            return 0
        
        # Generate frames, adding one line at a time
        frames = []
        
        # Process each line
        current_frame_lines = []
        for i, line in enumerate(self.lines):
            line_strip = line.strip()
            
            # Add the line to current frame
            current_frame_lines.append(line)
            
            # Skip creating new frames for empty lines and comment-only lines
            # (except for the very first frame)
            if (not line_strip or line_strip.startswith('%%')) and i > 0:
                continue
            
            # Create a new frame with current lines
            frames.append('\n'.join(current_frame_lines))
        
        # --- Write Output Files ---
        num_frames = len(frames)
        print(f"\nGenerating {num_frames} frame files...")
        
        for i, frame_content in enumerate(frames):
            frame_num = i + 1
            filename = f"image_{frame_num}.mmd"
            filepath = os.path.join(output_dir, filename)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(frame_content)
            except IOError as e:
                print(f"  Error writing file {filepath}: {e}")
        
        # Generate README.md with all frames
        readme_path = os.path.join(output_dir, "README.md")
        print(f"Generating README.md at {readme_path}...")
        
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"# Mermaid Graph Animation\n\n")
                f.write(f"Generated {num_frames} frames.\n\n")
                
                for i, frame_content in enumerate(frames):
                    frame_num = i + 1
                    f.write(f"## Frame {frame_num}\n\n```mermaid\n{frame_content}\n```\n\n")
            
            print("  README.md generated successfully.")
        except IOError as e:
            print(f"  Error writing README.md: {e}")
        
        print(f"\nGenerated {num_frames} animation frames in '{output_dir}'")
        return num_frames


# --- Main execution block ---
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print(f"\nUsage: python {os.path.basename(__file__)} <input_mermaid_file> [--output-dir <output_directory>]")
        print("\nParses Mermaid Graph/Flowchart Diagrams and generates animation frames line by line.")
        print("\nArguments:")
        print("  <input_mermaid_file>   Path to the input .mmd file (should start with graph or flowchart).")
        print("  --output-dir <dir>     Optional. Directory to save frames and README.md.")
        print("                         Defaults to 'graph_animation_frames'.")
        sys.exit(0)
    
    input_file = sys.argv[1]
    output_dir = "graph_animation_frames"  # Default directory
    
    if "--output-dir" in sys.argv:
        try:
            idx = sys.argv.index("--output-dir") + 1
            if idx < len(sys.argv):
                output_dir = sys.argv[idx]
            else:
                print("Error: --output-dir requires path.")
                sys.exit(1)
        except ValueError:
            print("Error parsing arguments.")
            sys.exit(1)
    
    if not os.path.isfile(input_file):
        print(f"Error: Input file not found: '{input_file}'")
        sys.exit(1)
    
    parser = MermaidGraphLineParser()
    
    try:
        print(f"Parsing Mermaid graph file: '{input_file}'...")
        parsed_data = parser.parse_file(input_file)
        
        print("Parsing complete.")
        print(f"  Total lines: {parsed_data['line_count']}")
        print(f"  Non-empty, non-comment lines: {parsed_data['non_empty_line_count']}")
        
        print(f"\nGenerating animation sequence in directory: '{output_dir}'...")
        frames_generated = parser.generate_animation_sequence(output_dir)
        
    except Exception as e:
        print(f"\n--- An error occurred ---")
        print(f"Error: {type(e).__name__}: {e}")
        print("\n--- Traceback ---")
        traceback.print_exc()
        print("-----------------")
        sys.exit(1)
    
    print("\nScript finished successfully.")