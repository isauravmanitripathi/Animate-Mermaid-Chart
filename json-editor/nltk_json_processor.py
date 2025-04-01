import json
import os
import sys
import nltk
from nltk.tokenize import sent_tokenize
import argparse

def process_json(input_file_path):
    # Ensure NLTK data is downloaded properly
    try:
        nltk.download('punkt', quiet=True)
    except:
        # If automatic download fails, provide clear instructions
        print("NLTK punkt resource is required but couldn't be downloaded automatically.")
        print("Please run the following in a Python interpreter:")
        print(">>> import nltk")
        print(">>> nltk.download('punkt')")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir = './parsed-nltk-json'
    os.makedirs(output_dir, exist_ok=True)
    
    # Determine output filename
    input_filename = os.path.basename(input_file_path)
    output_filename = f"nltk_{input_filename}"
    output_file_path = os.path.join(output_dir, output_filename)
    
    # Read input JSON
    with open(input_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Process each entry
    processed_data = []
    
    for item in data:
        # Extract the original data
        chapter_name = item.get('chapter_name', '')
        chapter_id = item.get('chapter_id', 0)
        section_number = item.get('section_number', '')
        section_name = item.get('section_name', '')
        text = item.get('text', '')
        
        # Split text using NLTK
        sentences = sent_tokenize(text)
        
        # Group sentences into chunks (2-3 sentences per chunk)
        chunk_size = 3  # You can adjust this
        text_chunks = []
        
        for i in range(0, len(sentences), chunk_size):
            chunk = sentences[i:i+chunk_size]
            chunk_text = ' '.join(chunk)
            section_id = i // chunk_size + 1
            text_chunks.append({f"text_sectionid_{section_id}": chunk_text})
        
        # Create the output item structure
        processed_item = {
            "chapter_name": chapter_name,
            "chapter_id": chapter_id,
            "section_number": section_number,
            "section_name": section_name,
            "mermaid_test": text_chunks
        }
        
        processed_data.append(processed_item)
    
    # Write output JSON
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, indent=2, ensure_ascii=False)
    
    # Return the absolute path
    return os.path.abspath(output_file_path)

if __name__ == "__main__":
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Process JSON file with NLTK sentence splitting')
    parser.add_argument('input_file', help='Path to input JSON file')
    args = parser.parse_args()
    
    # Process the file and get the output path
    try:
        output_path = process_json(args.input_file)
        print(f"Processing completed successfully!")
        print(f"Output saved to: {output_path}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)