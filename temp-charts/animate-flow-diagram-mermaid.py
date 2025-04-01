# -*- coding: utf-8 -*-
"""
Mermaid Flowchart Parser and Animator v3.2

Parses Mermaid flowcharts including styles and class definitions.
Generates a granular animation sequence based on connection order,
showing nodes with styles/subgraphs when they first appear in a connection,
and adding the connection line in a subsequent step. Handles chained connections.
"""

import re
import os
import sys
import traceback
from collections import defaultdict, OrderedDict

class MermaidFlowchartParser:
    def __init__(self):
        """Initializes the parser."""
        self.nodes = OrderedDict()  # Node ID -> Base definition string (e.g., "A[Text]")
        self.node_styles = {}       # Node ID -> Style Class Name
        self.connections_data = []  # Parsed connection dicts
        self.subgraphs = OrderedDict() # Subgraph Name -> List of Node IDs
        self.node_to_subgraph = {}  # Node ID -> Subgraph Name
        self.class_definitions = OrderedDict() # Class Name -> Attribute string
        self.declaration = ""
        self.ordered_elements = []  # Sequence of unique {'type': '...', 'data': ...} events

        # --- Regex Patterns ---
        self.node_def_anywhere_pattern = re.compile(
            r'([A-Za-z0-9_]+)((?:\[[^\]]*?\]|\([^)]*?\)|{[^}]*?})*)'
            r'(?:::([A-Za-z0-9_]+))?'
        )
        self.simple_node_with_style_pattern = re.compile(
            r'^\s*([A-Za-z0-9_]+):::([A-Za-z0-9_]+)\s*(?:%%.*)?$'
        )
        self.simple_node_pattern = re.compile(
            r'^\s*([A-Za-z0-9_]+)\s*(?:%%.*)?$'
        )
        self.connection_pattern = re.compile(
            r'([A-Za-z0-9_]+)\s+'
            r'((?:-{1,2}>?|={2}>)(?:\|[^|]*?\|)?)' # Connector -->, --, ->, ==>, maybe |label|
            r'\s+([A-Za-z0-9_]+)'
        )
        self.class_def_pattern = re.compile(r'^\s*classDef\s+([A-Za-z0-9_]+)\s+(.*)$')
        self.subgraph_start_pattern = re.compile(r'^\s*subgraph\s+(.*)$')
        self.subgraph_end_pattern = re.compile(r'^\s*end\s*$')
        # --- End Regex ---


    def _add_node(self, node_id, definition=None, style_class=None):
        """Adds/updates node definition and style, avoiding adding style names as nodes."""
        # Do not add node if the ID matches a defined class name
        if node_id in self.class_definitions:
            # print(f"Debug: Ignoring potential node '{node_id}' as it matches a classDef.")
            return

        # Add/Update node definition (prioritize full definitions)
        is_new_node = node_id not in self.nodes
        has_better_definition = definition and (is_new_node or self.nodes[node_id] == node_id)

        if is_new_node or has_better_definition:
            self.nodes[node_id] = definition if definition else node_id
        elif definition is None and is_new_node:
             self.nodes[node_id] = node_id

        # Add/Update node style
        if style_class:
            self.node_styles[node_id] = style_class


    def parse_file(self, filepath):
        """Reads a Mermaid file and initiates parsing."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
            return self.parse_content(content)
        except FileNotFoundError: print(f"Error: Input file not found: '{filepath}'"); sys.exit(1)
        except Exception as e: print(f"Error reading file '{filepath}': {e}"); traceback.print_exc(); sys.exit(1)


    def parse_content(self, content):
        """Parses Mermaid content line by line, extracting all elements."""
        lines = content.strip().split('\n')
        # --- Reset parser state ---
        self.declaration = ""
        self.nodes = OrderedDict(); self.node_styles = {}
        self.connections_data = []; self.subgraphs = OrderedDict()
        self.node_to_subgraph = {}; self.class_definitions = OrderedDict()
        self.ordered_elements = []; _definition_event_added = set()
        # --- End Reset ---

        if not lines: raise ValueError("Input content is empty.")
        self.declaration = lines[0].strip()
        if not (self.declaration.lower().startswith('flowchart') or self.declaration.lower().startswith('graph')):
             print(f"Warning: First line '{self.declaration}' may not be a valid Mermaid declaration.")

        current_subgraph_name = None; inside_subgraph_block = False
        temp_ordered_elements = [] # Collect raw events first

        for line_num, line in enumerate(lines[1:], start=2):
            line_strip = line.strip()
            if not line_strip or line_strip.startswith('%%'): continue

            # 1. Check for classDef (must be processed first)
            class_def_match = self.class_def_pattern.match(line_strip)
            if class_def_match:
                name, attrs = class_def_match.groups()
                attrs = attrs.strip().rstrip(';')
                self.class_definitions[name] = attrs
                # Ensure class names are not added as nodes later
                self._add_node(name) # Temporarily add to prevent simple node match
                continue

            # 2. Handle Subgraph Start/End
            if self.subgraph_start_pattern.match(line_strip):
                current_subgraph_name = self.subgraph_start_pattern.match(line_strip).group(1).strip()
                if current_subgraph_name not in self.subgraphs: self.subgraphs[current_subgraph_name] = []
                inside_subgraph_block = True
                continue
            if self.subgraph_end_pattern.match(line_strip) and inside_subgraph_block:
                current_subgraph_name = None; inside_subgraph_block = False
                continue

            # 3. Find Node Definitions & Styles (must happen before connection parsing on the same line)
            processed_nodes_on_this_line = set()
            for match in self.node_def_anywhere_pattern.finditer(line_strip):
                node_id, bracket_text, style_class = match.groups()
                # Prevent adding class names as nodes
                if node_id in self.class_definitions: continue

                full_def = node_id
                if bracket_text and bracket_text[0] in "[({": full_def = node_id + bracket_text
                self._add_node(node_id, full_def, style_class)
                processed_nodes_on_this_line.add(node_id)
                if node_id not in _definition_event_added:
                    temp_ordered_elements.append({'type': 'node_definition', 'data': {'id': node_id}})
                    _definition_event_added.add(node_id)

            # 4. Find Connections
            connections_found = self.connection_pattern.findall(line_strip)
            processed_as_connection = bool(connections_found)
            for source, full_connector, target in connections_found:
                # Prevent adding class names as nodes
                if source in self.class_definitions or target in self.class_definitions: continue

                self._add_node(source); self._add_node(target) # Ensure nodes exist
                label = None; label_match = re.search(r'\|([^|]*?)\|', full_connector)
                if label_match:
                    label = label_match.group(1)
                    connector_type_str = full_connector.replace(label_match.group(0), '').strip()
                else: connector_type_str = full_connector.strip()

                # Determine connection type
                if '-.->' in connector_type_str: conn_type = '-.->'
                elif '-->' in connector_type_str: conn_type = '-->'
                elif '==>' in connector_type_str: conn_type = '==>'
                elif '--' in connector_type_str: conn_type = '--'
                else: conn_type = connector_type_str # Fallback

                connection_data = {'source': source, 'target': target, 'type': conn_type, 'label': label}
                self.connections_data.append(connection_data) # Store raw data
                temp_ordered_elements.append({'type': 'connection', 'data': connection_data})

            # 5. Handle Simple Nodes (listed in subgraphs or styled standalone)
            if not processed_as_connection and not processed_nodes_on_this_line:
                simple_style_match = self.simple_node_with_style_pattern.match(line_strip)
                if simple_style_match:
                    node_id, style_class = simple_style_match.groups()
                    if node_id not in self.class_definitions: # Check again
                         self._add_node(node_id, style_class=style_class)
                         processed_nodes_on_this_line.add(node_id) # Mark handled
                         if node_id not in _definition_event_added:
                             temp_ordered_elements.append({'type': 'node_definition', 'data': {'id': node_id}})
                             _definition_event_added.add(node_id)

                elif self.simple_node_pattern.match(line_strip):
                    node_id = self.simple_node_pattern.match(line_strip).group(1)
                    if node_id not in self.class_definitions and node_id not in processed_nodes_on_this_line:
                        self._add_node(node_id)
                        processed_nodes_on_this_line.add(node_id)
                        if node_id not in _definition_event_added:
                            temp_ordered_elements.append({'type': 'node_definition', 'data': {'id': node_id}})
                            _definition_event_added.add(node_id)

            # Add nodes processed on this line to subgraph if applicable
            if inside_subgraph_block and current_subgraph_name:
                for node_id in processed_nodes_on_this_line:
                     if node_id not in self.subgraphs[current_subgraph_name]:
                         self.subgraphs[current_subgraph_name].append(node_id)
                     self.node_to_subgraph[node_id] = current_subgraph_name

        # --- Final Cleanup & De-duplication ---
        # Remove class names potentially added as nodes earlier
        for class_name in list(self.nodes.keys()):
             if class_name in self.class_definitions:
                  del self.nodes[class_name]

        all_node_ids_mentioned = set(self.nodes.keys())
        for conn in self.connections_data: all_node_ids_mentioned.update([conn['source'], conn['target']])
        for sg_name, node_list in self.subgraphs.items():
            for node_id in node_list:
                 if node_id not in self.class_definitions: all_node_ids_mentioned.add(node_id)
                 if node_id not in self.node_to_subgraph and sg_name: self.node_to_subgraph[node_id] = sg_name
        for node_id in all_node_ids_mentioned: self._add_node(node_id)

        # De-duplicate ordered elements
        seen_element_keys = set()
        for elem in temp_ordered_elements:
            key = None
            if elem['type'] == 'node_definition': key = f"def_{elem['data']['id']}"
            elif elem['type'] == 'connection':
                d = elem['data']; key = f"conn_{d['source']}_{d['target']}_{d['type']}_{d['label']}"
            if key and key not in seen_element_keys:
                self.ordered_elements.append(elem)
                seen_element_keys.add(key)

        return { # Return parsed data
            'nodes': self.nodes, 'node_styles': self.node_styles, 'connections_data': self.connections_data,
            'subgraphs': self.subgraphs, 'node_to_subgraph': self.node_to_subgraph,
            'class_definitions': self.class_definitions, 'ordered_elements': self.ordered_elements
        }

    def _generate_frame_content(self, visible_nodes, visible_connections_set):
        """Helper function generates Mermaid string for a frame based on visible elements."""
        # Start with declaration and all defined classes
        current_content = [self.declaration]
        if self.class_definitions: current_content.append("\n    %% Class Definitions")
        for name, attrs in self.class_definitions.items(): current_content.append(f"    classDef {name} {attrs}")

        # Add sections only if they have content
        current_node_defs = []; current_connections = []; subgraph_sections = []
        processed_definitions = set(); processed_connections_str = set()

        # 1. Add Node Definitions with Styles
        for node_id in self.nodes:
            if node_id in visible_nodes:
                base_definition = self.nodes.get(node_id, node_id) # Use ID if definition somehow missing
                style_class = self.node_styles.get(node_id)
                full_styled_definition = f"{base_definition}{f':::{style_class}' if style_class else ''}"
                if full_styled_definition not in processed_definitions:
                     current_node_defs.append(f"    {full_styled_definition}")
                     processed_definitions.add(full_styled_definition)

        # 2. Add Visible Connections
        sorted_connections = sorted(list(visible_connections_set))
        for source, target, label, conn_type in sorted_connections:
             if source in visible_nodes and target in visible_nodes:
                conn_str = f"    {source} {conn_type}"
                if label is not None: conn_str += f"|{label}|" # Handle label presence
                conn_str += f" {target}"
                if conn_str not in processed_connections_str:
                    current_connections.append(conn_str)
                    processed_connections_str.add(conn_str)

        # 3. Add Subgraphs
        processed_subgraph_nodes = set()
        for subgraph_name, original_node_list in self.subgraphs.items():
            visible_in_subgraph = [nid for nid in original_node_list if nid in visible_nodes]
            if visible_in_subgraph:
                subgraph_lines = [f"\n    subgraph {subgraph_name}"]
                visible_in_subgraph.sort()
                for nid in visible_in_subgraph:
                    subgraph_lines.append(f"        {nid}")
                    processed_subgraph_nodes.add(nid)
                subgraph_lines.append(f"    end")
                subgraph_sections.append("\n".join(subgraph_lines))

        # Assemble frame content, adding section comments if content exists
        if current_node_defs: current_content.append("\n    %% Node Definitions"); current_content.extend(sorted(current_node_defs))
        if current_connections: current_content.append("\n    %% Connections"); current_content.extend(sorted(current_connections))
        if subgraph_sections: current_content.append("\n    %% Subgraphs"); current_content.extend(sorted(subgraph_sections))

        return "\n".join(current_content)


    def generate_animation_sequence(self, output_dir):
        """Generates granular animation frames based on connection-driven node visibility."""
        if not os.path.exists(output_dir): os.makedirs(output_dir); print(f"Created directory: '{output_dir}'")
        else: # Clear existing files
            print(f"Clearing existing files in '{output_dir}'..."); files_cleared = 0
            for file in os.listdir(output_dir):
                if file.endswith('.mmd') or file.lower() == "readme.md":
                    try: os.remove(os.path.join(output_dir, file)); files_cleared += 1
                    except OSError as e: print(f"  Warn: Could not remove {file}: {e}")
            print(f"  Cleared {files_cleared} files.")

        frames = []; visible_nodes = set(); visible_connections_set = set(); last_frame_content = None

        # --- Frame 1: Declaration + ClassDefs ---
        initial_content_list = [self.declaration]
        if self.class_definitions: initial_content_list.append("\n    %% Class Definitions")
        initial_content_list.extend(f"    classDef {name} {attrs}" for name, attrs in self.class_definitions.items())
        initial_frame_str = "\n".join(initial_content_list); frames.append(initial_frame_str); last_frame_content = initial_frame_str
        print(f"Frame 1: Initial Declaration and ClassDefs added.")

        # --- Generate Frames Step-by-Step ---
        print(f"Processing {len(self.ordered_elements)} elements...")
        frame_counter = 1 # Start from frame 1 (declaration is frame 1)

        for element_index, element in enumerate(self.ordered_elements):
            # We primarily care about connections to drive visibility
            if element['type'] == 'connection':
                conn_data = element['data']
                source, target, label, conn_type = conn_data['source'], conn_data['target'], conn_data['label'], conn_data['type']
                connection_tuple = (source, target, label, conn_type)

                # Step A: Ensure Source Visible
                if source not in visible_nodes:
                    visible_nodes.add(source)
                    current_frame_content = self._generate_frame_content(visible_nodes, visible_connections_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content); last_frame_content = current_frame_content; frame_counter += 1
                        # print(f"  Elem {element_index+1}: Source '{source}' visible -> Frame {frame_counter}")

                # Step B: Ensure Target Visible
                if target not in visible_nodes:
                    visible_nodes.add(target)
                    current_frame_content = self._generate_frame_content(visible_nodes, visible_connections_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content); last_frame_content = current_frame_content; frame_counter += 1
                        # print(f"  Elem {element_index+1}: Target '{target}' visible -> Frame {frame_counter}")

                # Step C: Ensure Connection Visible (only if nodes are visible)
                if connection_tuple not in visible_connections_set and source in visible_nodes and target in visible_nodes:
                    visible_connections_set.add(connection_tuple)
                    current_frame_content = self._generate_frame_content(visible_nodes, visible_connections_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content); last_frame_content = current_frame_content; frame_counter += 1
                        # print(f"  Elem {element_index+1}: Conn '{source}{conn_type}{target}' visible -> Frame {frame_counter}")

            # Node definitions are used by the helper but don't trigger frames directly anymore

        # --- Write Output Files ---
        num_frames = len(frames)
        print(f"\nGenerating {num_frames} frame files...")
        for i, frame_content in enumerate(frames):
            frame_num = i + 1
            filename = f"image_{frame_num}.mmd"
            filepath = os.path.join(output_dir, filename)
            try:
                with open(filepath, 'w', encoding='utf-8') as f: f.write(frame_content)
            except IOError as e: print(f"  Error writing file {filepath}: {e}")

        # --- Create README.md ---
        readme_path = os.path.join(output_dir, "README.md")
        print(f"Generating README.md at {readme_path}...")
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write("# Mermaid Flowchart Animation\n\n")
                f.write(f"Generated {num_frames} frames.\n\n")
                for i, frame_content in enumerate(frames):
                    frame_num = i + 1
                    f.write(f"## Frame {frame_num}\n\n```mermaid\n{frame_content}\n```\n\n")
            print("  README.md generated successfully.")
        except IOError as e: print(f"  Error writing README.md: {e}")

        print(f"\nGenerated {num_frames} animation frames in '{output_dir}'")
        return num_frames


# --- Main execution block ---
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print("\nUsage: python your_script_name.py <input_mermaid_file> [--output-dir <output_directory>]")
        print("\nArguments:")
        print("  <input_mermaid_file>   Path to the input .mmd file.")
        print("  --output-dir <dir>     Optional. Directory to save frame files and README.md.")
        print("                         Defaults to 'animation_frames' in the current directory.")
        sys.exit(0)

    input_file = sys.argv[1]
    output_dir = "animation_frames" # Default output
    if "--output-dir" in sys.argv:
        try:
            output_dir_index = sys.argv.index("--output-dir") + 1
            if output_dir_index < len(sys.argv): output_dir = sys.argv[output_dir_index]
            else: print("Error: --output-dir option requires a directory path."); sys.exit(1)
        except ValueError: print("Error parsing --output-dir argument."); sys.exit(1)

    if not os.path.isfile(input_file):
        print(f"Error: Input file not found or is not a file: '{input_file}'")
        sys.exit(1)

    parser = MermaidFlowchartParser()
    try:
        print(f"Parsing Mermaid file: '{input_file}'...")
        parsed_data = parser.parse_file(input_file)
        print("Parsing complete.")
        print(f"  Found {len(parsed_data['nodes'])} unique nodes (excluding class names).")
        print(f"  Found {len(parsed_data['connections_data'])} connection definitions parsed.")
        print(f"  Found {len(parsed_data['subgraphs'])} subgraphs.")
        print(f"  Found {len(parsed_data['class_definitions'])} class definitions.")
        print(f"  Found {len(parsed_data['ordered_elements'])} unique elements for animation sequence.")

        print(f"\nGenerating animation sequence in directory: '{output_dir}'...")
        frames_generated = parser.generate_animation_sequence(output_dir)

    except Exception as e:
        print(f"\n--- An error occurred during processing ---")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")
        print("\n--- Traceback ---")
        traceback.print_exc()
        print("-----------------")
        sys.exit(1)

    print("\nScript finished successfully.")