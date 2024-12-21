import os

# Configuration: Add folder and file names to ignore
IGNORED_FOLDERS = {".venv", ".", ".git"}
IGNORED_FILES = {"ignore_this.py"}  # Example ignored files

# Output file name
OUTPUT_FILE = "combined_python_files.txt"

def build_project_tree(base_path):
    """Build a tree of the project structure."""
    tree_lines = []
    for root, dirs, files in os.walk(base_path):
        # Ignore specified folders
        dirs[:] = [d for d in dirs if d not in IGNORED_FOLDERS]

        # Indent tree structure
        level = root.replace(base_path, "").count(os.sep)
        indent = "    " * level
        tree_lines.append(f"{indent}{os.path.basename(root)}/")

        # Add files to the tree
        for file in files:
            tree_lines.append(f"{indent}    {file}")

    return "\n".join(tree_lines)

def collect_python_files(base_path):
    """Collect Python files from the project directory."""
    python_files = []
    for root, dirs, files in os.walk(base_path):
        # Ignore specified folders
        dirs[:] = [d for d in dirs if d not in IGNORED_FOLDERS]
        
        for file in files:
            if file.endswith(".py") and file not in IGNORED_FILES:
                python_files.append(os.path.join(root, file))

    return python_files

def combine_python_files(file_paths):
    """Combine the content of all Python files into a single string."""
    combined_content = []
    for file_path in file_paths:
        combined_content.append(f"# File: {os.path.relpath(file_path)}")
        with open(file_path, "r", encoding="utf-8") as f:
            combined_content.append(f.read())
        combined_content.append("\n" + "-" * 80 + "\n")  # Separator

    return "\n".join(combined_content)

def main():
    base_path = os.path.dirname(os.path.abspath(__file__))

    # Build project tree
    project_tree = build_project_tree(base_path)

    # Collect Python files
    python_files = collect_python_files(base_path)

    # Combine Python files' content
    combined_content = combine_python_files(python_files)

    # Write output file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# Project Tree\n")
        f.write(project_tree)
        f.write("\n\n" + "# Combined Python Files\n")
        f.write(combined_content)

    print(f"Combined Python files saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
