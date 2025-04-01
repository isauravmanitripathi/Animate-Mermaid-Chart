import json
import os
import anthropic
import sys
from dotenv import load_dotenv
import re
import traceback
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Initialize the Anthropic client
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("Warning: ANTHROPIC_API_KEY not found in environment variables or .env file.")
    print("Please make sure you have a .env file with ANTHROPIC_API_KEY=sk-ant-api03-...")
    sys.exit(1)

client = anthropic.Anthropic(
    api_key=api_key
)

def fix_json_string(json_str):
    """
    Fix common issues with JSON strings returned from the API.
    This is based on the reference code functionality.
    """
    if not json_str or not json_str.strip():
        return '{}'

    # Remove markdown code block markers
    if json_str.startswith('```json'):
        json_str = json_str[7:]
    elif json_str.startswith('```'):
        json_str = json_str[3:]
    
    if json_str.strip().endswith('```'):
        json_str = json_str.rsplit('```', 1)[0]

    # Try to find JSON object boundaries { ... }
    start_brace = json_str.find('{')
    end_brace = json_str.rfind('}')

    if start_brace != -1 and end_brace != -1 and start_brace < end_brace:
        json_str = json_str[start_brace:end_brace+1]
    elif start_brace != -1 and end_brace == -1:
        # We have an opening brace but no closing - add one at the end
        json_str = json_str[start_brace:] + '}'

    # Remove any leading/trailing whitespace
    json_str = json_str.strip()

    # Balance braces if needed
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)

    # Remove trailing commas in arrays and objects (common JSON error)
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)

    return json_str

def process_text_with_anthropic(text, previous_mermaid="", topic=""):
    """
    Send text to Anthropic API to generate mermaid code
    If previous_mermaid is provided, it will be used as context
    
    Returns:
        tuple: (mermaid_code, raw_response_dict)
    """
    context = ""
    if previous_mermaid:
        context = f"Here is the previous Mermaid diagram you created:\n```mermaid\n{previous_mermaid}\n```\n\nNow continue building on this diagram for the next section of text."
    
    # System message to emphasize JSON-only output (from reference code)
    system_prompt = "You are a diagram generator. You respond with properly formatted JSON only. Never add explanatory text outside of the JSON."
    
    prompt = f"""Create a sequential Mermaid diagram for the following text about {topic if topic else 'the topic'}.

{context}

Text to analyze:
{text}

Follow these specific rules:
- Use the 'graph TD' Mermaid syntax for a top-down directed graph
- Your new mermaid code MUST be compatible with the previous mermaid code
- Format node labels clearly with relevant information (<entity><br><detail>)
- Organize nodes sequentially using this pattern:
  1. Define a new node
  2. Immediately define connections to previously defined nodes
  3. Move to the next node
  4. Repeat
- Connect new nodes with relevant previous nodes to create an interconnected graph
- Use subgraphs to group related concepts when appropriate
- Color-code different types of nodes using appropriate classDef definitions

For example:
```
graph TD
%% First section
A[Concept A] 
B[Concept B]
A --> B

%% Second section (new additions)
C[Concept C]
A --> C
B --> C

%% Third section (new additions)
D[Concept D]
C --> D
```

CRITICAL: Your response MUST be ONLY a valid JSON object with EXACTLY these keys:
{{
  "mermaid_code": "The complete mermaid diagram code with all previous and new elements",
  "previous_code": "The previous code that was provided to you (if any)",
  "new_additions": "ONLY the new nodes and connections you've added"
}}

IMPORTANT INSTRUCTIONS:
- Your response must be ONLY valid JSON
- Do NOT include markdown formatting (like ```json or ```)
- Do NOT include any explanatory text outside the JSON object
- The "mermaid_code" value should contain the complete, valid Mermaid code
- Ensure the Mermaid code is properly escaped within the JSON string
- Do NOT mix arrow types (e.g., don't mix --> and --)
"""

    # Initialize raw response tracking
    raw_response = {
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
        "system_prompt": system_prompt
    }

    try:
        # Make API request with system prompt (based on reference code)
        print(f"    Sending request to Anthropic API...")
        
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=4096,
            temperature=0.3,  # Lower temperature for more consistent output
            system=system_prompt,  # Add system prompt for JSON-only output
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract the response text
        response_text = response.content[0].text
        
        # Store the full raw response for logging
        raw_response["raw_text"] = response_text
        raw_response["model"] = "claude-3-5-haiku-20241022"
        
        # Try to parse the JSON response with improved error handling
        try:
            # First try to clean and fix the JSON
            fixed_json_str = fix_json_string(response_text)
            
            # Store the fixed JSON string in the raw response
            raw_response["fixed_json"] = fixed_json_str
            
            # Then try to parse it
            response_json = json.loads(fixed_json_str)
            raw_response["parsed_json"] = response_json
            
            # Extract the full mermaid code
            mermaid_code = response_json.get("mermaid_code", "")
            
            # Get new additions for logging/debugging
            new_additions = response_json.get("new_additions", "")
            # Count the number of lines to estimate how many elements were added
            new_lines = new_additions.split('\n')
            print(f"    Added {len(new_lines)} new elements to the diagram")
            
            raw_response["extraction_method"] = "json_parsing"
            raw_response["extraction_success"] = True
            
            return mermaid_code, raw_response
            
        except json.JSONDecodeError as e:
            # If JSON parsing fails, log the error and try alternative extraction
            print(f"    Warning: Could not parse JSON response: {str(e)}. Falling back to text extraction.")
            
            # Debug: Save the problematic response to a file for inspection
            debug_file = f"debug_response_{hash(text)[:5]}.txt"
            with open(debug_file, 'w') as f:
                f.write(response_text)
            
            raw_response["json_parse_error"] = str(e)
            raw_response["debug_file"] = debug_file
            
            # Look for mermaid code pattern as a fallback
            mermaid_blocks = re.findall(r'```mermaid\s*([\s\S]*?)\s*```', response_text)
            if mermaid_blocks:
                print("    Found Mermaid code in markdown code block")
                raw_response["extraction_method"] = "markdown_code_block"
                raw_response["extraction_success"] = True
                return mermaid_blocks[0].strip(), raw_response
            
            # Second fallback: look for common Mermaid patterns
            mermaid_patterns = [
                r'(graph\s+[A-Z]+\s*\n[\s\S]+)',
                r'(flowchart\s+[A-Z]+\s*\n[\s\S]+)',
                r'(sequenceDiagram\s*\n[\s\S]+)',
                r'(stateDiagram(?:-v2)?\s*\n[\s\S]+)'
            ]
            
            for pattern in mermaid_patterns:
                matches = re.search(pattern, response_text)
                if matches:
                    print(f"    Found Mermaid code using pattern matching")
                    raw_response["extraction_method"] = "pattern_matching"
                    raw_response["pattern_used"] = pattern
                    raw_response["extraction_success"] = True
                    return matches.group(1).strip(), raw_response
            
            # Last resort: return the cleaned text
            print("    Using last resort text cleaning method")
            raw_response["extraction_method"] = "text_cleaning"
            raw_response["extraction_success"] = False
            cleaned_text = response_text.replace("```mermaid", "").replace("```", "").strip()
            return cleaned_text, raw_response
            
    except Exception as e:
        print(f"Error calling Anthropic API: {e}")
        print(traceback.format_exc())
        raw_response = {
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "traceback": traceback.format_exc(),
            "extraction_success": False,
            "extraction_method": "api_error"
        }
        return f"Error generating mermaid code: {e}", raw_response

def main():
    # Check if input is provided
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = input("Enter the path to your JSON file: ")
    
    output_dir = "./api-processed-json"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create timestamp for unique filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create output filenames
    base_filename = os.path.splitext(os.path.basename(input_file))[0]
    
    # 1. Incremental JSON file (updates as we process)
    incremental_file = os.path.join(output_dir, f"{base_filename}_incremental_{timestamp}.json")
    
    # 2. API response log file (stores all raw API responses)
    api_log_file = os.path.join(output_dir, f"{base_filename}_api_log_{timestamp}.json")
    
    # 3. Final output file
    output_file = os.path.join(output_dir, f"{base_filename}_final_{timestamp}.json")
    
    # Initialize API log as a list to store all responses
    api_responses = []
    
    try:
        # Read the input JSON
        with open(input_file, 'r') as f:
            data = json.load(f)
        
        # Save initial state to incremental file
        with open(incremental_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Initial state saved to: {incremental_file}")
        
        # Process each chapter
        for chapter in data:
            chapter_name = chapter.get("chapter_name", "Unknown Chapter")
            print(f"Processing chapter: {chapter_name}")
            
            # Process each text item in mermaid_test
            mermaid_test = chapter.get("mermaid_test", [])
            previous_mermaid = ""
            processed_texts = []
            
            # Iterate over each text item in the mermaid_test array
            for i, item in enumerate(mermaid_test):
                # Extract the text key and value
                if isinstance(item, dict):
                    # Get the first (and likely only) key, which should be something like "text_sectionid_1"
                    text_key = next(iter(item.keys()), f"text_{i+1}")
                    text_value = item.get(text_key, "")
                else:
                    print(f"  Warning: Item {i+1} is not a dictionary, skipping")
                    continue
                
                print(f"  Processing text {i+1}: {text_key}")
                
                # Generate mermaid code for this text, building on previous mermaid
                try:
                    mermaid_code, raw_response = process_text_with_anthropic(
                        text_value, 
                        previous_mermaid,
                        topic=f"{chapter_name} - {chapter.get('section_name', '')}"
                    )
                    
                    # Store the API response in the log
                    api_log_entry = {
                        "chapter": chapter_name,
                        "section": f"text_{i+1}",
                        "original_key": text_key,
                        "text_snippet": text_value[:100] + "..." if len(text_value) > 100 else text_value,
                        "timestamp": datetime.now().isoformat(),
                        "response_data": raw_response
                    }
                    
                    api_responses.append(api_log_entry)
                    
                except Exception as e:
                    print(f"    Error processing text: {str(e)}")
                    
                    # Log the error
                    api_responses.append({
                        "chapter": chapter_name,
                        "section": f"text_{i+1}",
                        "original_key": text_key,
                        "text_snippet": text_value[:100] + "..." if len(text_value) > 100 else text_value,
                        "timestamp": datetime.now().isoformat(),
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    })
                    
                    # Use error message as mermaid code to continue processing
                    mermaid_code = f"Error: {str(e)}"
                
                # Update the API log file after each response
                with open(api_log_file, 'w') as f:
                    json.dump(api_responses, f, indent=2)
                
                # Store the result in the new format
                processed_texts.append({
                    f"text_{i+1}": text_value,
                    f"mermaid_code_sectionid_{i+1}": mermaid_code
                })
                
                # Update previous_mermaid for next iteration
                previous_mermaid = mermaid_code
                
                # Update the incremental file after each section
                chapter["mermaid_test"] = processed_texts
                with open(incremental_file, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"    Incremental file updated with section {i+1}")
            
            # Replace the original mermaid_test with the processed version
            chapter["mermaid_test"] = processed_texts
        
        # Write the final updated data to the output file
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"\nProcessing complete:")
        print(f"1. Incremental JSON saved to: {incremental_file}")
        print(f"2. API response log saved to: {api_log_file}")
        print(f"3. Final output saved to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    # Verify python-dotenv is installed
    try:
        import dotenv
    except ImportError:
        print("The 'python-dotenv' package is required but not installed.")
        print("Please install it using: pip install python-dotenv")
        sys.exit(1)
        
    main()