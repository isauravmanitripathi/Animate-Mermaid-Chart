import re
import os
from collections import defaultdict, OrderedDict

class MermaidFlowchartParser:
    def __init__(self):
        self.nodes = OrderedDict()  # Node ID -> Full definition string or just ID
        self.connections = []       # List of connection dicts
        self.subgraphs = OrderedDict() # Subgraph Name -> List of Node IDs originally listed
        self.node_to_subgraph = {}  # Node ID -> Subgraph Name
        self.incoming_connections = defaultdict(list)
        self.outgoing_connections = defaultdict(list)
        self.declaration = ""
        # Regex patterns
        self.node_def_pattern = re.compile(r'^\s*([A-Za-z0-9_]+)((?:\[[^\]]*\]|\([^)]*\)|{[^}]*})).*$') # Node definition like A[...]
        self.simple_node_pattern = re.compile(r'^\s*([A-Za-z0-9_]+)\s*(?:%%.*)?$') # Just node ID on a line, optional comment
        self.connection_pattern = re.compile(r'([A-Za-z0-9_]+)\s+((?:-->|-.->|==>|===>)(?:\|[^|]*\|)?)\s+([A-Za-z0-9_]+)') # Connections A --- B
        self.subgraph_start_pattern = re.compile(r'^\s*subgraph\s+(.*)$')
        self.subgraph_end_pattern = re.compile(r'^\s*end\s*$')
        # Store original order of definitions and connections for animation
        self.ordered_elements = []

    def _add_node(self, node_id, definition=None):
        """Adds or updates a node, prioritizing full definitions."""
        if node_id not in self.nodes or definition:
            self.nodes[node_id] = definition if definition else node_id

    def parse_file(self, filepath):
        """Parse a Mermaid flowchart file"""
        with open(filepath, 'r') as f:
            content = f.read()
        return self.parse_content(content)

    def parse_content(self, content):
        """Parse Mermaid flowchart content"""
        lines = content.strip().split('\n')

        if not lines:
            raise ValueError("Input content is empty.")

        self.declaration = lines[0].strip()
        if not (self.declaration.lower().startswith('flowchart') or self.declaration.lower().startswith('graph')):
             print(f"Warning: First line '{self.declaration}' might not be a valid Mermaid declaration.")

        current_subgraph_name = None
        inside_subgraph_block = False

        for line in lines[1:]:
            line_strip = line.strip()

            # Skip empty lines and pure comments
            if not line_strip or line_strip.startswith('%%'):
                continue

            # Handle Subgraph Start/End
            subgraph_start_match = self.subgraph_start_pattern.match(line_strip)
            if subgraph_start_match:
                current_subgraph_name = subgraph_start_match.group(1).strip()
                if current_subgraph_name not in self.subgraphs:
                   self.subgraphs[current_subgraph_name] = []
                inside_subgraph_block = True
                continue # Don't process subgraph line further

            if self.subgraph_end_pattern.match(line_strip) and inside_subgraph_block:
                current_subgraph_name = None
                inside_subgraph_block = False
                continue # Don't process end line further

            # --- Process lines for nodes and connections ---

            # Check for connections first
            connections_found = self.connection_pattern.findall(line_strip)
            if connections_found:
                for source, connector, target in connections_found:
                    # Ensure nodes exist
                    self._add_node(source)
                    self._add_node(target)

                    # Extract label
                    label = None
                    label_match = re.search(r'\|([^|]*)\|', connector)
                    if label_match:
                        label = label_match.group(1)

                    conn_type = '-.->' if '-.' in connector else '-->' # Simple check for dotted/solid
                    # More robust check if other types are needed:
                    # if '-.->' in connector: conn_type = '-.->'
                    # elif '-->' in connector: conn_type = '-->'
                    # elif '==>' in connector: conn_type = '==>' # etc.


                    connection = {
                        'source': source,
                        'target': target,
                        'type': conn_type, # Store the exact type found
                        'label': label,
                        'full_line': line_strip # Store original line for ordering/exact reproduction
                    }
                    self.connections.append(connection)
                    self.incoming_connections[target].append(connection)
                    self.outgoing_connections[source].append(connection)
                    self.ordered_elements.append({'type': 'connection', 'data': connection})

            # Check for node definitions (A[...], B(...), C{...})
            node_def_match = self.node_def_pattern.match(line_strip)
            if node_def_match:
                node_id = node_def_match.group(1)
                full_def = node_id + node_def_match.group(2) # Reconstruct full definition A[...]
                self._add_node(node_id, full_def)
                self.ordered_elements.append({'type': 'node_definition', 'data': {'id': node_id, 'definition': full_def}})
                if inside_subgraph_block and current_subgraph_name:
                   if node_id not in self.subgraphs[current_subgraph_name]:
                       self.subgraphs[current_subgraph_name].append(node_id)
                   self.node_to_subgraph[node_id] = current_subgraph_name
                continue # Definition found, skip simple node check

            # Check for simple node IDs (inside subgraph or potentially standalone)
            simple_node_match = self.simple_node_pattern.match(line_strip)
            if simple_node_match and not connections_found: # Avoid matching nodes part of a connection line again
                node_id = simple_node_match.group(1)
                # Only add if it's not already defined more fully
                if node_id not in self.nodes or self.nodes[node_id] == node_id:
                     self._add_node(node_id)
                # If inside a subgraph block, add it to the subgraph list and mapping
                if inside_subgraph_block and current_subgraph_name:
                   if node_id not in self.subgraphs[current_subgraph_name]:
                       self.subgraphs[current_subgraph_name].append(node_id)
                   self.node_to_subgraph[node_id] = current_subgraph_name
                # Check if this simple node should be an ordered element (if not part of a definition/connection already processed)
                # This might add duplicates if node mentioned alone AND in connection on same line - handle later if needed
                is_already_element = any(el['type'] == 'node_definition' and el['data']['id'] == node_id for el in self.ordered_elements) or \
                                     any(el['type'] == 'connection' and (el['data']['source'] == node_id or el['data']['target'] == node_id) for el in self.ordered_elements)

                # Add as a simple node event if it wasn't part of a processed definition/connection
                # We primarily care about the *definitions* and *connections* as events for animation build up.
                # Simple node IDs are implicitly added when their connections or definitions appear.


        # --- Final Cleanup ---
        # Ensure all nodes mentioned in connections or subgraphs are in self.nodes
        for conn in self.connections:
            self._add_node(conn['source'])
            self._add_node(conn['target'])
        for sg_name, node_list in self.subgraphs.items():
            for node_id in node_list:
                self._add_node(node_id)
                # Update node_to_subgraph mapping if missed
                if node_id not in self.node_to_subgraph:
                    self.node_to_subgraph[node_id] = sg_name

        return {
            'nodes': self.nodes,
            'connections': self.connections,
            'subgraphs': self.subgraphs,
            'node_to_subgraph': self.node_to_subgraph,
            'incoming': dict(self.incoming_connections),
            'outgoing': dict(self.outgoing_connections),
            'ordered_elements': self.ordered_elements # For animation
        }

    def generate_animation_sequence(self, output_dir):
        """Generate a sequence of Mermaid diagrams showing incremental building based on element order."""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Clear existing files
        for file in os.listdir(output_dir):
            if file.endswith('.mmd') or file == "README.md":
                try:
                    os.remove(os.path.join(output_dir, file))
                except OSError as e:
                    print(f"Error removing file {file}: {e}")

        frames = []
        visible_nodes = set()
        visible_connections = [] # Store connection dicts
        rendered_connection_lines = set() # Avoid duplicate connection lines

        # Frame 0: Just the declaration
        frames.append(self.declaration)

        # Iterate through the ordered elements (definitions and connections)
        for element in self.ordered_elements:
            new_frame_generated = False
            nodes_made_visible_this_step = set() # Track nodes added specifically in this step

            if element['type'] == 'node_definition':
                node_id = element['data']['id']
                if node_id not in visible_nodes:
                    visible_nodes.add(node_id)
                    nodes_made_visible_this_step.add(node_id)
                    new_frame_generated = True
            elif element['type'] == 'connection':
                conn = element['data']
                connection_line_key = conn['full_line'] # Use the originally parsed line

                # Add nodes involved in the connection if not already visible
                if conn['source'] not in visible_nodes:
                    visible_nodes.add(conn['source'])
                    nodes_made_visible_this_step.add(conn['source'])
                    new_frame_generated = True # Mark frame generation needed due to new node
                if conn['target'] not in visible_nodes:
                    visible_nodes.add(conn['target'])
                    nodes_made_visible_this_step.add(conn['target'])
                    new_frame_generated = True # Mark frame generation needed due to new node

                # Add the connection itself if it hasn't been added
                if connection_line_key not in rendered_connection_lines:
                    # Check if both nodes are now visible before adding connection data
                    if conn['source'] in visible_nodes and conn['target'] in visible_nodes:
                         visible_connections.append(conn)
                         rendered_connection_lines.add(connection_line_key)
                         new_frame_generated = True # Mark frame generation needed due to new connection

            # Generate a frame *if* something relevant changed (node added or connection added)
            if new_frame_generated:
                current_content = [self.declaration]
                current_node_defs = []
                current_connections = []
                subgraph_sections = [] # Store subgraph blocks as strings

                # 1. Add Node Definitions for ALL currently visible nodes
                #    Place definitions before connections and subgraphs for clarity
                #    Use OrderedDict behavior of self.nodes to keep definition order somewhat stable
                visible_node_list_ordered = [nid for nid in self.nodes if nid in visible_nodes]
                for node_id in visible_node_list_ordered:
                    # Use the full definition string stored in self.nodes
                    node_definition = self.nodes[node_id]
                    # Add the definition line (could be full A[...] or just ID 'A' if no definition exists)
                    current_node_defs.append(f"    {node_definition}")

                # 2. Add Visible Connections
                for conn in visible_connections:
                    # Double check nodes are visible (should be guaranteed by logic above)
                    if conn['source'] in visible_nodes and conn['target'] in visible_nodes:
                        conn_str = f"    {conn['source']} {conn['type']}"
                        if conn['label']:
                            conn_str += f"|{conn['label']}|"
                        conn_str += f" {conn['target']}"
                        # Ensure we don't add the exact same connection line twice in a frame
                        if conn_str not in current_connections:
                             current_connections.append(conn_str) # Indent for readability


                # 3. Add Subgraphs - list ONLY node IDs inside
                # Use OrderedDict behavior of self.subgraphs if needed
                for subgraph_name, original_node_list in self.subgraphs.items():
                    # Filter original_node_list to include only nodes currently visible
                    visible_in_subgraph = [
                        node_id for node_id in original_node_list
                        if node_id in visible_nodes
                    ]

                    if visible_in_subgraph:
                        subgraph_lines = []
                        subgraph_lines.append(f"    subgraph {subgraph_name}")
                        for node_id in visible_in_subgraph:
                            # IMPORTANT: List only the node ID inside the subgraph block
                            subgraph_lines.append(f"        {node_id}")
                        subgraph_lines.append(f"    end")
                        subgraph_sections.append("\n".join(subgraph_lines))

                # Assemble the frame content
                current_content.extend(current_node_defs)
                current_content.extend(current_connections)
                current_content.extend(subgraph_sections)

                # Add the generated frame only if it's different from the last one
                # (prevents duplicate frames if only hidden nodes were added)
                new_frame_content_str = "\n".join(current_content)
                if not frames or new_frame_content_str != frames[-1]:
                     frames.append(new_frame_content_str)


        # --- Write frames to files ---
        num_frames = len(frames)
        # Check if the output directory exists, create if not (redundant check, but safe)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for i, frame_content in enumerate(frames):
            frame_num = i + 1 # Use 1-based indexing for filenames
            filename = f"frame_{frame_num:03d}.mmd" # Padded for sorting
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w') as f:
                f.write(frame_content)

        # --- Create README with all frames ---
        readme_path = os.path.join(output_dir, "README.md")
        with open(readme_path, 'w') as f:
            f.write("# Mermaid Flowchart Animation\n\n")
            f.write(f"Generated {num_frames} frames.\n\n")

            for i, frame_content in enumerate(frames):
                frame_num = i + 1
                f.write(f"## Frame {frame_num}\n\n")
                f.write("```mermaid\n")
                f.write(frame_content)
                f.write("\n```\n\n")

        print(f"Generated {num_frames} animation frames in '{output_dir}'")
        print(f"Created README.md with all frames in '{output_dir}'")

        return num_frames


# Example usage:
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python your_script_name.py <input_mermaid_file> [output_directory]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "animation_frames"

    if not os.path.exists(input_file):
        print(f"Error: Input file not found at '{input_file}'")
        sys.exit(1)

    parser = MermaidFlowchartParser()
    try:
        parsed_data = parser.parse_file(input_file)
        print(f"Parsing complete. Found {len(parsed_data['nodes'])} nodes, {len(parsed_data['connections'])} connections, {len(parsed_data['subgraphs'])} subgraphs.")
        frames_generated = parser.generate_animation_sequence(output_dir)
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)