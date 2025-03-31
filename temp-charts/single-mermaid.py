#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script to extract individual visual components (nodes, labels, paths)
from a Mermaid-generated SVG file (flowchart-v2, stateDiagram, entityRelationshipDiagram)
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
DEFAULT_OUTPUT_DIR = 'svg_components'

# --- Helper Function to Extract Y-Coordinate for Sorting ---
# [This function remains the same as the previous version - it worked well for sorting]
def get_sort_key(element, namespaces):
    """
    Estimates the primary Y-coordinate for sorting based on transform or path data.
    Uses lxml's element structure.
    """
    y = float('inf') # Default to bottom (sorts last)
    try: # Wrap in try-except to catch potential issues within this function
        # Priority 1: transform="translate(x, y)" on the element itself
        transform = element.get('transform')
        if transform:
            match = re.search(r'translate\(\s*([\d\.\-e]+)\s*,\s*([\d\.\-e]+)\s*\)', transform)
            if match:
                try: return float(match.group(2)) # Group 2 is Y
                except (ValueError, IndexError): pass

        # Priority 2: If it's a group, check transform on an inner standard label group
        if element.tag == ET.QName(namespaces['svg'], 'g'):
            label_groups = element.xpath('./svg:g[contains(@class, "label") and @transform]', namespaces=namespaces)
            if label_groups:
                 label_group = label_groups[0]
                 transform = label_group.get('transform')
                 if transform:
                     match = re.search(r'translate\(\s*([\d\.\-e]+)\s*,\s*([\d\.\-e]+)\s*\)', transform)
                     if match:
                         try:
                             parent_y = 0
                             parent_transform = element.get('transform')
                             if parent_transform:
                                 parent_match = re.search(r'translate\(\s*[\d\.\-e]+\s*,\s*([\d\.\-e]+)\s*\)', parent_transform)
                                 if parent_match:
                                     try: parent_y = float(parent_match.group(2))
                                     except (ValueError, IndexError): pass
                             return parent_y + float(match.group(2))
                         except (ValueError, IndexError): pass

        # Priority 3: For paths, use Y from the first 'M x,y' (absolute MoveTo) in 'd' attribute
        # Heuristic: May not be perfect for complex paths starting with relative moves.
        if element.tag == ET.QName(namespaces['svg'], 'path'):
            d_attr = element.get('d')
            if d_attr:
                match = re.search(r'M\s*[\d\.\-e]+\s*[,]?\s*([\d\.\-e]+)', d_attr) # Absolute M
                if match:
                    try: return float(match.group(1))
                    except (ValueError, IndexError): pass
                else: # If no absolute M, try first coordinate pair regardless of command
                    match = re.search(r'[A-Za-z]\s*([\d\.\-e]+)\s*[,]?\s*([\d\.\-e]+)', d_attr)
                    if match:
                         try: return float(match.group(2)) # Take Y coord
                         except (ValueError, IndexError): pass


        # Fallback 1: Try direct 'y' attribute or 'cy' (circle center)
        y_attr = element.get('y') or element.get('cy')
        if y_attr:
            try: return float(y_attr)
            except ValueError: pass

        # Fallback 2: Find the highest 'y' or 'cy' attribute among descendants
        descendants_with_y = element.xpath(".//*[@y or @cy]", namespaces=namespaces)
        min_y_descendant = float('inf')
        found_descendant_y = False
        for desc in descendants_with_y:
             y_val_str = desc.get('y') or desc.get('cy')
             if y_val_str:
                 try:
                     y_val = float(y_val_str)
                     min_y_descendant = min(min_y_descendant, y_val)
                     found_descendant_y = True
                 except ValueError: continue
        if found_descendant_y:
            return min_y_descendant

        # If absolutely no Y coordinate found, log warning and place last
        elem_id = element.get('id', 'N/A')
        elem_class = element.get('class', 'N/A')
        print(f"\nWarning: Could not determine reliable Y-sort-key for element tag='{element.xpath('local-name()')}' id='{elem_id}' class='{elem_class}'. Placing last.", end="")
        return y

    except Exception as e:
        # Catch errors during sort key calculation
        elem_id = element.get('id', 'N/A')
        print(f"\nError calculating sort key for element ID '{elem_id}': {e}. Placing last.", end="")
        return float('inf') # Ensure it sorts last if error occurs


# --- Main Extraction Function ---
def extract_and_save_components(svg_path, output_dir):
    """
    Parses the SVG, identifies components, sorts them, and renders each to a PNG file.
    """
    if not os.path.isfile(svg_path):
        print(f"Error: Input SVG file not found: {svg_path}")
        return False

    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        print(f"Error creating output directory '{output_dir}': {e}")
        return False

    try:
        namespaces = {'svg': 'http://www.w3.org/2000/svg'}
        parser = ET.XMLParser(remove_blank_text=True, recover=True)
        try:
            tree = ET.parse(svg_path, parser)
        except ET.XMLSyntaxError as e:
            print(f"Error: Failed to parse SVG file '{svg_path}'. It might be invalid XML.")
            print(f"Parser reported: {e}")
            return False
        root = tree.getroot()

        original_id = root.get('id')
        original_viewBox = root.get('viewBox')
        original_width = root.get('width')
        original_height = root.get('height')
        original_styles = root.xpath('//svg:style', namespaces=namespaces)
        style_copies = [copy.deepcopy(style) for style in original_styles] if original_styles else []

        if not original_viewBox:
            print("Error: Original SVG missing 'viewBox' attribute.")
            return False
        if not original_id:
            print("Warning: Original SVG root missing 'id'. Using default 'extracted-svg-component'.")
            original_id = "extracted-svg-component"

        # --- Identify potential components with MORE SPECIFIC Selectors ---
        print("Finding components using specific XPath selectors...")

        # Nodes: <g> elements with class 'node' inside a parent group (like <g class="nodes"> or root <g>)
        node_selector = '/svg:svg/svg:g//svg:g[contains(@class, "node")]'
        nodes = root.xpath(node_selector, namespaces=namespaces)
        print(f" - Found {len(nodes)} node groups ('{node_selector}')")

        # Edge Labels: <g> elements with class 'edgeLabel' inside <g class="edgeLabels">
        edge_label_selector = '/svg:svg/svg:g//svg:g[@class="edgeLabels"]/svg:g[contains(@class, "edgeLabel")]'
        edge_labels = root.xpath(edge_label_selector, namespaces=namespaces)
        print(f" - Found {len(edge_labels)} edge label groups ('{edge_label_selector}')")

        # Edge Paths: <path> elements with specific classes inside <g class="edgePaths">
        path_selector = '/svg:svg/svg:g//svg:g[@class="edgePaths"]/svg:path[contains(@class, "flowchart-link") or contains(@class, "transition")]'
        edge_paths = root.xpath(path_selector, namespaces=namespaces)
        print(f" - Found {len(edge_paths)} edge paths (flowchart-link or transition) ('{path_selector}')")

        # ER Diagram paths (example, adjust class if needed)
        er_path_selector = '/svg:svg/svg:g//svg:g[@class="edgePaths"]/svg:path[contains(@class, "relation")]'
        er_paths = root.xpath(er_path_selector, namespaces=namespaces)
        if er_paths:
            print(f" - Found {len(er_paths)} ER diagram relation paths ('{er_path_selector}')")
            edge_paths.extend(er_paths) # Add ER paths to the list

        all_potential_elements = nodes + edge_labels + edge_paths

        if not all_potential_elements:
            print("\nWarning: No components found matching the specific selectors.")
            print("The SVG structure might differ, or the diagram might be empty.")
            return True # Completed, but found nothing

        components_to_sort = []
        print("\nCalculating sort keys (Y-coordinates)...")
        for i, elem in enumerate(all_potential_elements):
            sort_y = get_sort_key(elem, namespaces)
            components_to_sort.append((sort_y, i, elem))

        components_to_sort.sort(key=lambda item: (item[0], item[1]))
        print(f"Sorting {len(components_to_sort)} components complete.")

        defs_elements = root.xpath('//svg:defs', namespaces=namespaces)
        defs_copy = copy.deepcopy(defs_elements[0]) if defs_elements else None
        has_defs = defs_copy is not None
        if not has_defs:
             print("Warning: No <defs> section found in the original SVG.")


        print(f"\nRendering {len(components_to_sort)} components to PNG files in '{output_dir}'...")
        print("(This preserves original positioning; use 'magick mogrify -trim *.png' to autocrop later)")
        success_count = 0
        fail_count = 0
        skip_count = 0
        for i, (sort_y, orig_index, element) in enumerate(components_to_sort):
            component_num = i + 1
            elem_id = element.get('id', f'elem_{orig_index}')
            elem_tag = element.xpath('local-name()')

            # --- FIX: Check if element is a path needing markers when defs are missing ---
            needs_markers = element.get('marker-start') or element.get('marker-mid') or element.get('marker-end')
            if elem_tag == 'path' and needs_markers and not has_defs:
                print(f"\nSkipping component {component_num} (Path ID: {elem_id}): Uses markers but no <defs> found in original SVG.", end="")
                skip_count += 1
                continue # Skip rendering this component

            # --- Proceed with rendering ---
            try:
                nsmap = {None: namespaces['svg']}
                if hasattr(root, 'nsmap'):
                    for prefix, uri in root.nsmap.items():
                        if prefix: nsmap[prefix] = uri

                new_svg = ET.Element(ET.QName(namespaces['svg'], 'svg'), nsmap=nsmap)
                new_svg.set('version', '1.1')
                new_svg.set('viewBox', original_viewBox)
                new_svg.set('id', original_id)
                if original_width: new_svg.set('width', original_width)
                if original_height: new_svg.set('height', original_height)

                for style_copy in style_copies:
                    new_svg.append(copy.deepcopy(style_copy))

                # Only add <defs> if they existed in the original
                if has_defs:
                    new_svg.append(copy.deepcopy(defs_copy))

                element_copy = copy.deepcopy(element)
                new_svg.append(element_copy)

                svg_bytes = ET.tostring(new_svg, encoding='utf-8', xml_declaration=True, pretty_print=False)
                output_filename = os.path.join(output_dir, f"component-{component_num:03d}.png")

                cairosvg.svg2png(bytestring=svg_bytes, write_to=output_filename)
                success_count += 1
                print(f"\r - Saved: {output_filename} [{component_num}/{len(components_to_sort)}]", end="")

            except Exception as e:
                fail_count += 1
                # Consolidate error printing
                print(f"\n--- Error processing component {component_num} ---")
                print(f"  Element: <{elem_tag}> ID: {elem_id}")
                print(f"  Error: {e}")
                # Optional: Save the failing SVG for debugging
                # try:
                #     fail_svg_filename = os.path.join(output_dir, f"component-{component_num:03d}_FAILED.svg")
                #     with open(fail_svg_filename, "wb") as f_err: f_err.write(svg_bytes)
                #     print(f"  Saved failing SVG to: {fail_svg_filename}")
                # except Exception as dump_e: print(f"  (Could not save failing SVG: {dump_e})")

        print(f"\n\nRendering finished. {success_count} succeeded, {fail_count} failed, {skip_count} skipped (missing defs).")
        return True

    except ET.ParseError as e:
        print(f"\nError: Failed to parse the SVG file '{svg_path}'.")
        print(f"Parser reported: {e}")
        return False
    except Exception as e:
        print(f"\nAn unexpected error occurred:")
        import traceback
        print("-" * 60)
        traceback.print_exc(file=sys.stdout)
        print("-" * 60)
        return False


# --- Get User Input ---
# [This function remains the same as the previous version]
def get_user_input():
    """Prompts the user for the input SVG file path and output directory."""
    print("SVG Component Extraction Tool")
    print("============================")
    print("Extracts nodes, labels, and arrows from a Mermaid SVG into separate PNGs.")
    print("Requires 'lxml' and 'cairosvg' (`pip install lxml cairosvg`).\n")

    while True:
        svg_path = input("Enter the path to your Mermaid SVG file: ").strip() # Added strip()
        if not svg_path:
            print("Input path cannot be empty.")
            continue
        # Check if path exists *before* checking extension
        if not os.path.exists(svg_path):
             print(f"Error: File not found at '{svg_path}'. Please check the path and remove trailing spaces if any.")
             continue
        # Check if it's a file and ends with .svg
        if os.path.isfile(svg_path) and svg_path.lower().endswith('.svg'):
            break
        elif not os.path.isfile(svg_path):
             print(f"Error: Input is a directory, not a file: '{svg_path}'.")
        elif not svg_path.lower().endswith('.svg'):
             print("Error: File does not appear to be an SVG file (must end with .svg).")
        else:
             print("Invalid input. Please enter a valid path to an SVG file.")


    output_dir_prompt = input(f"Enter the output directory name [{DEFAULT_OUTPUT_DIR}]: ")
    output_dir = output_dir_prompt.strip() if output_dir_prompt.strip() else DEFAULT_OUTPUT_DIR

    print()
    return svg_path, output_dir

# --- Main Execution Block ---
# [This block remains the same as the previous version]
if __name__ == "__main__":
    try:
        from lxml import etree
    except ImportError:
        print("\nFatal Error: The 'lxml' library is required but not found.")
        print("Please install it using: pip install lxml")
        sys.exit(1)

    input_svg_file, output_folder_name = get_user_input()

    print(f"Starting SVG component extraction for: '{input_svg_file}'")
    print(f"Output will be saved in: '{output_folder_name}'")
    print("-" * 60)

    success = extract_and_save_components(input_svg_file, output_folder_name)

    print("-" * 60)
    if success:
        print(f"Extraction process completed. Please check the '{output_folder_name}' directory.")
    else:
        print("Extraction process failed due to errors.")

    sys.exit(0 if success else 1)