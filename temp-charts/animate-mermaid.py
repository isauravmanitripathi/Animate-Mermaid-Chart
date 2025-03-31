import re
import os
import argparse
from collections import OrderedDict

class MermaidSequencer:
    def __init__(self, input_file=None, output_dir=None, diagram_type=None):
        self.input_file = input_file
        self.output_dir = output_dir or 'sequence_output'
        self.diagram_type = diagram_type or 'classDiagram'
        self.full_content = ""
        self.sections = OrderedDict()
        
    def load_file(self, file_path=None):
        """Load a Mermaid diagram file"""
        if file_path:
            self.input_file = file_path
            
        if not self.input_file:
            raise ValueError("No input file specified")
            
        with open(self.input_file, 'r') as f:
            self.full_content = f.read()
            
        print(f"Loaded file: {self.input_file}")
        return self.full_content
        
    def _detect_diagram_type(self):
        """Auto-detect the Mermaid diagram type from content"""
        first_line = self.full_content.strip().split('\n')[0].strip()
        if first_line in [
            'classDiagram', 'flowchart', 'sequenceDiagram', 
            'stateDiagram', 'erDiagram', 'gantt', 'pie',
            'journey', 'gitGraph'
        ]:
            self.diagram_type = first_line
            print(f"Detected diagram type: {self.diagram_type}")
        return self.diagram_type
        
    def parse_class_diagram(self):
        """Parse a class diagram into sections"""
        # Clean up any whitespace at the beginning
        content = self.full_content.strip()
        
        # Make sure we're working with a class diagram
        if not content.startswith('classDiagram'):
            raise ValueError("This is not a class diagram. Please specify the correct diagram type.")
            
        # Remove the first line (classDiagram declaration)
        content = re.sub(r'^classDiagram\s*\n', '', content)
        
        # Parse classes
        class_pattern = r'class\s+(\w+)\s+{[^}]*}'
        classes = re.findall(class_pattern, content)
        self.sections['classes'] = {}
        
        for i, class_name in enumerate(classes):
            class_content = re.search(f'class\\s+{class_name}\\s+{{([^}}]*?)}}', content).group(0)
            self.sections['classes'][class_name] = {
                'content': class_content,
                'order': i + 1
            }
            
        # Parse relationships
        relation_pattern = r'(\w+)\s+-->\s+(\w+)'
        relations = re.findall(relation_pattern, content)
        self.sections['relations'] = []
        
        for from_class, to_class in relations:
            relation_text = f"{from_class} --> {to_class}"
            self.sections['relations'].append(relation_text)
            
        # Parse notes
        note_pattern = r'note for (\w+) "([^"]*)"'
        notes = re.findall(note_pattern, content)
        self.sections['notes'] = {}
        
        for class_name, note_text in notes:
            self.sections['notes'][class_name] = f'note for {class_name} "{note_text}"'
            
        print(f"Parsed {len(self.sections['classes'])} classes, {len(self.sections['relations'])} relations, and {len(self.sections['notes'])} notes")
        return self.sections
    
    def create_sequence(self, num_steps=None):
        """Create a sequence of incremental diagrams
        
        If num_steps is not specified, it will automatically calculate based on:
        - One step for the core/first class
        - One step for each additional class
        - One step for adding notes when they exist
        """
        if not self.sections:
            if self.diagram_type == 'classDiagram':
                self.parse_class_diagram()
            else:
                raise ValueError(f"Parsing for {self.diagram_type} not implemented yet")
                
        # Auto-calculate the number of steps based on diagram complexity
        if not num_steps:
            # One step for each class
            class_steps = len(self.sections['classes'])
            
            # One step if there are any relations (we'll add them incrementally)
            relation_steps = 1 if self.sections['relations'] else 0
            
            # One step if there are any notes (we'll add them with their associated classes)
            note_steps = 1 if self.sections['notes'] else 0
            
            # Total steps needed
            num_steps = class_steps + relation_steps + note_steps
            print(f"Auto-calculated {num_steps} steps based on diagram complexity")
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"Created output directory: {self.output_dir}")
            
        # Step 1: Start with just the first class
        sequence = []
        all_classes = sorted(self.sections['classes'].items(), key=lambda x: x[1]['order'])
        
        if all_classes:
            first_diagram = f"{self.diagram_type}\n{all_classes[0][1]['content']}"
            
            # If there's a note for this class, add it
            if all_classes[0][0] in self.sections['notes']:
                first_diagram += f"\n{self.sections['notes'][all_classes[0][0]]}"
                
            sequence.append(first_diagram)
        
        # Determine number of items to add per step
        remaining_items = (len(all_classes) - 1) + len(self.sections['relations']) + len(self.sections['notes'])
        items_per_step = max(1, remaining_items // (num_steps - 1)) if num_steps > 1 else 1
        
        # Build the sequence, adding items incrementally
        current_diagram = sequence[0]
        added_classes = {all_classes[0][0]}
        added_relations = set()
        added_notes = set()
        if all_classes[0][0] in self.sections['notes']:
            added_notes.add(all_classes[0][0])
        
        # Step 2: Add the remaining classes one by one (one class per diagram)
        for class_name, class_info in all_classes[1:]:
            # Create a new diagram by adding one class
            next_diagram = current_diagram + f"\n{class_info['content']}"
            added_classes.add(class_name)
            
            # Add any relations that can now be formed with existing classes
            new_relations = []
            for relation in self.sections['relations']:
                rel_parts = relation.split(' --> ')
                if (rel_parts[0] in added_classes and rel_parts[1] in added_classes) and relation not in added_relations:
                    new_relations.append(relation)
                    added_relations.add(relation)
            
            if new_relations:
                next_diagram += '\n' + '\n'.join(new_relations)
            
            # Save this state as the next diagram in sequence
            sequence.append(next_diagram)
            current_diagram = next_diagram
        
        # Step 3: If there are any notes that haven't been added yet, add them in the final diagram
        remaining_notes = [note for class_name, note in self.sections['notes'].items() 
                          if class_name not in added_notes and class_name in added_classes]
        
        if remaining_notes:
            final_diagram = current_diagram + '\n' + '\n'.join(remaining_notes)
            sequence.append(final_diagram)
        
        # Ensure we're not creating more diagrams than requested
        if num_steps and len(sequence) > num_steps:
            sequence = sequence[:num_steps]
                
        # Save each step to a file with the naming format image_1.mmd, image_2.mmd, etc.
        for i, diagram in enumerate(sequence):
            file_path = os.path.join(self.output_dir, f"image_{i+1}.mmd")
            with open(file_path, 'w') as f:
                f.write(diagram)
            print(f"Created diagram {i+1}: {file_path}")
            
        return sequence
    
    def add_diagrams_to_readme(self):
        """Create a README.md with all generated diagrams"""
        readme_path = os.path.join(self.output_dir, "README.md")
        with open(readme_path, 'w') as f:
            f.write("# Mermaid Diagram Sequence\n\n")
            f.write("This sequence of diagrams was automatically generated to show incremental building of the diagram.\n\n")
            
            for i in range(len(os.listdir(self.output_dir)) - 1):  # -1 to exclude README.md
                f.write(f"## Diagram {i+1}\n\n")
                f.write(f"```mermaid\n")
                
                with open(os.path.join(self.output_dir, f"image_{i+1}.mmd"), 'r') as d:
                    f.write(d.read())
                    
                f.write(f"\n```\n\n")
                
        print(f"Created README with all diagrams: {readme_path}")

# Command-line interface
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create a sequence of incremental Mermaid diagrams')
    parser.add_argument('input_file', help='Input Mermaid diagram file (.mmd)')
    parser.add_argument('--output-dir', '-o', help='Output directory for sequence files')
    parser.add_argument('--steps', '-s', type=int, help='Number of steps in the sequence (optional, will auto-calculate if not provided)')
    parser.add_argument('--type', '-t', help='Diagram type (classDiagram, flowchart, etc.)')
    
    args = parser.parse_args()
    
    sequencer = MermaidSequencer(
        input_file=args.input_file,
        output_dir=args.output_dir,
        diagram_type=args.type
    )
    
    sequencer.load_file()
    if not args.type:
        sequencer._detect_diagram_type()
        
    sequencer.create_sequence(args.steps)
    sequencer.add_diagrams_to_readme()
    
    print("Sequence generation complete!")

# Example usage:
# python mermaid_sequencer.py diagram.mmd --steps 10 --output-dir sequence