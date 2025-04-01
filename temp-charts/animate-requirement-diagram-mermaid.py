# -*- coding: utf-8 -*-
"""
Mermaid Requirement Diagram Parser and Animator v1.1 (SyntaxError Fixed)

Parses Mermaid 'requirementDiagram' definitions, including different
requirement/element types, properties, relationships, and styling
(classDef, class, :::styleClass).
Generates a sequence of .mmd files representing the granular, incremental
build-up of the diagram, suitable for creating animations.
Element visibility is driven by relationships appearing in the parsed order.
"""

import re
import os
import sys
import traceback
from collections import defaultdict, OrderedDict

class MermaidRequirementParser:
    def __init__(self):
        """Initializes the parser for Requirement Diagrams."""
        self.element_properties = OrderedDict() # Element ID -> Dict of properties {'keyword', 'id', 'text', 'risk', ...}
        self.node_styles = {}        # Element ID -> Style Class Name
        self.relationships_data = [] # Parsed relationship dicts: {'source', 'target', 'type'}
        self.class_definitions = OrderedDict() # Class Name -> Attribute string
        self.declaration = ""        # Stores "requirementDiagram"
        self.ordered_elements = []   # Sequence of unique {'type': '...', 'data': ...} events

        # --- Element Keywords ---
        self.requirement_keywords = {
            "requirement", "functionalRequirement", "interfaceRequirement",
            "performanceRequirement", "physicalRequirement", "designConstraint"
        }
        self.element_keyword = "element"
        self.all_element_keywords = self.requirement_keywords.union({self.element_keyword})

        # --- Relationship Keywords ---
        self.relationship_keywords = {
            "contains", "copies", "derives", "satisfies",
            "verifies", "refines", "traces"
        }

        # --- Regex Patterns ---
        # Matches any known element type keyword at the start
        self.element_type_keyword_pattern = re.compile(
            r'^\s*(' + '|'.join(self.all_element_keywords) + r')\s+'
        )
        # Captures: 1=Keyword, 2=ID/Name, 3=StyleClass (optional), 4=Properties inside {} (optional)
        self.element_definition_pattern = re.compile(
            r'^\s*(' + '|'.join(self.all_element_keywords) + r')\s+' # Keyword (Group 1)
            r'([\w_]+|"[^"]+")'                                  # ID or "Quoted Name" (Group 2)
            r'(?:::([A-Za-z0-9_]+))?'                             # Optional :::StyleClass (Group 3)
            r'(?:\s*\{\s*(.*?)\s*\})?'                             # Optional { properties } (Group 4), non-greedy
            r'\s*$'
        )
        # Parses properties inside {}, splitting by semicolon or newline
        self.property_pattern = re.compile(r'^\s*(\w+)\s*:\s*(.*?)\s*$') # Non-greedy value match

        # Relationships: source - type -> target or target <- type - source
        # Captures: 1=ID1, 2=RelType, 3=ID2 OR 4=ID1, 5=RelType, 6=ID2
        self.relationship_pattern = re.compile(
            r'^\s*([\w_]+|"[^"]+")\s+-\s*(' + '|'.join(self.relationship_keywords) + r')\s*->\s*([\w_]+|"[^"]+")\s*$|' # Grp 1,2,3
            r'^\s*([\w_]+|"[^"]+")\s+<-\s*(' + '|'.join(self.relationship_keywords) + r')\s*-\s*([\w_]+|"[^"]+")\s*$'  # Grp 4,5,6
        )

        # classDef ClassName attributes
        self.class_def_pattern = re.compile(r'^\s*classDef\s+([A-Za-z0-9_]+)\s+(.*)$')
        # class ElementId1,ElementId2 ClassName
        self.class_assign_pattern = re.compile(r'^\s*class\s+([A-Za-z0-9_,\s]+?)\s+([A-Za-z0-9_]+)\s*;?$')
        # --- End Regex ---


    def _add_element(self, element_id, properties=None, style_class=None):
        """Adds or updates element properties and style."""
        if not element_id or not isinstance(element_id, str): return
        element_id = element_id.strip().strip('"')
        if not element_id or element_id in self.class_definitions: return

        if element_id not in self.element_properties:
            self.element_properties[element_id] = {'id': element_id} # Basic entry if new

        # Update properties
        if properties:
            self.element_properties[element_id].update(properties)

        # Ensure keyword exists
        if 'keyword' not in self.element_properties[element_id]:
             # Infer keyword based on typical properties or default to 'requirement'
             props_check = properties if properties else {}
             inferred_keyword = 'element' if ('docRef' in props_check or 'type' in props_check) else 'requirement'
             self.element_properties[element_id]['keyword'] = inferred_keyword

        # Add style
        if style_class:
            self.node_styles[element_id] = style_class


    def parse_file(self, filepath):
        """Reads a Mermaid file and initiates parsing."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
            return self.parse_content(content)
        except FileNotFoundError: print(f"Error: Input file not found: '{filepath}'"); sys.exit(1)
        except Exception as e: print(f"Error reading file '{filepath}': {e}"); traceback.print_exc(); sys.exit(1)


    def parse_content(self, content):
        """Parses Mermaid requirementDiagram content line by line."""
        lines = content.strip().split('\n')
        self.__init__() # Reset state

        if not lines: raise ValueError("Input content is empty.")
        self.declaration = lines[0].strip()
        if not self.declaration.lower().startswith('requirementdiagram'):
             print(f"Warning: First line '{self.declaration}' does not start with 'requirementDiagram'.")

        temp_ordered_elements = [] # Collect raw events first
        _definition_event_added = set() # Track unique element defs added
        _ignore_ids = set() # Track class names

        for line_num, line in enumerate(lines[1:], start=2):
            line_strip = line.strip()
            if not line_strip or line_strip.startswith('%%'): continue

            # 1. Check for classDef
            class_def_match = self.class_def_pattern.match(line_strip)
            if class_def_match:
                name, attrs = class_def_match.groups(); attrs = attrs.strip().rstrip(';')
                self.class_definitions[name] = attrs; _ignore_ids.add(name)
                continue

            # 2. Check for class Assignment
            class_assign_match = self.class_assign_pattern.match(line_strip)
            if class_assign_match:
                id_list_str, class_name = class_assign_match.groups()
                element_ids = [eid.strip().strip('"') for eid in id_list_str.split(',') if eid.strip()]
                if class_name in self.class_definitions:
                    for eid in element_ids:
                        if eid and eid not in _ignore_ids:
                            self._add_element(eid) # Ensure element exists
                            self.node_styles[eid] = class_name
                else: print(f"Warning: Line {line_num}: Class '{class_name}' not defined.")
                continue

            # 3. Check for Element/Requirement Definition
            element_def_match = self.element_definition_pattern.match(line_strip)
            if element_def_match:
                keyword, element_id, style_class, props_str = element_def_match.groups()
                element_id = element_id.strip().strip('"')
                if element_id in _ignore_ids: continue

                properties = {'keyword': keyword}
                if props_str:
                    prop_lines = re.split(r'[;\n]', props_str)
                    for prop_line in prop_lines:
                        prop_match = self.property_pattern.match(prop_line)
                        if prop_match:
                            key, value = prop_match.groups()
                            key_lower = key.lower()
                            # Normalize common keys
                            if key_lower == "verifymethod": key = "verifyMethod"
                            elif key_lower == "docref": key = "docRef"
                            # Store cleaned value
                            properties[key] = value.strip().strip('"')

                self._add_element(element_id, properties, style_class)
                if element_id not in _definition_event_added:
                     temp_ordered_elements.append({'type': 'element_definition', 'data': {'id': element_id}})
                     _definition_event_added.add(element_id)
                continue # Handled as element definition

            # 4. Check for Relationships
            rel_match = self.relationship_pattern.match(line_strip)
            if rel_match:
                if rel_match.group(1): # Forward ->
                    source_id, rel_type, target_id = rel_match.group(1), rel_match.group(2), rel_match.group(3)
                else: # Backward <-
                    target_id, rel_type, source_id = rel_match.group(4), rel_match.group(5), rel_match.group(6)

                source_id = source_id.strip().strip('"'); target_id = target_id.strip().strip('"')
                rel_type = rel_type.strip()
                if source_id in _ignore_ids or target_id in _ignore_ids: continue

                self._add_element(source_id); self._add_element(target_id) # Ensure elements exist

                relationship_data = {'source': source_id, 'target': target_id, 'type': rel_type}
                self.relationships_data.append(relationship_data)
                temp_ordered_elements.append({'type': 'relationship', 'data': relationship_data})
                continue

            # Handle potential simple node IDs if needed (less common in req diagrams)
            # simple_match = self.simple_node_pattern.match(line_strip)
            # if simple_match:
            #     node_id = simple_match.group(1)
            #     if node_id and node_id not in _ignore_ids:
            #         self._add_element(node_id)
            #         if node_id not in _definition_event_added:
            #              temp_ordered_elements.append({'type': 'element_definition', 'data': {'id': node_id}})
            #              _definition_event_added.add(node_id)


        # --- Final Cleanup & De-duplication ---
        all_element_ids = set(self.element_properties.keys())
        for rel in self.relationships_data: all_element_ids.update([rel['source'], rel['target']])
        for eid in all_element_ids:
            if eid not in _ignore_ids: self._add_element(eid) # Ensure all mentioned valid elements exist

        seen_element_keys = set()
        for elem in temp_ordered_elements:
            key = None
            if elem['type'] == 'element_definition': key = f"def_{elem['data']['id']}"
            elif elem['type'] == 'relationship':
                d = elem['data']; key = f"rel_{d['source']}_{d['target']}_{d['type']}"
            if key and key not in seen_element_keys:
                self.ordered_elements.append(elem)
                seen_element_keys.add(key)

        return {
            'element_properties': self.element_properties, 'node_styles': self.node_styles,
            'relationships_data': self.relationships_data, 'class_definitions': self.class_definitions,
            'ordered_elements': self.ordered_elements
        }

    def _generate_frame_content(self, visible_elements, visible_relationships_set):
        """Helper function generates Mermaid Requirement Diagram string for a frame."""
        content_lines = [self.declaration]

        # Add Class Definitions
        if self.class_definitions: content_lines.append("\n    %% Class Definitions")
        for name, attrs in self.class_definitions.items(): content_lines.append(f"    classDef {name} {attrs}")

        # Add Element/Requirement Definitions
        element_def_lines = []
        processed_elements = set()
        if visible_elements: content_lines.append("\n    %% Elements & Requirements")
        # Sort elements for consistent output order
        for element_id in sorted(list(visible_elements)):
            if element_id in self.element_properties and element_id not in processed_elements:
                props = self.element_properties[element_id]
                keyword = props.get('keyword', 'requirement') # Default if keyword missing somehow
                style_class = self.node_styles.get(element_id)

                # Construct properties string inside {}
                props_str_parts = []
                # Define a standard order for properties for consistency
                prop_order = ['id', 'text', 'risk', 'verifyMethod', 'type', 'docRef']
                for key in prop_order:
                    if key in props:
                        value = props[key]
                        # Use triple quotes for f-string for text/type/docRef which need quotes in output
                        if key in ['text', 'type', 'docRef']:
                            # Basic internal quote escaping for the value itself
                            safe_value = str(value).replace('"', '\\"')
                            props_str_parts.append(f"""{key}: "{safe_value}\"""") # CORRECTED f-string
                        else:
                             props_str_parts.append(f"{key}: {value}")

                props_str = ""
                if props_str_parts: props_str = f" {{ {'; '.join(props_str_parts)} }}"

                # Quote element ID if it contains spaces or special chars (basic check)
                quoted_id = f'"{element_id}"' if re.search(r'\s', element_id) else element_id
                def_line = f"    {keyword} {quoted_id}{f':::{style_class}' if style_class else ''}{props_str}"
                element_def_lines.append(def_line)
                processed_elements.add(element_id)
        content_lines.extend(element_def_lines) # Already sorted by element_id

        # Add Relationships
        relationship_lines = []
        processed_rels_str = set()
        if visible_relationships_set: content_lines.append("\n    %% Relationships")
        # Sort relationships for consistent output order
        sorted_relationships = sorted(list(visible_relationships_set))
        for source, target, rel_type in sorted_relationships:
            if source in visible_elements and target in visible_elements:
                # Quote IDs if they contain spaces
                q_source = f'"{source}"' if ' ' in source else source
                q_target = f'"{target}"' if ' ' in target else target
                rel_str = f"    {q_source} - {rel_type} -> {q_target}"
                if rel_str not in processed_rels_str:
                    relationship_lines.append(rel_str)
                    processed_rels_str.add(rel_str)
        content_lines.extend(relationship_lines) # Already sorted

        # Add class assignments (alternative to :::)
        class_assignments = defaultdict(list)
        # Check which styles were *not* applied via :::
        for element_id, style_class in self.node_styles.items():
             if element_id in visible_elements:
                # Check if the definition line for this element already includes :::style_class
                props = self.element_properties.get(element_id, {})
                keyword = props.get('keyword', 'requirement')
                quoted_id = f'"{element_id}"' if ' ' in element_id else element_id
                approx_def_line_start = f"    {keyword} {quoted_id}"
                found_with_colon = False
                for def_line in element_def_lines:
                     if def_line.strip().startswith(approx_def_line_start) and f":::{style_class}" in def_line:
                          found_with_colon = True
                          break
                if not found_with_colon:
                     class_assignments[style_class].append(element_id)

        if any(class_assignments.values()): content_lines.append("\n    %% Class Assignments (if not using :::)")
        for style_class, elements in sorted(class_assignments.items()):
            elements.sort()
            quoted_elements = [f'"{eid}"' if ' ' in eid else eid for eid in elements]
            content_lines.append(f"    class {','.join(quoted_elements)} {style_class}")


        return "\n".join(content_lines)


    def generate_animation_sequence(self, output_dir):
        """Generates granular animation frames for Requirement Diagrams."""
        # --- Setup and Clearing ---
        if not os.path.exists(output_dir): os.makedirs(output_dir); print(f"Created directory: '{output_dir}'")
        else:
            print(f"Clearing existing files in '{output_dir}'..."); files_cleared = 0
            for file in os.listdir(output_dir):
                if file.endswith('.mmd') or file.lower() == "readme.md":
                    try: os.remove(os.path.join(output_dir, file)); files_cleared += 1
                    except OSError as e: print(f"  Warn: Could not remove {file}: {e}")
            print(f"  Cleared {files_cleared} files.")

        frames = []; visible_elements = set(); visible_relationships_set = set(); last_frame_content = None

        # --- Frame 1: Declaration + ClassDefs ---
        initial_content_list = [self.declaration]
        if self.class_definitions: initial_content_list.append("\n    %% Class Definitions")
        initial_content_list.extend(f"    classDef {name} {attrs}" for name, attrs in self.class_definitions.items())
        initial_frame_str = "\n".join(initial_content_list); frames.append(initial_frame_str); last_frame_content = initial_frame_str
        print(f"Frame 1: Initial Declaration and ClassDefs added.")

        # --- Generate Frames Step-by-Step ---
        print(f"Processing {len(self.ordered_elements)} elements...")
        frame_counter = 1
        elements_defined_but_not_visible = set(elem['data']['id'] for elem in self.ordered_elements if elem['type'] == 'element_definition')
        relationships_processed_visually = set()

        for element_index, element in enumerate(self.ordered_elements):
            if element['type'] == 'relationship':
                rel_data = element['data']
                source, target, rel_type = rel_data['source'], rel_data['target'], rel_data['type']
                relationship_tuple = (source, target, rel_type)

                if relationship_tuple in relationships_processed_visually: continue

                # Ensure elements exist (safety check)
                if source not in self.element_properties or target not in self.element_properties:
                    # print(f"Warning: Skipping relationship element {element_index+1} due to missing element definition for {source} or {target}")
                    continue # Skip if element data isn't parsed

                # Step A: Ensure Source Visible
                if source not in visible_elements:
                    visible_elements.add(source)
                    elements_defined_but_not_visible.discard(source)
                    current_frame_content = self._generate_frame_content(visible_elements, visible_relationships_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content); last_frame_content = current_frame_content; frame_counter += 1

                # Step B: Ensure Target Visible
                if target not in visible_elements:
                    visible_elements.add(target)
                    elements_defined_but_not_visible.discard(target)
                    current_frame_content = self._generate_frame_content(visible_elements, visible_relationships_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content); last_frame_content = current_frame_content; frame_counter += 1

                # Step C: Ensure Relationship Visible
                if relationship_tuple not in visible_relationships_set and source in visible_elements and target in visible_elements:
                    visible_relationships_set.add(relationship_tuple)
                    relationships_processed_visually.add(relationship_tuple)
                    current_frame_content = self._generate_frame_content(visible_elements, visible_relationships_set)
                    if current_frame_content != last_frame_content:
                        frames.append(current_frame_content); last_frame_content = current_frame_content; frame_counter += 1

            elif element['type'] == 'element_definition':
                 # Processed during parsing, visibility handled by connections or at the end
                 pass

        # --- Add any remaining defined but unconnected elements ---
        if elements_defined_but_not_visible:
             print(f"Adding {len(elements_defined_but_not_visible)} unconnected elements...")
             made_final_change = False
             for element_id in sorted(list(elements_defined_but_not_visible)):
                  if element_id not in visible_elements:
                       visible_elements.add(element_id)
                       made_final_change = True
             if made_final_change:
                  current_frame_content = self._generate_frame_content(visible_elements, visible_relationships_set)
                  if current_frame_content != last_frame_content:
                      frames.append(current_frame_content); last_frame_content = current_frame_content; frame_counter += 1
                      print(f"  Added final frame for unconnected elements (Frame {frame_counter}).")

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

        readme_path = os.path.join(output_dir, "README.md")
        print(f"Generating README.md at {readme_path}...")
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"# Mermaid Requirement Diagram Animation ({os.path.basename(input_file)})\n\n")
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
        print("\nParses Mermaid Requirement Diagrams and generates animation frames.")
        print("\nArguments:")
        print("  <input_mermaid_file>   Path to the input .mmd file (must start with requirementDiagram).")
        print("  --output-dir <dir>     Optional. Directory to save frames and README.md.")
        print("                         Defaults to 'requirement_animation_frames'.")
        sys.exit(0)

    input_file = sys.argv[1]
    output_dir = "requirement_animation_frames"
    if "--output-dir" in sys.argv:
        try:
            idx = sys.argv.index("--output-dir") + 1
            if idx < len(sys.argv): output_dir = sys.argv[idx]
            else: print("Error: --output-dir requires path."); sys.exit(1)
        except ValueError: print("Error parsing arguments."); sys.exit(1)

    if not os.path.isfile(input_file):
        print(f"Error: Input file not found: '{input_file}'"); sys.exit(1)

    parser = MermaidRequirementParser() # Using the requirement parser class
    try:
        print(f"Parsing Mermaid requirement diagram file: '{input_file}'...")
        parsed_data = parser.parse_file(input_file)
        print("Parsing complete.")
        print(f"  Declaration: {parser.declaration}")
        print(f"  Found {len(parsed_data['element_properties'])} unique elements/requirements.")
        print(f"  Found {len(parsed_data['relationships_data'])} relationship instances parsed.")
        print(f"  Found {len(parsed_data['class_definitions'])} class definitions.")
        print(f"  Found {len(parsed_data['ordered_elements'])} unique elements/relationships for animation sequence.")

        print(f"\nGenerating animation sequence in directory: '{output_dir}'...")
        frames_generated = parser.generate_animation_sequence(output_dir)

    except Exception as e:
        print(f"\n--- An error occurred ---"); print(f"Error: {type(e).__name__}: {e}")
        print("\n--- Traceback ---"); traceback.print_exc(); print("-----------------")
        sys.exit(1)

    print("\nScript finished successfully.")