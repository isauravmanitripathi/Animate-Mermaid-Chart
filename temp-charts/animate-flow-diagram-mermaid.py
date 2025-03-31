import re
import os
import sys
import traceback
from collections import defaultdict, OrderedDict

class MermaidFlowchartParser:
    def __init__(self):
        """Initializes the parser with necessary attributes and regex patterns."""
        self.nodes = OrderedDict()  # Stores Node ID -> Full definition string or just ID
        self.connections = []       # Stores a list of connection dictionaries
        self.subgraphs = OrderedDict() # Stores Subgraph Name -> List of Node IDs originally listed
        self.node_to_subgraph = {}  # Maps Node ID -> Subgraph Name
        self.incoming_connections = defaultdict(list) # Maps Target Node -> List of incoming connections
        self.outgoing_connections = defaultdict(list) # Maps Source Node -> List of outgoing connections
        self.declaration = ""       # Stores the first line (e.g., "flowchart TD")

        # --- Regex Patterns ---
        # Node definition ANYWHERE on the line, e.g., A[Description] or B(Shape) or C{Database}
        self.node_def_anywhere_pattern = re.compile(
            r'([A-Za-z0-9_]+)((?:\[[^\]]*\]|\([^)]*\)|{[^}]*})*)' # Captures ID and brackets/parens/curlies content
        )
        # Node definition specifically at the START of a line (less critical with the 'anywhere' pattern but can be a fallback)
        self.node_def_start_pattern = re.compile(
            r'^\s*([A-Za-z0-9_]+)((?:\[[^\]]*\]|\([^)]*\)|{[^}]*})).*$'
        )
        # Just a node ID on a line (often in subgraphs), optional comment
        self.simple_node_pattern = re.compile(
            r'^\s*([A-Za-z0-9_]+)\s*(?:%%.*)?$'
        )
        # Connections like A --> B or A -.->|Label| B
        self.connection_pattern = re.compile(
            r'([A-Za-z0-9_]+)\s+((?:-->|-.->|==>|===>)(?:\|[^|]*\|)?)\s+([A-Za-z0-9_]+)'
        )
        # Subgraph start and end lines
        self.subgraph_start_pattern = re.compile(r'^\s*subgraph\s+(.*)$')
        self.subgraph_end_pattern = re.compile(r'^\s*end\s*$')

        # --- Animation Specific ---
        # Stores the sequence of elements (definitions, connections) in the order they are parsed
        self.ordered_elements = []
        # Helper set to track nodes whose definition event has been added to ordered_elements (prevents duplicates)
        self._definition_event_added = set()


    def _add_node(self, node_id, definition=None):
        """
        Helper function to add or update a node in the self.nodes dictionary.
        Prioritizes keeping the full definition (like A[Text]) over just the ID (A).
        """
        # Only update if the new definition is more complete than the existing one
        if node_id not in self.nodes or (definition and self.nodes[node_id] == node_id):
            self.nodes[node_id] = definition if definition else node_id
        # If a definition already exists, don't overwrite it with just the ID
        elif definition is None and node_id not in self.nodes:
             self.nodes[node_id] = node_id


    def parse_file(self, filepath):
        """Reads a Mermaid file and initiates parsing."""
        with open(filepath, 'r') as f:
            content = f.read()
        return self.parse_content(content)

    def parse_content(self, content):
        """
        Parses the Mermaid flowchart content line by line.
        Identifies the declaration, nodes (with definitions), connections, and subgraphs.
        Builds the internal state (nodes, connections, subgraphs, ordered_elements).
        """
        lines = content.strip().split('\n')

        # --- Reset parser state for potentially parsing multiple contents ---
        self.declaration = ""
        self.nodes = OrderedDict()
        self.connections = []
        self.subgraphs = OrderedDict()
        self.node_to_subgraph = {}
        self.incoming_connections = defaultdict(list)
        self.outgoing_connections = defaultdict(list)
        self.ordered_elements = []
        self._definition_event_added = set()
        # --- End Reset ---

        if not lines:
            raise ValueError("Input content is empty.")

        # Extract declaration (first line)
        self.declaration = lines[0].strip()
        if not (self.declaration.lower().startswith('flowchart') or self.declaration.lower().startswith('graph')):
             print(f"Warning: First line '{self.declaration}' might not be a valid Mermaid declaration.")

        current_subgraph_name = None
        inside_subgraph_block = False

        # Process lines starting from the second line
        for line_num, line in enumerate(lines[1:], start=2):
            line_strip = line.strip()

            # Skip empty lines and pure comments
            if not line_strip or line_strip.startswith('%%'):
                continue

            # --- Step 1: Pre-scan the line for ANY node definitions (like A[Text]) ---
            # This ensures definitions are captured even if they appear within connection lines.
            definitions_on_line = self.node_def_anywhere_pattern.findall(line_strip)
            for node_id, bracket_text in definitions_on_line:
                # Check if bracket_text is not empty (pattern might match ID even without brackets if not careful)
                if bracket_text: # Ensures it found [...] or (...) or {...}
                    full_def = node_id + bracket_text
                    self._add_node(node_id, full_def) # Update self.nodes
                    # Add a 'node_definition' event to the ordered list *once* per node ID
                    if node_id not in self._definition_event_added:
                        self.ordered_elements.append({'type': 'node_definition', 'data': {'id': node_id, 'definition': full_def}})
                        self._definition_event_added.add(node_id)

            # --- Step 2: Handle Subgraph Start/End Markers ---
            subgraph_start_match = self.subgraph_start_pattern.match(line_strip)
            if subgraph_start_match:
                current_subgraph_name = subgraph_start_match.group(1).strip()
                if current_subgraph_name not in self.subgraphs:
                   self.subgraphs[current_subgraph_name] = [] # Initialize list for nodes in this subgraph
                inside_subgraph_block = True
                continue # Move to next line, don't process this line further

            if self.subgraph_end_pattern.match(line_strip) and inside_subgraph_block:
                current_subgraph_name = None # Exited subgraph block
                inside_subgraph_block = False
                continue # Move to next line

            # --- Step 3: Process Connections and Simple Nodes (mostly within subgraphs) ---

            # Check for connections (A --> B, etc.)
            connections_found = self.connection_pattern.findall(line_strip)
            processed_as_connection = False
            if connections_found:
                processed_as_connection = True
                for source, connector, target in connections_found:
                    # Ensure nodes involved exist in self.nodes (add as simple ID if not already defined)
                    self._add_node(source)
                    self._add_node(target)

                    # Extract label if present (e.g., |Label|)
                    label = None
                    label_match = re.search(r'\|([^|]*)\|', connector)
                    if label_match:
                        label = label_match.group(1)

                    # Determine connection type (simple check for now)
                    conn_type = '-.->' if '-.' in connector else '-->'

                    # Store connection details
                    connection = {
                        'source': source,
                        'target': target,
                        'type': conn_type,
                        'label': label,
                        'full_line': line_strip # Store original line for reference/uniqueness
                    }
                    # Avoid adding duplicate connection objects (simple check)
                    if connection not in self.connections:
                        self.connections.append(connection)
                        self.incoming_connections[target].append(connection)
                        self.outgoing_connections[source].append(connection)
                        # Add connection event for the animation sequence
                        self.ordered_elements.append({'type': 'connection', 'data': connection})

            # Check for simple node IDs (e.g., just 'A' on a line)
            # Primarily useful when inside a subgraph block and the line wasn't a connection
            if inside_subgraph_block and not processed_as_connection:
                simple_node_match = self.simple_node_pattern.match(line_strip)
                if simple_node_match:
                    node_id = simple_node_match.group(1)
                    self._add_node(node_id) # Add as simple ID if not already fully defined
                    # Add to the current subgraph's list and the node-to-subgraph map
                    if current_subgraph_name and node_id not in self.subgraphs[current_subgraph_name]:
                       self.subgraphs[current_subgraph_name].append(node_id)
                    if current_subgraph_name:
                       self.node_to_subgraph[node_id] = current_subgraph_name
                    # Note: We don't typically add a separate 'simple_node' event to ordered_elements,
                    # as node visibility for animation is usually triggered by definitions or connections.

        # --- Final Cleanup and Verification ---
        # Ensure all nodes mentioned in connections or listed in subgraphs exist in self.nodes
        all_node_ids_mentioned = set()
        for conn in self.connections:
            all_node_ids_mentioned.add(conn['source'])
            all_node_ids_mentioned.add(conn['target'])
        for sg_name, node_list in self.subgraphs.items():
            for node_id in node_list:
                 all_node_ids_mentioned.add(node_id)
                 # Ensure node_to_subgraph mapping is complete
                 if node_id not in self.node_to_subgraph and sg_name:
                    self.node_to_subgraph[node_id] = sg_name

        for node_id in all_node_ids_mentioned:
            self._add_node(node_id) # Add any missing nodes as simple IDs


        # --- De-duplicate ordered_elements ---
        # This ensures we process each unique definition once and each unique connection line once
        # in the animation generation, respecting the order found as much as possible.
        final_ordered_elements = []
        seen_elements_keys = set() # Tracks unique keys of elements added

        # Prioritize adding definitions first
        node_defs_added_to_final = set()
        for elem in self.ordered_elements:
             if elem['type'] == 'node_definition':
                  node_id = elem['data']['id']
                  if node_id not in node_defs_added_to_final:
                      final_ordered_elements.append(elem)
                      node_defs_added_to_final.add(node_id)
                      seen_elements_keys.add(f"def_{node_id}") # Mark definition as seen

        # Then add connections based on their full line content for uniqueness
        for elem in self.ordered_elements:
             if elem['type'] == 'connection':
                  conn_key = f"conn_{elem['data']['full_line']}" # Key based on original line
                  if conn_key not in seen_elements_keys:
                      final_ordered_elements.append(elem)
                      seen_elements_keys.add(conn_key) # Mark connection line as seen

        self.ordered_elements = final_ordered_elements
        # --- End De-duplication ---


        # Return the parsed data
        return {
            'nodes': self.nodes,
            'connections': self.connections,
            'subgraphs': self.subgraphs,
            'node_to_subgraph': self.node_to_subgraph,
            'incoming': dict(self.incoming_connections),
            'outgoing': dict(self.outgoing_connections),
            'ordered_elements': self.ordered_elements # The crucial sequence for animation
        }

    def generate_animation_sequence(self, output_dir):
        """
        Generates a sequence of Mermaid diagrams (.mmd files and README.md)
        showing the incremental building of the flowchart based on the
        order elements (definitions, connections) were parsed.
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: '{output_dir}'")
        else:
            print(f"Output directory exists: '{output_dir}'")


        # --- Clear existing frame files and README ---
        print("Clearing existing frame files...")
        files_cleared = 0
        for file in os.listdir(output_dir):
            if file.endswith('.mmd') or file.lower() == "readme.md":
                try:
                    os.remove(os.path.join(output_dir, file))
                    files_cleared += 1
                except OSError as e:
                    print(f"  Warning: Could not remove file {file}: {e}")
        print(f"  Cleared {files_cleared} existing files.")
        # --- End Clearing ---


        frames = [] # List to hold the content of each animation frame
        visible_nodes = set() # Tracks nodes currently visible in the animation
        visible_connections = [] # Stores connection dictionaries that are currently visible
        # Tracks the unique connection *lines* added to prevent duplicates in the output MMD
        rendered_connection_lines = set()

        # Frame 0: Just the flowchart declaration
        frames.append(self.declaration)

        # --- Generate Frames by Processing Ordered Elements ---
        for element_index, element in enumerate(self.ordered_elements):
            new_frame_generated = False # Flag to check if the current element causes a visual change

            # --- Update Visibility based on the current element ---
            if element['type'] == 'node_definition':
                # Definitions ensure the node text is known, but don't necessarily make the node visible yet.
                # Visibility is primarily driven by connections in this animation logic.
                # We already added the definition event during parsing.
                pass # No direct visibility change from definition alone

            elif element['type'] == 'connection':
                conn = element['data']
                connection_line_key = conn['full_line'] # Use original line for tracking uniqueness
                nodes_newly_added_this_step = False

                # If source node isn't visible, make it visible
                if conn['source'] not in visible_nodes:
                    visible_nodes.add(conn['source'])
                    nodes_newly_added_this_step = True

                # If target node isn't visible, make it visible
                if conn['target'] not in visible_nodes:
                    visible_nodes.add(conn['target'])
                    nodes_newly_added_this_step = True

                # If the connection line itself hasn't been rendered yet
                if connection_line_key not in rendered_connection_lines:
                    # Ensure both nodes are currently visible before adding the connection
                    if conn['source'] in visible_nodes and conn['target'] in visible_nodes:
                        visible_connections.append(conn) # Add connection data
                        rendered_connection_lines.add(connection_line_key) # Mark line as rendered
                        new_frame_generated = True # Connection added -> visual change

                # If nodes were newly added, even if connection existed, force frame generation
                elif nodes_newly_added_this_step:
                     new_frame_generated = True

            # --- Generate Frame Content if Visual Change Occurred ---
            if new_frame_generated:
                current_content = [self.declaration] # Start with the declaration
                current_node_defs = []
                current_connections = []
                subgraph_sections = []

                # 1. Add Node Definitions for ALL currently visible nodes
                #    Iterate through self.nodes to maintain a somewhat consistent order
                processed_definitions = set() # Prevent duplicate definition lines within *this* frame
                for node_id in self.nodes:
                    if node_id in visible_nodes:
                        node_definition_str = self.nodes[node_id] # Get A or A[Text]
                        # Add the definition string if it's not just the ID or if already added
                        if node_definition_str and node_definition_str not in processed_definitions:
                             current_node_defs.append(f"    {node_definition_str}")
                             processed_definitions.add(node_definition_str)

                # 2. Add Visible Connections
                processed_connections = set() # Prevent duplicate connection lines within *this* frame
                for conn_data in visible_connections:
                    # Double-check nodes are visible (should be true here)
                    if conn_data['source'] in visible_nodes and conn_data['target'] in visible_nodes:
                        # Format the connection line string
                        conn_str = f"    {conn_data['source']} {conn_data['type']}"
                        if conn_data['label']:
                            conn_str += f"|{conn_data['label']}|"
                        conn_str += f" {conn_data['target']}"
                        # Add the string if not already added in this frame
                        if conn_str not in processed_connections:
                             current_connections.append(conn_str)
                             processed_connections.add(conn_str)

                # 3. Add Subgraphs - list ONLY node IDs inside them
                # Iterate through subgraphs in the order they were parsed
                for subgraph_name, original_node_list in self.subgraphs.items():
                    # Find which nodes from this subgraph's original list are currently visible
                    visible_in_subgraph = [
                        node_id for node_id in original_node_list
                        if node_id in visible_nodes
                    ]
                    # If any nodes in this subgraph are visible, create the block
                    if visible_in_subgraph:
                        subgraph_lines = []
                        subgraph_lines.append(f"    subgraph {subgraph_name}")
                        for node_id in visible_in_subgraph:
                            # IMPORTANT: List only the node ID inside the subgraph block
                            subgraph_lines.append(f"        {node_id}")
                        subgraph_lines.append(f"    end")
                        subgraph_sections.append("\n".join(subgraph_lines))

                # --- Assemble the complete frame content ---
                # Sorting helps maintain consistency frame-to-frame if parsing order varies slightly
                current_content.extend(sorted(list(current_node_defs)))
                current_content.extend(sorted(list(current_connections)))
                current_content.extend(sorted(subgraph_sections)) # Sort subgraph blocks by name

                # Add the generated frame content string to our list of frames
                # Avoid adding identical consecutive frames
                new_frame_content_str = "\n".join(current_content)
                if not frames or new_frame_content_str != frames[-1]:
                     frames.append(new_frame_content_str)
                # --- End Frame Content Assembly ---

        # --- Write Generated Frames to Files ---
        num_frames = len(frames)
        print(f"Generating {num_frames} frame files...")

        # Write individual .mmd frame files
        for i, frame_content in enumerate(frames):
            frame_num = i + 1 # Use 1-based indexing for filenames
            # Pad frame number for better sorting (e.g., frame_001.mmd, frame_010.mmd)
            filename = f"image_{frame_num}.mmd"
            filepath = os.path.join(output_dir, filename)
            try:
                with open(filepath, 'w') as f:
                    f.write(frame_content)
            except IOError as e:
                 print(f"  Error writing file {filepath}: {e}")


        # Write the README.md file containing all frames
        readme_path = os.path.join(output_dir, "README.md")
        print(f"Generating README.md at {readme_path}...")
        try:
            with open(readme_path, 'w') as f:
                f.write("# Mermaid Flowchart Animation\n\n")
                f.write(f"Generated {num_frames} frames.\n\n")

                for i, frame_content in enumerate(frames):
                    frame_num = i + 1
                    f.write(f"## Frame {frame_num}\n\n")
                    f.write("```mermaid\n")
                    f.write(frame_content)
                    f.write("\n```\n\n")
            print("  README.md generated successfully.")
        except IOError as e:
            print(f"  Error writing README.md: {e}")

        print(f"\nGenerated {num_frames} animation frames in '{output_dir}'")
        print(f"Created README.md with all frames in '{output_dir}'")

        return num_frames


# --- Main execution block ---
if __name__ == "__main__":
    # --- Argument Parsing ---
    if len(sys.argv) < 2:
        print("Usage: python your_script_name.py <input_mermaid_file> [--output-dir <output_directory>]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = "animation_frames" # Default output directory

    # Basic handling for --output-dir argument
    if "--output-dir" in sys.argv:
        try:
            output_dir_index = sys.argv.index("--output-dir") + 1
            if output_dir_index < len(sys.argv):
                output_dir = sys.argv[output_dir_index]
            else:
                print("Error: --output-dir option requires a directory path.")
                sys.exit(1)
        except ValueError:
             # Should not happen if index() finds it, but good practice
             pass # Handled by initial check if < len(sys.argv)

    # --- File Existence Check ---
    if not os.path.isfile(input_file):
        print(f"Error: Input file not found or is not a file: '{input_file}'")
        sys.exit(1)

    # --- Parser Instantiation and Execution ---
    parser = MermaidFlowchartParser()
    try:
        print(f"Parsing Mermaid file: '{input_file}'...")
        parsed_data = parser.parse_file(input_file)
        print(f"Parsing complete.")
        print(f"  Found {len(parsed_data['nodes'])} unique nodes.")
        print(f"  Found {len(parsed_data['connections'])} connection definitions.")
        print(f"  Found {len(parsed_data['subgraphs'])} subgraphs.")
        print(f"  Found {len(parsed_data['ordered_elements'])} elements for animation sequence.")

        # --- Generate Animation ---
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