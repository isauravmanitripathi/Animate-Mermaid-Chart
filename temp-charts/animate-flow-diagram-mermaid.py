import os
import re
import argparse

class MermaidAnimator:
    def __init__(self, input_file, output_dir="animation_output"):
        self.input_file = input_file
        self.output_dir = output_dir
        self.lines = []
        self.declaration = ""
        self.subgraph_blocks = {}  # Dictionary to store subgraph definitions
        self.node_to_subgraph = {}  # Maps node IDs to their subgraphs
        self.visible_nodes = set()  # Nodes that have appeared so far
        
    def load_file(self):
        """Load the mermaid file and separate declaration from content"""
        with open(self.input_file, 'r') as f:
            content = f.read().strip()
        
        lines = content.split('\n')
        self.declaration = lines[0]  # First line is always the declaration
        self.lines = [line for line in lines[1:] if line.strip() and not line.strip().startswith('%%')]
        
        print(f"Loaded {len(self.lines) + 1} lines from {self.input_file}")
        
    def find_subgraphs(self):
        """Find all subgraphs and their nodes"""
        # First, extract all subgraph blocks
        i = 0
        while i < len(self.lines):
            line = self.lines[i].strip()
            
            if line.startswith('subgraph'):
                subgraph_name = line.replace('subgraph', '').strip()
                subgraph_content = [line]
                j = i + 1
                
                while j < len(self.lines) and not self.lines[j].strip() == 'end':
                    subgraph_content.append(self.lines[j])
                    j += 1
                
                if j < len(self.lines):  # Add the 'end' line
                    subgraph_content.append(self.lines[j])
                
                # Store the complete subgraph block
                self.subgraph_blocks[subgraph_name] = subgraph_content
                
                # Extract node IDs from this subgraph
                nodes = []
                for sline in subgraph_content[1:-1]:  # Skip the 'subgraph' and 'end' lines
                    sline = sline.strip()
                    if sline and not sline.startswith('subgraph') and not sline.startswith('end'):
                        # This should be a node ID
                        nodes.append(sline)
                
                # Map each node to this subgraph
                for node in nodes:
                    self.node_to_subgraph[node] = subgraph_name
                
                i = j + 1  # Skip past this subgraph
            else:
                i += 1
        
        print(f"Found {len(self.subgraph_blocks)} subgraphs")
    
    def extract_nodes(self, line):
        """Extract node IDs from a line"""
        # Simple pattern to match node IDs
        node_pattern = re.compile(r'([A-Za-z0-9_]+)(?:\[|\(|{)')
        return node_pattern.findall(line)
    
    def create_partial_subgraph(self, subgraph_name):
        """Create a subgraph containing only the nodes seen so far"""
        if subgraph_name not in self.subgraph_blocks:
            return None
        
        subgraph_lines = self.subgraph_blocks[subgraph_name]
        visible_nodes = []
        
        # Extract the nodes from this subgraph
        for line in subgraph_lines[1:-1]:  # Skip subgraph and end lines
            line = line.strip()
            if line and not line.startswith('subgraph') and not line.startswith('end'):
                # This is a node ID
                if line in self.visible_nodes:
                    visible_nodes.append(line)
        
        if not visible_nodes:
            return None
            
        # Create a partial subgraph with only visible nodes
        result = [f"subgraph {subgraph_name}"]
        result.extend(visible_nodes)
        result.append("end")
        
        return "\n".join(result)
    
    def generate_animation(self):
        """Generate the sequence of diagrams"""
        self.load_file()
        self.find_subgraphs()
        
        # Create output directory
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        else:
            # Clear existing mmd files
            for file in os.listdir(self.output_dir):
                if file.endswith('.mmd'):
                    os.remove(os.path.join(self.output_dir, file))
        
        # Start with just the declaration
        diagrams = [self.declaration]
        content_lines = [self.declaration]
        
        # Filter out subgraph lines
        content_only_lines = []
        i = 0
        while i < len(self.lines):
            line = self.lines[i].strip()
            
            if line.startswith('subgraph'):
                # Skip this subgraph block
                depth = 1
                j = i + 1
                while j < len(self.lines) and depth > 0:
                    if self.lines[j].strip().startswith('subgraph'):
                        depth += 1
                    elif self.lines[j].strip() == 'end':
                        depth -= 1
                    j += 1
                i = j
            else:
                content_only_lines.append(self.lines[i])
                i += 1
        
        # Now process the content lines one by one
        for i, line in enumerate(content_only_lines):
            # Add this line to our content
            content_lines.append(line)
            
            # Find any nodes in this line
            nodes = self.extract_nodes(line)
            for node in nodes:
                self.visible_nodes.add(node)
            
            # Find which subgraphs these nodes belong to
            related_subgraphs = set()
            for node in nodes:
                if node in self.node_to_subgraph:
                    related_subgraphs.add(self.node_to_subgraph[node])
            
            # Build this diagram
            current_diagram = content_lines.copy()
            
            # Add all subgraphs with visible nodes
            for subgraph_name in self.subgraph_blocks:
                partial = self.create_partial_subgraph(subgraph_name)
                if partial:
                    current_diagram.append("")  # Add a blank line for separation
                    current_diagram.append(partial)
            
            # Save this diagram
            diagrams.append("\n".join(current_diagram))
        
        # Write all diagrams to files
        for i, diagram in enumerate(diagrams):
            with open(os.path.join(self.output_dir, f"image_{i+1}.mmd"), 'w') as f:
                f.write(diagram)
        
        # Create README
        self.create_readme(diagrams)
        
        return len(diagrams)
    
    def create_readme(self, diagrams):
        """Create a README.md with all diagrams"""
        with open(os.path.join(self.output_dir, "README.md"), 'w') as f:
            f.write("# Mermaid Diagram Animation\n\n")
            f.write("This sequence of diagrams shows the step-by-step building of the flowchart.\n\n")
            
            for i, diagram in enumerate(diagrams):
                f.write(f"## Diagram {i+1}\n\n")
                f.write("```mermaid\n")
                f.write(diagram)
                f.write("\n```\n\n")
        
        print(f"Created README.md in {self.output_dir}")
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an animated sequence of Mermaid diagrams")
    parser.add_argument('input_file', help='Input Mermaid diagram file (.mmd)')
    parser.add_argument('--output-dir', '-o', default='animation_output', help='Output directory')
    
    args = parser.parse_args()
    
    animator = MermaidAnimator(args.input_file, args.output_dir)
    count = animator.generate_animation()
    
    print(f"Generated {count} diagram steps in {args.output_dir}")