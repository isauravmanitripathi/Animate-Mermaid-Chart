#!/usr/bin/env python3

import argparse
import re
import os
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

# --- Configuration ---
# Try to find tools in PATH, user can override with args
MMDC_PATH = shutil.which("mmdc")
FFMPEG_PATH = shutil.which("ffmpeg")
IMAGEMAGICK_CONVERT_PATH = shutil.which("convert")
# --- End Configuration ---

def find_tool(tool_name, configured_path, arg_path):
    """Finds the path to an external tool, prioritizing command-line arg."""
    if arg_path:
        if shutil.which(arg_path):
            return arg_path
        else:
            print(f"Warning: Specified {tool_name} path '{arg_path}' not found or not executable.", file=sys.stderr)
            # Fall through to check configured/default path
    if configured_path and shutil.which(configured_path):
        return configured_path
    # If default configured path not found, try finding tool directly in PATH
    found_path = shutil.which(tool_name)
    if found_path:
        return found_path
    return None # Not found

# --- Updated Parser Function ---
def parse_mermaid_class_diagram(mermaid_code):
    """
    Parses a Mermaid class diagram string into its core components.
    Improved to handle notes and relationships more reliably.

    Args:
        mermaid_code: A string containing the Mermaid class diagram definition.

    Returns:
        A list of strings, where each string is a logically separate component
        (directive, class block, interface block, relationship, note, etc.),
        in the order they appear. Returns None if parsing fails fundamentally.
    """
    lines = mermaid_code.strip().splitlines()
    components = []
    in_block = False # Generic block flag (class, interface, etc.)
    current_block_lines = []
    # Pattern for Class/Interface start (can have { or not on the same line)
    block_start_pattern = re.compile(r"^\s*(class|interface)\s+\S+")
    # Pattern for Note 'left of', 'right of', 'over'
    note_pos_pattern = re.compile(r"^\s*note\s+(left of|right of|over)\s+\S+")
    # Pattern for Note 'for' syntax
    note_for_pattern = re.compile(r"^\s*note\s+for\s+\S+\s+\".*\"\s*$")
    # Pattern for Links
    link_pattern = re.compile(r"^\s*link\s+\S+\s+.*")
    # More robust relationship pattern:
    # Catches: NodeA "LabelA" Arrow "LabelB" NodeB : EndLabel
    # Allows for various arrow types and optional labels/cardinality
    relationship_pattern = re.compile(
        r"^\s*" +                   # Start anchor
        r"(\S+)" +                  # Start node/class name (non-whitespace)
        r"(?:\s+\".*?\")?" +        # Optional "quoted label" for start cardinality
        r"\s+" +                    # Separating space
        # Allow spaces around arrow components e.g. <| --
        r"(<\|?\s*--[xo]?\s*|--[xo]?\s*\|?>|\*--|o--|-->|--)" + # The arrow types
        r"\s+" +                    # Separating space
        r"(?:\".*?\")?" +           # Optional "quoted label" for end cardinality
        r"\s+" +                    # Separating space
        r"(\S+)" +                  # End node/class name (non-whitespace)
        r"(?:\s*:\s*.*)?" +         # Optional : label text at the end
        r"\s*$"                     # End anchor
    )

    if not lines or not lines[0].strip().lower().startswith("classdiagram"):
        print("Error: Input does not start with 'classDiagram'.", file=sys.stderr)
        return None

    # Keep the 'classDiagram' line but don't add to components list yet
    diagram_declaration = lines[0]

    for line_num, line in enumerate(lines[1:], start=1): # Process lines after 'classDiagram'
        stripped_line = line.strip()

        if not stripped_line:
            continue # Skip empty lines

        # Handle Comments (Skip/Ignore)
        if stripped_line.startswith("%%"):
            # Skip directive blocks too for simplicity now
            if stripped_line.startswith("%%{") and stripped_line.endswith("}%%"):
                pass # Skip single-line directive blocks
            elif stripped_line.startswith("%%{"):
                 # Multi-line directive block - Need state (ignoring for now)
                 print(f"Warning: Skipping multi-line directive block starting line {line_num+1}", file=sys.stderr)
                 pass
            else:
                 pass # Ignore simple comments
            continue

        # --- State Machine for Blocks (Class/Interface) ---
        if in_block:
            current_block_lines.append(line)
            if stripped_line == "}":
                components.append("\n".join(current_block_lines))
                in_block = False
                current_block_lines = []
            continue # Continue accumulating lines within the block

        # --- Identify Start of Blocks ---
        # Check if line starts a class/interface block AND is not already in one
        if block_start_pattern.match(stripped_line):
             if stripped_line.endswith("{"):
                 in_block = True
                 current_block_lines = [line]
             else: # Single-line definition or class without {}? Treat as single component.
                 components.append(line)
             continue # Move to next line after starting/adding a block def

        # --- Identify Standalone Components (Notes, Relationships, Links) ---
        # Check these only if NOT inside a block
        if note_for_pattern.match(stripped_line) or \
           note_pos_pattern.match(stripped_line):
            # print(f"DEBUG: Identified Note: {stripped_line}") # Keep commented out unless debugging
            components.append(line)
            continue
        elif relationship_pattern.match(stripped_line):
             # print(f"DEBUG: Identified Relationship: {stripped_line}") # Keep commented out unless debugging
             components.append(line)
             continue
        elif link_pattern.match(stripped_line):
             # print(f"DEBUG: Identified Link: {stripped_line}") # Keep commented out unless debugging
             components.append(line)
             continue

        # If we reach here and it's not blank, comment, or start of block,
        # and we are NOT in a block, it's likely unrecognized.
        print(f"Warning: Line {line_num+1} skipped (unrecognized syntax?): {line.strip()}", file=sys.stderr)

    if in_block:
        print("Warning: Reached end of input while still inside a block (missing '}')?", file=sys.stderr)
        # Add the incomplete block if desired
        # components.append("\n".join(current_block_lines))

    # Return the identified components
    return components

# --- Frame Generation Function (Unchanged) ---
def generate_mermaid_frames(components):
    """Generates a sequence of Mermaid diagram strings."""
    frames = []
    base = "classDiagram"
    current_diagram_parts = []

    for component in components:
        current_diagram_parts.append(component)
        # Indent components for readability
        indented_components = ["    " + part.replace("\n", "\n    ") for part in current_diagram_parts]
        frames.append(base + "\n" + "\n".join(indented_components))

    return frames

# --- Rendering and GIF Creation Function (Updated) ---
def render_frames_and_create_gif(frames, output_gif, mmdc_exec, gif_tool_exec, frame_rate, temp_dir_base, keep_temp=False):
    """Renders frames using mmdc and creates GIF using ffmpeg or convert."""
    temp_dir = tempfile.mkdtemp(prefix="mermaid_anim_", dir=temp_dir_base)
    print(f"Created temporary directory: {temp_dir}")
    frame_files = []
    success = False # Track overall success

    try:
        # 1. Render each frame to PNG
        for i, frame_code in enumerate(frames):
            frame_num_str = f"{i:03d}"
            mmd_path = os.path.join(temp_dir, f"frame_{frame_num_str}.mmd")
            png_path = os.path.join(temp_dir, f"frame_{frame_num_str}.png")
            frame_files.append(png_path)

            print(f"Rendering frame {i+1}/{len(frames)}...")
            with open(mmd_path, "w", encoding='utf-8') as f:
                f.write(frame_code)

            # Use theme 'neutral' (valid theme) and transparent background
            cmd = [
                mmdc_exec,
                "-i", mmd_path,
                "-o", png_path,
                "-t", "neutral",    # Use valid theme name
                "-b", "transparent", # Use transparent background
                # Add other mmdc options if needed, e.g., -w width -H height
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8')

            if result.returncode != 0:
                print(f"Error rendering frame {i+1}:", file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                # Decide whether to stop or continue
                return False # Stop on first error


        # 2. Combine PNGs into GIF
        print(f"\nCombining {len(frame_files)} frames into {output_gif}...")
        tool_name = Path(gif_tool_exec).name.lower()

        if "ffmpeg" in tool_name:
             # Using FFmpeg - Simplified command (less prone to internal errors)
            print("Creating GIF with FFmpeg (simplified command)...")
            cmd_gif = [
                gif_tool_exec,
                "-v", "warning",
                "-framerate", str(frame_rate),
                "-i", os.path.join(temp_dir, "frame_%03d.png"), # Input sequence
                # Consider adding -vf for padding if needed, but keep simple first
                # "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-loop", "0", # Loop indefinitely
                "-y", # Overwrite output without asking
                output_gif
            ]
            # Note: This simplified command won't clear transparent backgrounds well.
            # A more complex ffmpeg command *might* work with newer versions,
            # potentially involving palettegen/use and background setting, but
            # ImageMagick is often better for this specific transparency case.
            # Example of a potentially better (but maybe buggy) ffmpeg command:
            # cmd_gif = [
            #     gif_tool_exec, "-v", "warning", "-framerate", str(frame_rate),
            #     "-i", os.path.join(temp_dir, "frame_%03d.png"),
            #     "-filter_complex",
            #     # Set background, overlay frame, generate palette, use palette
            #     f"[0:v]fps={frame_rate},pad=width=ceil(iw/2)*2:height=ceil(ih/2)*2:x=-1:y=-1:color=white@1.0, "
            #     f"setpts=N/(FRAME_RATE*TB) [base]; "
            #     f"[base][0:v] overlay=shortest=1:x=0:y=0 [frames]; "
            #     f"[frames] split [s0][s1]; [s0] palettegen [p]; [s1][p] paletteuse",
            #     "-loop", "0", "-y", output_gif
            # ]
            result_gif = subprocess.run(cmd_gif, capture_output=True, text=True, check=False)

        elif "convert" in tool_name:
            # Using ImageMagick's convert - with background handling
            print("Creating GIF with ImageMagick (forcing background clear)...")
            cmd_gif = [
                gif_tool_exec,
                "-delay", str(int(100 / frame_rate)), # Delay in ticks (1/100 sec)
                "-loop", "0",                          # Loop indefinitely
                "-background", "white",                # Set background color
                "-dispose", "Background",              # Clear frame to background
                os.path.join(temp_dir, "frame_*.png"), # Input files (wildcard)
                output_gif
            ]
            result_gif = subprocess.run(cmd_gif, capture_output=True, text=True, check=False)
        else:
            print(f"Error: Unknown GIF tool '{gif_tool_exec}'. Use 'ffmpeg' or 'convert'.", file=sys.stderr)
            return False # Explicitly return False here

        if result_gif.returncode != 0:
            print(f"Error creating GIF with {tool_name}:", file=sys.stderr)
            print(result_gif.stderr, file=sys.stderr)
            success = False
        else:
            print(f"\nSuccessfully created GIF: {output_gif}")
            success = True # Set success only if GIF command worked

        return success # Return status

    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return False
    finally:
        # 3. Clean up temporary directory unless requested not to
        if not keep_temp and os.path.exists(temp_dir):
            print(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)
        elif keep_temp:
             print(f"Temporary directory kept at: {temp_dir}")


# --- Main Execution Logic (Updated with keep_temp flag) ---
def main():
    parser = argparse.ArgumentParser(description="Parse a Mermaid Class Diagram (.mmd) file and generate animation frames or a GIF.")
    parser.add_argument("input_file", help="Path to the input .mmd file.")
    parser.add_argument("-o", "--output", help="Optional: Path to save the output GIF file. If not provided, prints Mermaid code for each frame to console.")
    parser.add_argument("-r", "--frame-rate", type=float, default=1.0, help="Frames per second for the output GIF (default: 1.0).")
    parser.add_argument("--mmdc-path", help=f"Optional: Path to the 'mmdc' executable (default: tries '{MMDC_PATH}' or finds in PATH).")
    parser.add_argument("--gif-tool", choices=['ffmpeg', 'imagemagick'], default='ffmpeg' if FFMPEG_PATH else ('imagemagick' if IMAGEMAGICK_CONVERT_PATH else None), help="Tool to use for creating GIF ('ffmpeg' or 'imagemagick'). Tries ffmpeg first by default.")
    parser.add_argument("--gif-tool-path", help="Optional: Path to the GIF creation tool ('ffmpeg' or 'convert') executable.")
    parser.add_argument("--temp-dir", help="Optional: Directory to store temporary frame files (default: system temp).")
    parser.add_argument("--keep-temp", action='store_true', help="Optional: Keep the temporary directory containing frame images after execution for debugging.")


    args = parser.parse_args()

    # --- Validate Input File ---
    input_path = Path(args.input_file)
    if not input_path.is_file():
        print(f"Error: Input file not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    # --- Read Input ---
    print(f"Reading Mermaid code from: {args.input_file}")
    try:
        mermaid_code = input_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Parse ---
    print("Parsing Mermaid definition...")
    components = parse_mermaid_class_diagram(mermaid_code)
    if components is None:
        print("Parsing failed.", file=sys.stderr)
        sys.exit(1)
    if not components:
        print("Warning: No components (classes, relationships, notes, etc.) found after parsing.", file=sys.stderr)
        if not args.output:
             print("\n--- Frame 0 (Base) ---")
             print("classDiagram") # Print base diagram if nothing else
        sys.exit(0 if not args.output else 1)

    print(f"Found {len(components)} components.")

    # --- Generate Frames ---
    print("Generating animation frame definitions...")
    mermaid_frames = generate_mermaid_frames(components)
    print(f"Generated {len(mermaid_frames)} frames.")


    # --- Output ---
    if args.output:
        # --- Find Tools ---
        mmdc_exec = find_tool("mmdc", MMDC_PATH, args.mmdc_path)
        if not mmdc_exec:
            print("Error: Mermaid CLI ('mmdc') not found. Please install @mermaid-js/mermaid-cli or provide path using --mmdc-path.", file=sys.stderr)
            sys.exit(1)
        print(f"Using mmdc: {mmdc_exec}")

        gif_tool_choice = args.gif_tool
        gif_tool_exec = None
        # Determine default tool if not specified
        if not gif_tool_choice:
             if FFMPEG_PATH:
                 gif_tool_choice = 'ffmpeg'
             elif IMAGEMAGICK_CONVERT_PATH:
                 gif_tool_choice = 'imagemagick'
             else:
                 print("Error: No GIF creation tool ('ffmpeg' or 'imagemagick/convert') found in PATH.", file=sys.stderr)
                 sys.exit(1)
             print(f"Auto-selected GIF tool: {gif_tool_choice}")


        if gif_tool_choice == 'ffmpeg':
            gif_tool_exec = find_tool("ffmpeg", FFMPEG_PATH, args.gif_tool_path)
            if not gif_tool_exec:
                 print(f"Error: GIF tool 'ffmpeg' not found.", file=sys.stderr)
                 sys.exit(1)
        elif gif_tool_choice == 'imagemagick':
            # Look for 'convert' specifically for ImageMagick
            gif_tool_exec = find_tool("convert", IMAGEMAGICK_CONVERT_PATH, args.gif_tool_path)
            if not gif_tool_exec:
                 print(f"Error: ImageMagick's 'convert' tool not found.", file=sys.stderr)
                 sys.exit(1)

        if not gif_tool_exec:
             # This case should ideally not be reached due to checks above
             print(f"Error: Could not determine path for GIF tool '{gif_tool_choice}'.", file=sys.stderr)
             sys.exit(1)

        print(f"Using GIF tool ({gif_tool_choice}): {gif_tool_exec}")


        # --- Render and Create GIF ---
        success = render_frames_and_create_gif(
            mermaid_frames,
            args.output,
            mmdc_exec,
            gif_tool_exec,
            args.frame_rate,
            args.temp_dir, # Can be None, mkdtemp handles it
            args.keep_temp # Pass the flag
        )
        if not success:
            print("\nGIF creation failed.", file=sys.stderr)
            sys.exit(1)

    else:
        # Print frames to console
        print("\nPrinting Mermaid code for each frame to console:")
        # Also print the base frame
        print("\n--- Frame 0 (Base) ---")
        print("classDiagram")
        for i, frame in enumerate(mermaid_frames):
            print(f"\n--- Frame {i+1}/{len(mermaid_frames)} ---")
            print(frame)

if __name__ == "__main__":
    main()