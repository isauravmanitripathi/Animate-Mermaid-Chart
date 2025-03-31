#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script to extract individual visual components (nodes, labels, paths)
from a Mermaid-generated SVG file (specifically tested with flowchart-v2 and stateDiagram types)
and save each component as a separate PNG image, sorted top-to-bottom.

Requires: pip install lxml cairosvg
"""

try:
    from lxml import etree as ET # Use lxml for robust XPath support
except ImportError:
    print("\nError: The 'lxml' library is required but not found.")
    print("Please install it using: pip install lxml")
    import sys
    sys.exit(1)

import cairosvg
import os
import re
import copy
import sys

# --- Configuration ---
# You can set defaults here, but the script will prompt for input
DEFAULT_OUTPUT_DIR = 'svg_components'

# --- Helper Function to Extract Y-Coordinate for Sorting ---
def get_sort_key(element, namespaces):
    """
    Estimates the primary Y-coordinate for sorting based on transform or path data.
    Uses lxml's element structure.
    """
    y = float('inf') # Default to bottom (sorts last)

    # Priority 1: transform="translate(x, y)" on the element itself
    transform = element.get('transform')
    if transform:
        # Regex to find translate(x, y), handling optional spaces and scientific notation
        match = re.search(r'translate\(\s*([\d\.\-e]+)\s*,\s*([\d\.\-e]+)\s*\)', transform)
        if match:
            try:
                # Group 2 is the Y coordinate in translate(x, y)
                return float(match.group(2))
            except (ValueError, IndexError):
                pass # Ignore if parsing fails, continue searching

    # Priority 2: If it's a group, check transform on an inner standard label group
    # Covers cases like <g class="edgeLabel"><g class="label" transform="translate(...)">
    if element.tag == ET.QName(namespaces['svg'], 'g'): # Check if it's an SVG 'g' element
        # Use lxml's xpath for robust searching within the current element
        # Looks for immediate child 'g' with class 'label' and a transform
        label_groups = element.xpath('./svg:g[contains(@class, "label") and @transform]', namespaces=namespaces)
        if label_groups: # Check if list is not empty
             label_group = label_groups[0] # Take the first one if found
             transform = label_group.get('transform')
             if transform:
                 match = re.search(r'translate\(\s*([\d\.\-e]+)\s*,\s*([\d\.\-e]+)\s*\)', transform)
                 if match:
                     try:
                         # Add label's offset Y to parent group's offset Y (if parent has one)
                         parent_y = 0
                         parent_transform = element.get('transform')
                         if parent_transform:
                             parent_match = re.search(r'translate\(\s*[\d\.\-e]+\s*,\s*([\d\.\-e]+)\s*\)', parent_transform)
                             if parent_match:
                                 try: parent_y = float(parent_match.group(2)) # Group 2 is Y
                                 except (ValueError, IndexError): pass

                         # Return combined Y (parent group + label group)
                         return parent_y + float(match.group(2)) # Group 2 is Y
                     except (ValueError, IndexError):
                         pass # Fall through if label transform invalid

    # Priority 3: For paths, use Y from the first 'M x,y' (absolute MoveTo) in 'd' attribute
    # This is a heuristic, might not be perfect for all paths.
    if element.tag == ET.QName(namespaces['svg'], 'path'): # Check if it's an SVG 'path'
        d_attr = element.get('d')
        if d_attr:
            # Find the first absolute 'M' command's Y coordinate
            # Format: M <x>,<y> or M <x> <y>
            match = re.search(r'M\s*[\d\.\-e]+\s*[,]?\s*([\d\.\-e]+)', d_attr)
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, IndexError):
                    pass # Ignore if parsing fails

    # Fallback 1: Try direct 'y' attribute (common on <rect>, <text>, <circle cy>)
    y_attr = element.get('y') or element.get('cy') # Also check circle center y
    if y_attr:
        try: return float(y_attr)
        except ValueError: pass

    # Fallback 2: Find the highest 'y' or 'cy' attribute among descendants
    # This helps if the main element has no position but children do.
    # Uses more robust XPath to find any descendant with 'y' or 'cy'.
    descendants_with_y = element.xpath(".//*[@y or @cy]", namespaces=namespaces)
    min_y_descendant = float('inf')
    found_descendant_y = False
    for desc in descendants_with_y:
         y_val_str = desc.get('y') or desc.get('cy')
         if y_val_str:
             try:
                 y_val = float(y_val_str)
                 # Heuristic: Consider transform of the descendant's parent relative to the component root 'element'
                 # This is getting complex; a simpler approach is often sufficient. Let's just use the direct y value for now.
                 min_y_descendant = min(min_y_descendant, y_val)
                 found_descendant_y = True
             except ValueError: continue # Skip if not a valid number
    if found_descendant_y:
        return min_y_descendant


    # If absolutely no Y coordinate found, log a warning and place it last
    elem_id = element.get('id', 'N/A')
    elem_class = element.get('class', 'N/A')
    print(f"Warning: Could not determine reliable Y-sort-key for element tag='{element.xpath('local-name()')}' id='{elem_id}' class='{elem_class}'. Placing last.")
    return y # Return infinity to sort last


# --- Main Extraction Function ---
def extract_and_save_components(svg_path, output_dir):
    """
    Parses the SVG, identifies components, sorts them, and renders each to a PNG file.
    """
    if not os.path.isfile(svg_path):
        print(f"Error: Input SVG file not found: {svg_path}")
        return False # Indicate failure

    # Create output directory if it doesn't exist
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        print(f"Error creating output directory '{output_dir}': {e}")
        return False # Indicate failure

    try:
        # Define the primary SVG namespace (usually 'svg')
        # lxml typically handles namespaces well, but explicit definition is good practice
        namespaces = {'svg': 'http://www.w3.org/2000/svg'}

        # Parse the SVG file using lxml
        # remove_blank_text can help simplify the tree slightly
        parser = ET.XMLParser(remove_blank_text=True, recover=True) # Added recover=True for potentially malformed SVGs
        try:
            tree = ET.parse(svg_path, parser)
        except ET.XMLSyntaxError as e:
            print(f"Error: Failed to parse SVG file '{svg_path}'. It might be invalid XML.")
            print(f"Parser reported: {e}")
            return False # Indicate failure

        root = tree.getroot()

        # --- Get essential attributes from the original SVG root ---
        original_id = root.get('id')
        original_viewBox = root.get('viewBox')
        original_width = root.get('width')
        original_height = root.get('height')

        # Attempt to find style block(s) using xpath, case-insensitive tag
        original_styles = root.xpath('//svg:style', namespaces=namespaces)
        style_copies = [copy.deepcopy(style) for style in original_styles] if original_styles else []


        # --- Validate essential attributes ---
        if not original_viewBox:
            print("Error: Original SVG is missing the 'viewBox' attribute.")
            print("Cannot determine the canvas dimensions for extracted components.")
            return False # Indicate failure
        if not original_id:
            print("Warning: Original SVG root is missing the 'id' attribute.")
            print("This might cause issues with internal references (like arrowheads). Using a default ID.")
            original_id = "extracted-svg-component" # Assign a default

        # --- Identify potential components using lxml's XPath ---
        print("Finding components using XPath selectors...")

        # Selector for Nodes (covers start, end, basic shapes, states)
        node_selector = './/svg:g[contains(@class, "node")]'
        nodes = root.xpath(node_selector, namespaces=namespaces)
        print(f" - Found {len(nodes)} node groups ('{node_selector}')")

        # Selector for Edge Labels (text associated with arrows)
        edge_label_selector = './/svg:g[contains(@class, "edgeLabel")]'
        edge_labels = root.xpath(edge_label_selector, namespaces=namespaces)
        print(f" - Found {len(edge_labels)} edge label groups ('{edge_label_selector}')")

        # Selector for Edge Paths (the arrow lines) - Adjust class based on SVG type
        # For flowcharts: 'flowchart-link'; For state diagrams: 'transition'
        # Let's try to find either:
        path_selector_flow = './/svg:path[contains(@class, "flowchart-link")]'
        path_selector_state = './/svg:path[contains(@class, "transition")]'
        edge_paths_flow = root.xpath(path_selector_flow, namespaces=namespaces)
        edge_paths_state = root.xpath(path_selector_state, namespaces=namespaces)
        edge_paths = edge_paths_flow + edge_paths_state # Combine results
        print(f" - Found {len(edge_paths_flow)} flowchart edge paths ('{path_selector_flow}')")
        print(f" - Found {len(edge_paths_state)} state diagram edge paths ('{path_selector_state}')")
        print(f"   Total edge paths found: {len(edge_paths)}")

        # Selector for Cluster boxes/labels (optional, can be complex)
        # cluster_selector = './/svg:g[contains(@class, "cluster")]'
        # clusters = root.xpath(cluster_selector, namespaces=namespaces)
        # print(f" - Found {len(clusters)} cluster groups ('{cluster_selector}')")

        # Combine all identified elements
        # Add 'clusters' to this list if you uncomment and use the cluster selector
        all_potential_elements = nodes + edge_labels + edge_paths

        if not all_potential_elements:
            print("\nWarning: No components were found matching the defined selectors.")
            print("Please check the class names used in your specific SVG file and adjust")
            print("the XPath selectors in the script if necessary.")
            return True # Completed, but found nothing

        # --- Prepare components for sorting ---
        components_to_sort = []
        print("\nCalculating sort keys (Y-coordinates) for components...")
        for i, elem in enumerate(all_potential_elements):
            sort_y = get_sort_key(elem, namespaces)
            # Store tuple: (sort_key_Y, original_index, element_object)
            # Original index ensures stable sorting if Y coordinates are identical
            components_to_sort.append((sort_y, i, elem))

        # Sort components primarily by Y-coordinate, secondarily by their original order
        components_to_sort.sort(key=lambda item: (item[0], item[1]))
        print(f"Sorting {len(components_to_sort)} components completed.")

        # --- Extract <defs> section ---
        # Crucial for elements like arrow markers
        defs_elements = root.xpath('//svg:defs', namespaces=namespaces)
        defs_copy = copy.deepcopy(defs_elements[0]) if defs_elements else None
        if defs_copy is None:
             print("Warning: No <defs> section found in the original SVG.")
             print("         Elements like arrowheads might not render correctly in components.")


        # --- Process and Render each component ---
        print(f"\nRendering {len(components_to_sort)} components to PNG files in '{output_dir}'...")
        success_count = 0
        fail_count = 0
        for i, (sort_y, orig_index, element) in enumerate(components_to_sort):
            component_num = i + 1
            elem_id = element.get('id', f'elem_{orig_index}') # Get element ID for logging/debugging
            elem_tag = element.xpath('local-name()') # Get local tag name (without namespace)

            try:
                # --- Create a new SVG root for the individual component ---
                # Define the namespace map for lxml element creation
                # Include the default SVG namespace and any others found in the original root
                nsmap = {None: namespaces['svg']} # Default namespace
                if hasattr(root, 'nsmap'): # Check if nsmap attribute exists (lxml specific)
                    for prefix, uri in root.nsmap.items():
                        if prefix: # Only add explicitly defined prefixes (like 'xlink')
                            nsmap[prefix] = uri

                # Create the <svg> element with the correct namespace
                new_svg = ET.Element(ET.QName(namespaces['svg'], 'svg'), nsmap=nsmap)

                # Set essential attributes from the original SVG
                new_svg.set('version', '1.1')
                new_svg.set('viewBox', original_viewBox)
                new_svg.set('id', original_id) # Use original ID for internal references to work

                # Copy width and height if they were present on the original root
                if original_width: new_svg.set('width', original_width)
                if original_height: new_svg.set('height', original_height)
                # Add a background color for visibility if desired (optional)
                # new_svg.set('style', 'background-color: white;')


                # --- Add styles and definitions ---
                # Add copies of original style blocks
                for style_copy in style_copies:
                    new_svg.append(copy.deepcopy(style_copy))

                # Add copy of definitions (critical for markers, etc.)
                if defs_copy is not None:
                    new_svg.append(copy.deepcopy(defs_copy))

                # --- Add the component element ---
                # Deep copy the actual component element to avoid modifying the original tree
                element_copy = copy.deepcopy(element)
                new_svg.append(element_copy)

                # --- Convert the new SVG structure to bytes ---
                # Use lxml's tostring; encoding='utf-8' is standard for cairosvg
                # xml_declaration=True includes <?xml ...?> header
                # pretty_print=False is slightly more compact for processing
                svg_bytes = ET.tostring(new_svg, encoding='utf-8', xml_declaration=True, pretty_print=False)

                # --- Define output filename ---
                output_filename = os.path.join(output_dir, f"component-{component_num:03d}.png") # Pad number for sorting

                # --- Render using cairosvg ---
                cairosvg.svg2png(
                    bytestring=svg_bytes,
                    write_to=output_filename,
                    # Optional parameters for cairosvg:
                    # background_color="rgba(255, 255, 255, 0.8)" # e.g., semi-transparent white background
                    # scale=2.0 # Render at 2x resolution
                    # dpi=192 # Alternative way to set resolution
                )
                success_count += 1
                # Simple progress indicator
                print(f"\r - Saved: {output_filename} [{component_num}/{len(components_to_sort)}]", end="")


            except Exception as e:
                fail_count += 1
                print(f"\n--- Error processing component {component_num} ---")
                print(f"  Element Tag: <{elem_tag}>")
                print(f"  Element ID: {elem_id}")
                print(f"  Assigned Sort Y: {sort_y}")
                print(f"  Output File Attempted: {output_filename}")
                print(f"  Error Details: {e}")
                # For deeper debugging, you might want to save the temporary SVG bytes that failed:
                # try:
                #     fail_svg_filename = os.path.join(output_dir, f"component-{component_num:03d}_FAILED.svg")
                #     with open(fail_svg_filename, "wb") as f_err:
                #         f_err.write(svg_bytes)
                #     print(f"  Saved failing SVG content to: {fail_svg_filename}")
                # except Exception as dump_e:
                #     print(f"  (Could not save failing SVG: {dump_e})")

        print(f"\n\nRendering finished. {success_count} succeeded, {fail_count} failed.")
        return True # Indicate successful completion (even if some components failed)

    except ET.ParseError as e:
        # Catch XML parsing errors specifically
        print(f"\nError: Failed to parse the SVG file '{svg_path}'.")
        print(f"It might contain invalid XML syntax.")
        print(f"Parser reported: {e}")
        return False
    except Exception as e:
        # Catch any other unexpected errors during processing
        print(f"\nAn unexpected error occurred during the extraction process:")
        import traceback
        print("-" * 60)
        traceback.print_exc(file=sys.stdout)
        print("-" * 60)
        return False


# --- Get User Input ---
def get_user_input():
    """Prompts the user for the input SVG file path and output directory."""
    print("SVG Component Extraction Tool")
    print("============================")
    print("Extracts nodes, labels, and arrows from a Mermaid SVG into separate PNGs.")
    print("Requires 'lxml' and 'cairosvg' (`pip install lxml cairosvg`).\n")

    while True:
        svg_path = input("Enter the path to your Mermaid SVG file: ")
        if not svg_path:
            print("Input path cannot be empty.")
            continue
        # Basic check if file exists and has .svg extension
        if os.path.isfile(svg_path) and svg_path.lower().endswith('.svg'):
            break
        elif not os.path.exists(svg_path):
            print(f"Error: File not found at '{svg_path}'. Please check the path.")
        elif not svg_path.lower().endswith('.svg'):
             print("Error: File does not appear to be an SVG file (must end with .svg).")
        else: # Should ideally not happen if isfile check works
             print("Invalid input. Please enter a valid path to an SVG file.")

    # Prompt for output directory, using a default if none provided
    output_dir_prompt = input(f"Enter the output directory name [{DEFAULT_OUTPUT_DIR}]: ")
    output_dir = output_dir_prompt.strip() if output_dir_prompt.strip() else DEFAULT_OUTPUT_DIR

    print() # Add a newline for cleaner separation before processing starts
    return svg_path, output_dir

# --- Main Execution Block ---
if __name__ == "__main__":
    # Ensure lxml is available before proceeding
    try:
        from lxml import etree
    except ImportError:
        print("\nFatal Error: The 'lxml' library is required but not found.")
        print("Please install it using: pip install lxml")
        sys.exit(1) # Exit if dependency is missing

    # Get input from user
    input_svg_file, output_folder_name = get_user_input()

    # Run the main extraction process
    print(f"Starting SVG component extraction for: '{input_svg_file}'")
    print(f"Output will be saved in: '{output_folder_name}'")
    print("-" * 60)

    success = extract_and_save_components(input_svg_file, output_folder_name)

    print("-" * 60)
    if success:
        print(f"Extraction process completed. Please check the '{output_folder_name}' directory.")
    else:
        print("Extraction process failed due to errors.")

    sys.exit(0 if success else 1) # Exit with 0 on success, 1 on failure