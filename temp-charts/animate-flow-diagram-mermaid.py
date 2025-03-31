# -*- coding: utf-8 -*-
"""
Mermaid Flowchart Parser and Animator

Parses a Mermaid flowchart (.mmd) file and generates a sequence of 
.mmd files representing the incremental build-up of the flowchart,
suitable for creating animations. Each frame attempts to add a single 
node or a single connection.
"""

import re
import os
import sys
import traceback
from collections import defaultdict, OrderedDict

class MermaidFlowchartParser:
    def __init__(self):
        """Initializes the parser with necessary attributes and regex patterns."""
        self.nodes = OrderedDict()  # Stores Node ID -> Full definition string or just ID
        self.connections = []       # Stores a list of connection dictionaries (raw parsed data)
        self.subgraphs = OrderedDict() # Stores Subgraph Name -> List of Node IDs originally listed
        self.node_to_subgraph = {}  # Maps Node ID -> Subgraph Name
        self.incoming_connections = defaultdict(list) # Maps Target Node -> List of incoming connections
        self.outgoing_connections = defaultdict(list) # Maps Source Node -> List of outgoing connections
        self.declaration = ""       # Stores the first line (e.g., "flowchart TD")

        # --- Regex Patterns ---
        # Node definition ANYWHERE on the line, e.g., A[Description] or B(Shape) or C{Database}
        # Correctly handles brackets, parentheses, and curly braces.
        self.node_def_anywhere_pattern = re.compile(
            r'([A-Za-z0-9_]+)((?:\[[^\]]*?\]|\([^)]*?\)|{[^}]*?})*)'
            # Uses non-greedy matching '[^\]]*?' etc. just in case, although greedy should also work.
            # The final '*' after the group allows matching nodes defined without brackets too,
            # but the check `if bracket_text:` in parse_content ensures we only use it when brackets exist.
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
        # Helper set to track nodes whose definition event has been added to ordered_elements (prevents duplicates during parsing)
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
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.parse_content(content)
        except FileNotFoundError:
            print(f"Error: Input file not found at '{filepath}'")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file '{filepath}': {e}")
            sys.exit(1)


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
        # Basic check for valid declaration (can be improved)
        if not (self.declaration.lower().startswith('flowchart') or self.declaration.lower().startswith('graph')):
             print(f"Warning: First line '{self.declaration}' might not be a standard Mermaid flowchart/graph declaration.")

        current_subgraph_name = None
        inside_subgraph_block = False

        # Process lines starting from the second line
        for line_num, line in enumerate(lines[1:], start=2):
            line_strip = line.strip()

            # Skip empty lines and pure comments
            if not line_strip or line_strip.startswith('%%'):
                continue

            # --- Step 1: Pre-scan the line for ANY node definitions (like A[Text]) ---
            definitions_on_line = self.node_def_anywhere_pattern.findall(line_strip)
            for node_id, bracket_text in definitions_on_line:
                # Make sure bracket_text actually contains brackets/parens/curlies
                if bracket_text and bracket_text[0] in "[({":
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
                   self.subgraphs[current_subgraph_name] = []
                inside_subgraph_block = True
                # Add subgraph start event maybe? For now, just track state.
                continue

            if self.subgraph_end_pattern.match(line_strip) and inside_subgraph_block:
                current_subgraph_name = None
                inside_subgraph_block = False
                # Add subgraph end event maybe?
                continue

            # --- Step 3: Process Connections and Simple Nodes (mostly within subgraphs) ---
            connections_found = self.connection_pattern.findall(line_strip)
            processed_as_connection = False
            if connections_found:
                processed_as_connection = True
                for source, connector, target in connections_found:
                    # Ensure nodes exist (add as simple ID if not already defined)
                    self._add_node(source)
                    self._add_node(target)

                    # Extract label if present
                    label = None
                    label_match = re.search(r'\|([^|]*)\|', connector)
                    if label_match: label = label_match.group(1)

                    # Determine connection type
                    conn_type = '-.->' if '-.' in connector else ('==>' if '==' in connector else '-->')

                    # Store connection details
                    connection = {
                        'source': source, 'target': target, 'type': conn_type,
                        'label': label, 'full_line': line_strip # Store original line for reference
                    }

                    # Avoid adding completely identical connection entries if a line somehow has duplicates
                    conn_tuple_for_check = (source, target, conn_type, label)
                    if not any(c['source'] == source and c['target'] == target and c['type'] == conn_type and c['label'] == label for c in self.connections):
                        self.connections.append(connection)
                        self.incoming_connections[target].append(connection)
                        self.outgoing_connections[source].append(connection)
                        # Add connection event for the animation sequence
                        self.ordered_elements.append({'type': 'connection', 'data': connection})

            # Check for simple node IDs (e.g., just 'A' on a line)
            # This handles nodes listed inside subgraph blocks
            if inside_subgraph_block and not processed_as_connection:
                simple_node_match = self.simple_node_pattern.match(line_strip)
                if simple_node_match:
                    node_id = simple_node_match.group(1)
                    self._add_node(node_id) # Add as simple ID if not known
                    if current_subgraph_name:
                         if node_id not in self.subgraphs[current_subgraph_name]:
                            self.subgraphs[current_subgraph_name].append(node_id)
                         self.node_to_subgraph[node_id] = current_subgraph_name
                    # Check if this simple node needs a definition event (if not already added)
                    if node_id not in self._definition_event_added:
                         # Add a definition event even for simple nodes if they haven't been defined
                         # This helps ensure they appear in the animation if only listed in subgraphs
                         self.ordered_elements.append({'type': 'node_definition', 'data': {'id': node_id, 'definition': node_id}})
                         self._definition_event_added.add(node_id)


        # --- Final Cleanup and Verification ---
        all_node_ids_mentioned = set()
        for conn in self.connections:
            all_node_ids_mentioned.add(conn['source'])
            all_node_ids_mentioned.add(conn['target'])
        for sg_name, node_list in self.subgraphs.items():
            for node_id in node_list:
                 all_node_ids_mentioned.add(node_id)
                 if node_id not in self.node_to_subgraph and sg_name:
                    self.node_to_subgraph[node_id] = sg_name
        for node_id in all_node_ids_mentioned:
            self._add_node(node_id) # Ensure all mentioned nodes are in self.nodes


        # --- De-duplicate ordered_elements to ensure clean animation sequence ---
        final_ordered_elements = []
        seen_element_keys = set() # Tracks unique keys like "def_A" or "conn_A->B"

        # Process definitions first to ensure nodes are known
        for elem in self.ordered_elements:
             if elem['type'] == 'node_definition':
                  node_id = elem['data']['id']
                  key = f"def_{node_id}"
                  if key not in seen_element_keys:
                      final_ordered_elements.append(elem)
                      seen_element_keys.add(key)

        # Then process connections
        for elem in self.ordered_elements:
             if elem['type'] == 'connection':
                  d = elem['data']
                  # Create a unique key for the connection content
                  key = f"conn_{d['source']}_{d['target']}_{d['type']}_{d['label']}"
                  if key not in seen_element_keys:
                      final_ordered_elements.append(elem)
                      seen_element_keys.add(key)

        self.ordered_elements = final_ordered_elements
        # --- End De-duplication ---


        return {
            'nodes': self.nodes, 'connections': self.connections, 'subgraphs': self.subgraphs,
            'node_to_subgraph': self.node_to_subgraph, 'incoming': dict(self.incoming_connections),
            'outgoing': dict(self.outgoing_connections), 'ordered_elements': self.ordered_elements
        }

    def _generate_frame_content(self, visible_nodes, visible_connections_set):
        """
        Helper function to generate the Mermaid string for a given state.
        Args:
            visible_nodes (set): Set of node IDs currently visible.
            visible_connections_set (set): Set of connection tuples (source, target, label, type) visible.
        Returns:
            str: The Mermaid diagram content for the frame.
        """
        current_content = [self.declaration]
        current_node_defs = []
        current_connections = []
        subgraph_sections = []

        # 1. Add Node Definitions for visible nodes
        processed_definitions = set() # Avoid duplicates within this frame
        # Iterate through self.nodes (OrderedDict) to try and maintain definition order
        for node_id in self.nodes:
            if node_id in visible_nodes:
                node_definition_str = self.nodes[node_id] # Get A or A[Text]
                if node_definition_str and node_definition_str not in processed_definitions:
                     current_node_defs.append(f"    {node_definition_str}")
                     processed_definitions.add(node_definition_str)

        # 2. Add Visible Connections from the set
        processed_connections_str = set() # Avoid duplicates within this frame
        # Sort the connection tuples for consistent output order
        sorted_connections = sorted(list(visible_connections_set))
        for source, target, label, conn_type in sorted_connections:
             # Safety check: Ensure nodes are actually visible
             if source in visible_nodes and target in visible_nodes:
                # Format the connection string
                conn_str = f"    {source} {conn_type}"
                if label: # Add label if it exists
                    conn_str += f"|{label}|"
                conn_str += f" {target}"
                # Add if not already added in this frame
                if conn_str not in processed_connections_str:
                    current_connections.append(conn_str)
                    processed_connections_str.add(conn_str)

        # 3. Add Subgraphs, listing only visible node IDs inside
        # Iterate through subgraphs in the order they were parsed (OrderedDict)
        for subgraph_name, original_node_list in self.subgraphs.items():
            # Find which nodes from this subgraph's original list are currently visible
            visible_in_subgraph = [nid for nid in original_node_list if nid in visible_nodes]
            # If any nodes in this subgraph are visible, create the block
            if visible_in_subgraph:
                subgraph_lines = [f"    subgraph {subgraph_name}"]
                # List node IDs inside, sort for consistency
                subgraph_lines.extend(f"        {nid}" for nid in sorted(visible_in_subgraph))
                subgraph_lines.append(f"    end")
                subgraph_sections.append("\n".join(subgraph_lines))

        # --- Assemble frame content ---
        # Add sections in standard order, sort lists within sections for consistency
        current_content.extend(sorted(current_node_defs))
        current_content.extend(sorted(current_connections))
        current_content.extend(sorted(subgraph_sections)) # Sort subgraph blocks by name

        return "\n".join(current_content)

    def generate_animation_sequence(self, output_dir):
        """
        Generates a sequence of Mermaid diagrams (.mmd files and README.md)
        where each frame represents the addition of a single node or connection.
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: '{output_dir}'")
        else:
            # Clear existing files only if directory already exists
            print(f"Output directory exists: '{output_dir}'")
            print("Clearing existing frame files...")
            files_cleared = 0
            for file in os.listdir(output_dir):
                if file.endswith('.mmd') or file.lower() == "readme.md":
                    try: os.remove(os.path.join(output_dir, file)); files_cleared += 1
                    except OSError as e: print(f"  Warning: Could not remove file {file}: {e}")
            print(f"  Cleared {files_cleared} existing files.")


        frames = [] # Holds the content string of each frame
        visible_nodes = set() # Tracks node IDs currently visible
        # Tracks unique connections currently visible using tuples: (source, target, label, type)
        visible_connections_set = set()
        last_frame_content = None # Stores the content of the previously added frame

        # --- Frame 0: Just the declaration ---
        frames.append(self.declaration)
        last_frame_content = self.declaration

        # --- Generate Frames Step-by-Step based on ordered_elements ---
        print(f"Processing {len(self.ordered_elements)} elements for animation...")
        for element_index, element in enumerate(self.ordered_elements):
            made_visual_change = False # Did this element cause a state change needing a new frame?

            if element['type'] == 'node_definition':
                node_id = element['data']['id']
                # Check if this node is appearing for the first time
                if node_id not in visible_nodes:
                    visible_nodes.add(node_id)
                    made_visual_change = True
                    # --- Generate Frame: Node Appeared ---
                    current_frame_content = self._generate_frame_content(visible_nodes, visible_connections_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content)
                        last_frame_content = current_frame_content
                    # ---

            elif element['type'] == 'connection':
                conn_data = element['data']
                source = conn_data['source']
                target = conn_data['target']
                label = conn_data['label']
                conn_type = conn_data['type']
                # Unique identifier for the connection content
                connection_tuple = (source, target, label, conn_type)

                # Step A: Ensure Source Node is Visible
                if source not in visible_nodes:
                    visible_nodes.add(source)
                    made_visual_change = True
                    # --- Generate Frame: Source Node Appeared ---
                    current_frame_content = self._generate_frame_content(visible_nodes, visible_connections_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content)
                        last_frame_content = current_frame_content
                    # ---

                # Step B: Ensure Target Node is Visible
                if target not in visible_nodes:
                    visible_nodes.add(target)
                    made_visual_change = True
                    # --- Generate Frame: Target Node Appeared ---
                    current_frame_content = self._generate_frame_content(visible_nodes, visible_connections_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content)
                        last_frame_content = current_frame_content
                    # ---

                # Step C: Ensure Connection Line is Visible (only if nodes are visible)
                if connection_tuple not in visible_connections_set and \
                   source in visible_nodes and target in visible_nodes:
                   # Check again if nodes are visible before adding connection
                    visible_connections_set.add(connection_tuple)
                    made_visual_change = True
                    # --- Generate Frame: Connection Appeared ---
                    current_frame_content = self._generate_frame_content(visible_nodes, visible_connections_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content)
                        last_frame_content = current_frame_content
                    # ---

            # Debug print (optional)
            # if made_visual_change:
            #     print(f"  Element {element_index+1}: {element['type']} caused Frame {len(frames)}")

        # --- Write Generated Frames to Files ---
        num_frames = len(frames)
        print(f"\nGenerating {num_frames} frame files...")

        # Write individual .mmd frame files
        for i, frame_content in enumerate(frames):
            frame_num = i + 1
            filename = f"image_{frame_num}.mmd" # Padded frame number
            filepath = os.path.join(output_dir, filename)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(frame_content)
            except IOError as e:
                 print(f"  Error writing file {filepath}: {e}")

        # --- Create README.md file containing all frames ---
        readme_path = os.path.join(output_dir, "README.md")
        print(f"Generating README.md at {readme_path}...")
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
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
        return num_frames


# --- Main execution block (handles command-line arguments) ---
if __name__ == "__main__":
    # Basic argument parsing
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print("\nUsage: python mermaid_animator.py <input_mermaid_file> [--output-dir <output_directory>]")
        print("\nArguments:")
        print("  <input_mermaid_file>   Path to the input .mmd file.")
        print("  --output-dir <dir>     Optional. Directory to save frame files and README.md.")
        print("                         Defaults to 'animation_frames' in the current directory.")
        sys.exit(0)

    input_file = sys.argv[1]
    output_dir = "animation_frames" # Default output

    # Handle optional --output-dir argument
    if "--output-dir" in sys.argv:
        try:
            output_dir_index = sys.argv.index("--output-dir") + 1
            if output_dir_index < len(sys.argv):
                output_dir = sys.argv[output_dir_index]
            else:
                # Ensure the flag isn't the very last argument
                print("Error: --output-dir option requires a directory path.")
                sys.exit(1)
        except ValueError:
             # This case should be unlikely if .index worked, but handles potential edge cases
             print("Error parsing --output-dir argument.")
             sys.exit(1)

    # --- Input File Validation ---
    if not os.path.isfile(input_file):
        print(f"Error: Input file not found or is not a file: '{input_file}'")
        sys.exit(1)

    # --- Instantiate Parser and Run ---
    parser = MermaidFlowchartParser()
    try:
        print(f"Parsing Mermaid file: '{input_file}'...")
        parsed_data = parser.parse_file(input_file) # Calls parse_content internally
        print("Parsing complete.")
        print(f"  Found {len(parsed_data['nodes'])} unique nodes.")
        print(f"  Found {len(parsed_data['connections'])} unique connection definitions.")
        print(f"  Found {len(parsed_data['subgraphs'])} subgraphs.")
        print(f"  Found {len(parsed_data['ordered_elements'])} elements for animation sequence.")

        # Generate the animation sequence
        print(f"\nGenerating animation sequence in directory: '{output_dir}'...")
        frames_generated = parser.generate_animation_sequence(output_dir)

    except Exception as e:
        # Catch-all for unexpected errors during parsing or generation
        print(f"\n--- An error occurred during processing ---")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")
        print("\n--- Traceback ---")
        traceback.print_exc()
        print("-----------------")
        sys.exit(1) # Exit with an error code

    print("\nScript finished successfully.")