# -*- coding: utf-8 -*-
"""
Mermaid Graph Parser and Animator v4.1

Parses Mermaid 'graph' diagrams, including nested subgraphs, node styles 
(classDef, class, :::styleClass), and various link types.
Generates a sequence of .mmd files representing the granular, incremental 
build-up of the graph, suitable for creating animations. 
Node visibility is driven by connections appearing in the parsed order.
Handles chained connections sequentially.
"""

import re
import os
import sys
import traceback
from collections import defaultdict, OrderedDict

class MermaidGraphParser:
    def __init__(self):
        """Initializes the parser with necessary attributes and regex patterns for graphs."""
        self.nodes = OrderedDict()  # Node ID -> Base definition string (e.g., "A[Text]", "B(Text)")
        self.node_styles = {}       # Node ID -> Style Class Name (e.g., "A": "styleClass")
        self.connections_data = []  # Parsed connection dicts: {'source', 'target', 'type', 'label'}
        self.subgraphs = OrderedDict() # Subgraph ID/Title -> List of direct child Node IDs originally listed inside
        self.subgraph_parents = {}  # Subgraph ID/Title -> Parent Subgraph ID/Title or None
        self.node_to_subgraph = {}  # Node ID -> Innermost Subgraph ID/Title it belongs to
        self.class_definitions = OrderedDict() # Class Name -> Attribute string
        self.declaration = ""       # Stores the first line (e.g., "graph TD")
        self.ordered_elements = []  # Sequence of unique {'type': '...', 'data': ...} events for animation

        # --- Regex Patterns ---
        # Node definitions + optional :::style
        # Captures: 1=ID, 2=Brackets(optional), 3=StyleClass(optional)
        self.node_def_anywhere_pattern = re.compile(
            r'([A-Za-z0-9_]+)((?:\[[^\]]*?\]|\([^)]*?\)|{[^}]*?}|{{[^}]*?}}|\[\(.*?\)\]|\(\(.*?\)\)|\[\[.*?\]\]|>[^\]]*?\]|\[/[^\]]*?\]|\[\\[^\]]*?\\]|\[>[^\]]*?\]))?'
            r'(?:::([A-Za-z0-9_]+))?'
        )
        # NodeID:::StyleClass alone on a line
        self.simple_node_with_style_pattern = re.compile(
            r'^\s*([A-Za-z0-9_]+):::([A-Za-z0-9_]+)\s*(?:%%.*)?$'
        )
        # NodeID alone on a line
        self.simple_node_pattern = re.compile(
            r'^\s*([A-Za-z0-9_]+)\s*(?:%%.*)?$'
        )
        # Connections: -->, ---, -.->, -.-, ==>, etc. + optional |Label|
        # Captures: 1=Source, 2=ConnectorString, 3=Target
        self.connection_pattern = re.compile(
            r'([A-Za-z0-9_]+)\s+'
            r'((?:-{1,3}>?|-{1,3}\.?-{1,2}>?|o--o|x--x|<-->|={2}>)(?:\|[^|]*?\|)?)'
            r'\s+([A-Za-z0-9_]+)'
        )
        # classDef ClassName attributes
        self.class_def_pattern = re.compile(r'^\s*classDef\s+([A-Za-z0-9_]+)\s+(.*)$')
        # class Node1,Node2 ClassName
        self.class_assign_pattern = re.compile(r'^\s*class\s+([A-Za-z0-9_,\s]+?)\s+([A-Za-z0-9_]+)\s*;?$')
        # subgraph ID ["Optional Title"]
        self.subgraph_start_pattern = re.compile(r'^\s*subgraph\s+([\w_]+|"[^"]+")\s*(?:\[(.*?)\])?.*$')
        # end
        self.subgraph_end_pattern = re.compile(r'^\s*end\s*$')
        # --- End Regex ---


    def _add_node(self, node_id, definition=None, style_class=None, current_subgraph_id=None):
        """Adds/updates node definition, style, and subgraph mapping."""
        # Basic validation
        if not node_id or not isinstance(node_id, str): return
        # Ignore if the ID is actually a defined class name
        if node_id in self.class_definitions: return

        node_id = node_id.strip() # Ensure no leading/trailing whitespace
        if not node_id: return

        # Add/Update node definition (prioritize keeping full definitions)
        is_new_node = node_id not in self.nodes
        has_better_definition = definition and (is_new_node or self.nodes[node_id] == node_id)

        if is_new_node or has_better_definition:
            self.nodes[node_id] = definition if definition else node_id
        elif definition is None and is_new_node: # Ensure node exists if first seen without definition
             self.nodes[node_id] = node_id

        # Add/Update node style
        if style_class: self.node_styles[node_id] = style_class
        # Add/Update subgraph mapping (innermost)
        if current_subgraph_id: self.node_to_subgraph[node_id] = current_subgraph_id


    def parse_file(self, filepath):
        """Reads a Mermaid file and initiates parsing."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
            return self.parse_content(content)
        except FileNotFoundError: print(f"Error: Input file not found: '{filepath}'"); sys.exit(1)
        except Exception as e: print(f"Error reading file '{filepath}': {e}"); traceback.print_exc(); sys.exit(1)


    def parse_content(self, content):
        """Parses Mermaid graph content, handling nesting, styles, and connections."""
        lines = content.strip().split('\n')
        # --- Reset parser state ---
        self.__init__()
        # --- End Reset ---

        if not lines: raise ValueError("Input content is empty.")
        self.declaration = lines[0].strip()
        if not self.declaration.lower().startswith('graph'):
             print(f"Warning: First line '{self.declaration}' may not start with 'graph'.")

        subgraph_stack = [] # Use a stack to handle nested subgraphs: stores subgraph IDs/Titles
        temp_ordered_elements = [] # Collect raw events first
        _definition_event_added = set() # Track nodes added to temp_ordered_elements

        # Temporarily mark class names to avoid parsing them as nodes
        _ignore_ids = set(self.class_definitions.keys())

        for line_num, line in enumerate(lines[1:], start=2):
            line_strip = line.strip()
            if not line_strip or line_strip.startswith('%%'): continue

            # --- Processing Order: classDef -> subgraph -> class -> nodes/connections ---

            # 1. classDef
            class_def_match = self.class_def_pattern.match(line_strip)
            if class_def_match:
                name, attrs = class_def_match.groups(); attrs = attrs.strip().rstrip(';')
                self.class_definitions[name] = attrs
                _ignore_ids.add(name) # Mark this ID to be ignored if seen as a node
                continue

            # 2. Subgraph Start/End
            subgraph_start_match = self.subgraph_start_pattern.match(line_strip)
            if subgraph_start_match:
                sg_id_or_title = subgraph_start_match.group(1).strip()
                # Prefer explicit ID in brackets if present: subgraph title [id]
                sg_explicit_id = subgraph_start_match.group(2)
                sg_id = sg_explicit_id.strip() if sg_explicit_id else sg_id_or_title
                # Add to ignore list to prevent treating subgraph ID as node unless explicitly defined
                _ignore_ids.add(sg_id.strip('"')) # Ignore quoted or unquoted version

                parent_subgraph = subgraph_stack[-1] if subgraph_stack else None
                if sg_id not in self.subgraphs: self.subgraphs[sg_id] = []
                self.subgraph_parents[sg_id] = parent_subgraph
                subgraph_stack.append(sg_id)
                continue

            if self.subgraph_end_pattern.match(line_strip) and subgraph_stack:
                subgraph_stack.pop()
                continue

            # 3. class Assignment
            class_assign_match = self.class_assign_pattern.match(line_strip)
            if class_assign_match:
                node_list_str, class_name = class_assign_match.groups()
                node_ids = [nid.strip() for nid in node_list_str.split(',') if nid.strip()]
                if class_name in self.class_definitions:
                    for node_id in node_ids:
                        if node_id and node_id not in _ignore_ids:
                            self._add_node(node_id) # Ensure node exists
                            self.node_styles[node_id] = class_name
                else: print(f"Warning: Line {line_num}: Class '{class_name}' not defined.")
                continue

            # --- Process Nodes and Connections on the line ---
            current_sg_id = subgraph_stack[-1] if subgraph_stack else None # Innermost subgraph
            processed_nodes_on_this_line = set()
            processed_as_connection = False

            # 4. Find Node Definitions & Styles (can coexist with connections)
            # Need to process whole line for all potential defs before connections
            node_defs_found = []
            for match in self.node_def_anywhere_pattern.finditer(line_strip):
                node_id, bracket_text, style_class = match.groups()
                if node_id in _ignore_ids: continue

                full_def = node_id
                if bracket_text: full_def = node_id + bracket_text

                self._add_node(node_id, full_def, style_class, current_sg_id)
                processed_nodes_on_this_line.add(node_id)
                if node_id not in _definition_event_added:
                    temp_ordered_elements.append({'type': 'node_definition', 'data': {'id': node_id}})
                    _definition_event_added.add(node_id)

            # 5. Find Connections
            for match in self.connection_pattern.finditer(line_strip):
                source, full_connector, target = match.groups()
                processed_as_connection = True
                if source in _ignore_ids or target in _ignore_ids: continue

                self._add_node(source, current_subgraph_id=current_sg_id)
                self._add_node(target, current_subgraph_id=current_sg_id)

                label = None; label_match = re.search(r'\|([^|]*?)\|', full_connector)
                if label_match:
                    label = label_match.group(1)
                    connector_type_str = full_connector.replace(label_match.group(0), '').strip()
                else: connector_type_str = full_connector.strip()

                # Store exact connector type
                conn_type = connector_type_str

                connection_data = {'source': source, 'target': target, 'type': conn_type, 'label': label}
                self.connections_data.append(connection_data) # Store raw data
                temp_ordered_elements.append({'type': 'connection', 'data': connection_data})


            # 6. Handle Simple Nodes (if line wasn't a connection and didn't define nodes)
            if not processed_as_connection and not processed_nodes_on_this_line:
                simple_style_match = self.simple_node_with_style_pattern.match(line_strip)
                if simple_style_match:
                    node_id, style_class = simple_style_match.groups()
                    if node_id not in _ignore_ids:
                         self._add_node(node_id, style_class=style_class, current_subgraph_id=current_sg_id)
                         processed_nodes_on_this_line.add(node_id)
                         if node_id not in _definition_event_added:
                             temp_ordered_elements.append({'type': 'node_definition', 'data': {'id': node_id}})
                             _definition_event_added.add(node_id)

                elif self.simple_node_pattern.match(line_strip):
                    node_id = self.simple_node_pattern.match(line_strip).group(1)
                    if node_id not in _ignore_ids and node_id not in processed_nodes_on_this_line:
                        self._add_node(node_id, current_subgraph_id=current_sg_id)
                        processed_nodes_on_this_line.add(node_id)
                        if node_id not in _definition_event_added:
                           temp_ordered_elements.append({'type': 'node_definition', 'data': {'id': node_id}})
                           _definition_event_added.add(node_id)

            # Add newly processed nodes to the current subgraph data structure
            if current_sg_id:
                for node_id in processed_nodes_on_this_line:
                    # Check if node isn't already listed in this specific subgraph
                    if node_id not in self.subgraphs[current_sg_id]:
                        self.subgraphs[current_sg_id].append(node_id)
                    # Ensure node->subgraph mapping is correct (already done in _add_node)
                    self.node_to_subgraph[node_id] = current_sg_id


        # --- Final Cleanup & De-duplication ---
        # Remove ignored IDs (class names) if they only exist as keys with value==key
        for ignored_id in list(self.nodes.keys()):
             if ignored_id in _ignore_ids and self.nodes[ignored_id] == ignored_id:
                  del self.nodes[ignored_id]

        # Ensure all mentioned valid nodes exist
        all_node_ids_mentioned = set(self.nodes.keys())
        for conn in self.connections_data: all_node_ids_mentioned.update([conn['source'], conn['target']])
        for sg_id, node_list in self.subgraphs.items():
            for node_id in node_list:
                 if node_id not in _ignore_ids: all_node_ids_mentioned.add(node_id)
                 if node_id not in self.node_to_subgraph and sg_id: self.node_to_subgraph[node_id] = sg_id
        for node_id in all_node_ids_mentioned:
            if node_id not in _ignore_ids: self._add_node(node_id)

        # De-duplicate ordered elements to ensure unique animation steps
        seen_element_keys = set()
        for elem in temp_ordered_elements:
            key = None
            # Use only node ID for definition uniqueness
            if elem['type'] == 'node_definition': key = f"def_{elem['data']['id']}"
            # Use connection content for connection uniqueness
            elif elem['type'] == 'connection':
                d = elem['data']; key = f"conn_{d['source']}_{d['target']}_{d['type']}_{d['label']}"

            if key and key not in seen_element_keys:
                self.ordered_elements.append(elem)
                seen_element_keys.add(key)

        return { # Return parsed data
            'nodes': self.nodes, 'node_styles': self.node_styles, 'connections_data': self.connections_data,
            'subgraphs': self.subgraphs, 'node_to_subgraph': self.node_to_subgraph,
            'class_definitions': self.class_definitions, 'ordered_elements': self.ordered_elements,
            'subgraph_parents': self.subgraph_parents
        }

    def _generate_frame_content(self, visible_nodes, visible_connections_set):
        """Helper function generates Mermaid string for a frame, handling nesting."""
        content_lines = [self.declaration]

        # Add Class Definitions
        if self.class_definitions: content_lines.append("\n    %% Class Definitions")
        for name, attrs in self.class_definitions.items(): content_lines.append(f"    classDef {name} {attrs}")

        # Add Node Definitions (Outside Subgraphs for clarity)
        node_def_lines = []
        processed_definitions = set() # Track definitions added this frame
        # We iterate through visible nodes to ensure only they are defined
        # Sorting visible nodes ensures consistent definition order frame-to-frame
        for node_id in sorted(list(visible_nodes)):
            if node_id in self.nodes: # Check if node definition exists
                base_definition = self.nodes[node_id]
                style_class = self.node_styles.get(node_id)
                # Construct full definition including style if applicable
                full_styled_definition = f"{base_definition}{f':::{style_class}' if style_class else ''}"

                if full_styled_definition not in processed_definitions:
                    node_def_lines.append(f"    {full_styled_definition}")
                    processed_definitions.add(full_styled_definition)

        if node_def_lines: content_lines.append("\n    %% Node Definitions"); content_lines.extend(node_def_lines)

        # Add Connections
        connection_lines = []
        processed_connections_str = set() # Avoid duplicate connection strings *within* this frame
        sorted_connections = sorted(list(visible_connections_set)) # Sort for consistency
        for source, target, label, conn_type in sorted_connections:
            # Check visibility again (safety)
            if source in visible_nodes and target in visible_nodes:
                conn_str = f"    {source} {conn_type}"
                if label is not None: conn_str += f"|{label}|"
                conn_str += f" {target}"
                if conn_str not in processed_connections_str:
                    connection_lines.append(conn_str)
                    processed_connections_str.add(conn_str)
        if connection_lines: content_lines.append("\n    %% Connections"); content_lines.extend(connection_lines) # Already sorted

        # Add Subgraphs (handles nesting recursively)
        if self.subgraphs: content_lines.append("\n    %% Subgraphs")
        rendered_subgraphs = set()
        # Find top-level subgraphs (those whose parent is None or not in self.subgraphs)
        all_sg_ids = set(self.subgraphs.keys())
        top_level_subgraphs = sorted([
            sg_id for sg_id in all_sg_ids
            if self.subgraph_parents.get(sg_id) is None or self.subgraph_parents.get(sg_id) not in all_sg_ids
        ])

        def render_subgraph_recursive(sg_id, indent="    "):
            # Check if this subgraph should be rendered and hasn't been
            nodes_in_sg = self.subgraphs.get(sg_id, [])
            visible_direct_nodes_in_sg = [nid for nid in nodes_in_sg if nid in visible_nodes and self.node_to_subgraph.get(nid) == sg_id]
            child_subgraphs = sorted([csg_id for csg_id, parent in self.subgraph_parents.items() if parent == sg_id])
            has_visible_children = any(nid in visible_nodes for nid in nodes_in_sg)
            has_visible_child_subgraphs = any(csg_id in self.subgraphs for csg_id in child_subgraphs) # Check if child subgraphs exist in keys

            # Only render if it contains visible nodes directly or contains subgraphs that might have visible content
            if sg_id in rendered_subgraphs or not (visible_direct_nodes_in_sg or has_visible_child_subgraphs):
                 return []

            rendered_subgraphs.add(sg_id)
            lines = [f"{indent}subgraph {sg_id}"] # Use the ID/Title stored as the key

            # List *direct* child nodes that are visible
            visible_direct_nodes_in_sg.sort()
            for nid in visible_direct_nodes_in_sg:
                 lines.append(f"{indent}    {nid}")

            # Recursively render child subgraphs
            for csg_id in child_subgraphs:
                 lines.extend(render_subgraph_recursive(csg_id, indent + "    "))

            lines.append(f"{indent}end")
            return lines

        # Render starting from top-level ones
        for sg_id in top_level_subgraphs:
            content_lines.extend(render_subgraph_recursive(sg_id))
        # Render any potentially orphaned subgraphs (should be rare if parsing is correct)
        for sg_id in sorted(list(self.subgraphs.keys())):
             if sg_id not in rendered_subgraphs:
                   # Check if it contains any visible node before rendering
                   if any(nid in visible_nodes for nid in self.subgraphs.get(sg_id,[])):
                        content_lines.extend(render_subgraph_recursive(sg_id))


        return "\n".join(content_lines)

    def generate_animation_sequence(self, output_dir):
        """Generates granular animation frames based on connection-driven node visibility."""
        # --- Setup and Clearing ---
        if not os.path.exists(output_dir): os.makedirs(output_dir); print(f"Created directory: '{output_dir}'")
        else:
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
        print(f"Processing {len(self.ordered_elements)} elements for animation sequence...")
        frame_counter = 1 # Start from frame 1

        nodes_defined_but_not_visible = set(elem['data']['id'] for elem in self.ordered_elements if elem['type'] == 'node_definition')
        connections_processed = set() # Track processed connection tuples

        for element_index, element in enumerate(self.ordered_elements):
            if element['type'] == 'connection':
                conn_data = element['data']
                source, target, label, conn_type = conn_data['source'], conn_data['target'], conn_data['label'], conn_data['type']
                connection_tuple = (source, target, label, conn_type)

                # Skip if connection already processed visually
                if connection_tuple in connections_processed: continue

                # Ensure nodes exist in self.nodes (parsing should guarantee this, but safety check)
                if source not in self.nodes or target not in self.nodes:
                    print(f"Warning: Skipping connection element {element_index+1} due to missing node definition for {source} or {target}")
                    continue

                made_change = False # Track if *this element* caused a frame change

                # Step A: Ensure Source Visible
                if source not in visible_nodes:
                    visible_nodes.add(source)
                    nodes_defined_but_not_visible.discard(source) # Mark as now visible
                    current_frame_content = self._generate_frame_content(visible_nodes, visible_connections_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content); last_frame_content = current_frame_content; frame_counter += 1; made_change = True

                # Step B: Ensure Target Visible
                if target not in visible_nodes:
                    visible_nodes.add(target)
                    nodes_defined_but_not_visible.discard(target) # Mark as now visible
                    current_frame_content = self._generate_frame_content(visible_nodes, visible_connections_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content); last_frame_content = current_frame_content; frame_counter += 1; made_change = True

                # Step C: Ensure Connection Visible (only if nodes are visible)
                if connection_tuple not in visible_connections_set and source in visible_nodes and target in visible_nodes:
                    visible_connections_set.add(connection_tuple)
                    connections_processed.add(connection_tuple) # Mark as visually processed
                    current_frame_content = self._generate_frame_content(visible_nodes, visible_connections_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content); last_frame_content = current_frame_content; frame_counter += 1; made_change = True

            # Note: Node definitions primarily populate self.nodes. Their visibility is triggered by connections.

        # --- Add any remaining defined but unconnected nodes at the end ---
        if nodes_defined_but_not_visible:
             print(f"Adding {len(nodes_defined_but_not_visible)} unconnected nodes...")
             made_final_change = False
             for node_id in sorted(list(nodes_defined_but_not_visible)): # Process alphabetically
                  if node_id not in visible_nodes:
                       visible_nodes.add(node_id)
                       made_final_change = True
             if made_final_change:
                  current_frame_content = self._generate_frame_content(visible_nodes, visible_connections_set)
                  if current_frame_content != last_frame_content:
                      frames.append(current_frame_content); last_frame_content = current_frame_content; frame_counter += 1
                      print(f"  Added final frame for unconnected nodes (Frame {frame_counter}).")


        # --- Write Output Files ---
        num_frames = len(frames)
        print(f"\nGenerating {num_frames} frame files...")
        # ... (Writing frames and README logic remains the same as previous version) ...
        for i, frame_content in enumerate(frames):
            frame_num = i + 1
            filename = f"image_{frame_num}.mmd"
            filepath = os.path.join(output_dir, filename)
            try:
                with open(filepath, 'w', encoding='utf-8') as f: f.write(frame_content)
            except IOError as e: print(f"  Error writing file {filepath}: {e}")

        readme_path = os.path.join(output_dir, "README.md")
        print(f"Generating README.md at {readme_path}...")
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"# Mermaid Graph Animation ({os.path.basename(input_file)})\n\n")
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
        print(f"\nUsage: python {os.path.basename(__file__)} <input_mermaid_file> [--output-dir <output_directory>]")
        print("\nArguments:")
        print("  <input_mermaid_file>   Path to the input .mmd file (graph or flowchart).")
        print("  --output-dir <dir>     Optional. Directory to save frames and README.md.")
        print("                         Defaults to 'graph_animation_frames'.")
        sys.exit(0)

    input_file = sys.argv[1]
    output_dir = "graph_animation_frames" # Default output directory name
    if "--output-dir" in sys.argv:
        try:
            idx = sys.argv.index("--output-dir") + 1
            if idx < len(sys.argv): output_dir = sys.argv[idx]
            else: print("Error: --output-dir requires path."); sys.exit(1)
        except ValueError: print("Error parsing arguments."); sys.exit(1)

    if not os.path.isfile(input_file):
        print(f"Error: Input file not found: '{input_file}'"); sys.exit(1)

    parser = MermaidGraphParser() # Using the combined graph/flowchart parser class
    try:
        print(f"Parsing Mermaid file: '{input_file}'...")
        parsed_data = parser.parse_file(input_file)
        print("Parsing complete.")
        print(f"  Declaration: {parser.declaration}")
        print(f"  Found {len(parsed_data['nodes'])} unique nodes.")
        print(f"  Found {len(parsed_data['connections_data'])} connection instances parsed.")
        print(f"  Found {len(parsed_data['subgraphs'])} subgraphs defined.")
        print(f"  Found {len(parsed_data['class_definitions'])} class definitions.")
        print(f"  Found {len(parsed_data['ordered_elements'])} unique elements for animation sequence.")

        print(f"\nGenerating animation sequence in directory: '{output_dir}'...")
        frames_generated = parser.generate_animation_sequence(output_dir)

    except Exception as e:
        print(f"\n--- An error occurred ---"); print(f"Error: {type(e).__name__}: {e}")
        print("\n--- Traceback ---"); traceback.print_exc(); print("-----------------")
        sys.exit(1)

    print("\nScript finished successfully.")