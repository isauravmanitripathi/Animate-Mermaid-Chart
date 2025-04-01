import json
import os
import google.generativeai as genai
import sys
from dotenv import load_dotenv
import re
import traceback
from datetime import datetime
import time

# Load environment variables from .env file
load_dotenv()

# Initialize the Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("Warning: GEMINI_API_KEY not found in environment variables or .env file.")
    print("Please make sure you have a .env file with GEMINI_API_KEY=...")
    sys.exit(1)

genai.configure(api_key=api_key)

def fix_json_string(json_str):
    """
    Fix common issues with JSON strings returned from the API.
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

def format_mermaid_code(mermaid_code):
    """
    Format Mermaid code with proper indentation.
    
    Args:
        mermaid_code (str): Raw Mermaid code
        
    Returns:
        str: Properly formatted and indented Mermaid code
    """
    lines = mermaid_code.split('\n')
    formatted_lines = []
    indent_level = 0
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            formatted_lines.append('')
            continue
        
        # Adjust indent based on subgraph markers
        if stripped.startswith('subgraph'):
            formatted_lines.append('    ' * indent_level + stripped)
            indent_level += 1
            continue
        elif stripped == 'end':
            indent_level = max(0, indent_level - 1)
            formatted_lines.append('    ' * indent_level + stripped)
            continue
        
        # Handle comments
        if stripped.startswith('%%'):
            formatted_lines.append('    ' * indent_level + stripped)
            continue
            
        # Add proper indentation to all other lines
        formatted_lines.append('    ' * indent_level + stripped)
    
    return '\n'.join(formatted_lines)

def process_text_with_gemini(text, previous_mermaid="", topic="", retry_count=3):
    """
    Send text to Gemini API to generate incremental mermaid code
    If previous_mermaid is provided, it will be used as context
    
    Returns:
        tuple: (new_mermaid_additions, raw_response_dict)
    """
    # Extract header and styling from previous mermaid if exists
    header_style = ""
    node_definitions = ""
    
    if previous_mermaid:
        # Extract the header (graph TD and class definitions)
        lines = previous_mermaid.split('\n')
        header_lines = []
        style_lines = []
        
        # Process line by line to extract header and styles
        in_classDef = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('graph ') or stripped.startswith('flowchart '):
                header_lines.append(stripped)
            elif stripped.startswith('classDef ') or in_classDef:
                in_classDef = True
                style_lines.append(stripped)
                if ';' in stripped:
                    in_classDef = False
        
        header_style = '\n'.join(header_lines + style_lines)
    
    context_message = ""
    if previous_mermaid:
        context_message = f"""
Here is the previous Mermaid diagram you created:

```mermaid
{previous_mermaid}
```

IMPORTANT: To save tokens and be efficient, you should ONLY generate the NEW additions to the diagram.
DO NOT regenerate the entire diagram. Your response should ONLY contain the new nodes and connections that relate to the text.
The existing header, style definitions, nodes, and connections will be preserved - you just need to build on them.
"""
    
    # Initialize raw response tracking
    raw_response = {
        "timestamp": datetime.now().isoformat(),
    }

    prompt = f"""Create a sequential Mermaid diagram for the following text about {topic if topic else 'the topic'}.

{context_message}

Text to analyze:
{text}

Use a sequential node-connection pattern with the following structure:
1. Define a node
2. Immediately define any connections to previously defined nodes
3. Move to the next node
4. Repeat the pattern

For example:
```
%% New node for current section
D[Entity D]
%% Connections from D to previous nodes
A --> D
C --> D
%% Another new node
E[Entity E]
%% Connections to/from E
D --> E
B <--> E
```

Follow these specific rules:
- Only generate new additions that start EXACTLY where the previous diagram left off
- Your new code must be syntactically compatible with the existing diagram
- The new generated code should be interconnected with previous nodes, or create subgraphs if needed. 
- Format node labels clearly with relevant information (<entity><br><detail>)
- Group related nodes with clear section comments using %% before each section and also subgraphs
- Use descriptive node labels with relevant data points
- Each time try to create a more interconnect graph so all of it is interconnected
- Include bidirectional relationships where appropriate

When adding new nodes and connections:
  1. Start with a comment indicating what this new section represents
  2. ONLY add new nodes and connections related to the current text
  3. Connect these new nodes to existing nodes where appropriate
  4. Make sure each line has proper indentation (4 spaces per level)
  5. Use descriptive labels for all connections

IMPORTANT: DO NOT repeat any existing nodes or connections from the previous diagram.
Start EXACTLY where the previous diagram left off.

If this is the first section, create a properly structured diagram with:
  1. Header (graph TD)
  2. Class definitions for styling
  3. Clear node and connection structure

CRITICAL: Your response MUST be ONLY a valid JSON object with EXACTLY these keys:
{
  "new_additions": "ONLY the new nodes and connections you've added (NOT including header and classDefs, and NOT including any existing nodes/connections)"
}

IMPORTANT FORMATTING INSTRUCTIONS:
- Properly indent all code (4 spaces per level)
- Put each node or connection on its own line
- Start with section comments (using %%) to explain what the new additions represent
- DO NOT include any content from the previous diagram

Return ONLY the JSON object without any markdown code blocks or other text.
"""

    # Store prompt in raw response
    raw_response["prompt"] = prompt

    # Generation configuration
    generation_config = {
        "temperature": 0.3,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 4096,
    }

    # Safety settings
    safety_settings = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        }
    ]

    # Retry logic
    for attempt in range(retry_count):
        try:
            # Exponential backoff for retries
            if attempt > 0:
                backoff_time = min(30, 2 ** attempt)  # Cap at 30 seconds
                time.sleep(backoff_time)
                print(f"    Retrying (attempt {attempt+1}/{retry_count}) after {backoff_time}s delay...")
                
                # Slightly vary temperature on retries to get different responses
                generation_config["temperature"] = min(1.0, 0.3 + (attempt * 0.1))
            
            # Make API request with system prompt
            print(f"    Sending request to Gemini API...")
            
            # Create Gemini model
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Generate content
            response = model.generate_content(prompt)
            
            # Extract the response text
            response_text = response.text
            
            # Store the full raw response for logging
            raw_response["raw_text"] = response_text
            raw_response["model"] = "gemini-2.0-flash"
            raw_response["attempt"] = attempt + 1
            
            # Try to parse the JSON response with improved error handling
            try:
                # First try to clean and fix the JSON
                fixed_json_str = fix_json_string(response_text)
                
                # Store the fixed JSON string in the raw response
                raw_response["fixed_json"] = fixed_json_str
                
                # Then try to parse it
                response_json = json.loads(fixed_json_str)
                raw_response["parsed_json"] = response_json
                
                # Extract just the new additions
                new_additions = response_json.get("new_additions", "")
                
                # Format the new additions with proper indentation
                formatted_additions = format_mermaid_code(new_additions)
                
                # Count the number of lines to estimate how many elements were added
                new_lines = formatted_additions.split('\n')
                num_new_lines = len([line for line in new_lines if line.strip()])
                print(f"    Added {num_new_lines} new elements to the diagram")
                
                raw_response["extraction_method"] = "json_parsing"
                raw_response["extraction_success"] = True
                
                return formatted_additions, raw_response
                
            except json.JSONDecodeError as e:
                # If JSON parsing fails, log the error and try alternative extraction
                print(f"    Warning: Could not parse JSON response: {str(e)}. Falling back to text extraction.")
                
                # Debug: Save the problematic response to a file for inspection
                debug_file = f"debug_response_{abs(hash(text) % 10000)}.txt"
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
                    mermaid_code = mermaid_blocks[0].strip()
                    
                    # Since we couldn't get just the additions, try to extract only the new parts
                    # by removing header, graph declaration, and classDef lines
                    lines = mermaid_code.split('\n')
                    filtered_lines = []
                    for line in lines:
                        stripped = line.strip()
                        if (not stripped.startswith('graph ') and 
                            not stripped.startswith('flowchart ') and 
                            not stripped.startswith('classDef ')):
                            filtered_lines.append(line)
                            
                    additions = '\n'.join(filtered_lines)
                    return format_mermaid_code(additions), raw_response
                
                # Last resort: return the cleaned text
                print("    Using last resort text cleaning method")
                raw_response["extraction_method"] = "text_cleaning"
                raw_response["extraction_success"] = False
                cleaned_text = response_text.replace("```mermaid", "").replace("```", "").strip()
                
                # Try to continue with next attempt if we have retries left
                if attempt < retry_count - 1:
                    continue
                
                return format_mermaid_code(cleaned_text), raw_response
                
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            print(traceback.format_exc())
            raw_response["error"] = str(e)
            raw_response["traceback"] = traceback.format_exc()
            raw_response["extraction_success"] = False
            raw_response["extraction_method"] = "api_error"
            raw_response["attempt"] = attempt + 1
            
            # Try again if we have retries left
            if attempt < retry_count - 1:
                continue
            
            return f"Error generating mermaid code: {e}", raw_response

def combine_mermaid_code(previous_code, new_additions):
    """
    Combine previous mermaid code with new additions
    
    Args:
        previous_code (str): Existing mermaid code
        new_additions (str): New mermaid additions
        
    Returns:
        str: Combined mermaid code
    """
    if not previous_code:
        return new_additions
        
    # Check if the new additions already have a graph declaration
    if new_additions.strip().startswith('graph ') or new_additions.strip().startswith('flowchart '):
        # In this case, the new additions already have a complete mermaid structure
        return new_additions
        
    # Extract parts from the previous code
    lines = previous_code.split('\n')
    header_lines = []
    style_lines = []
    node_lines = []
    
    in_header = True
    in_style = False
    
    for line in lines:
        stripped = line.strip()
        if in_header and (stripped.startswith('graph ') or stripped.startswith('flowchart ')):
            header_lines.append(line)
            in_header = False
        elif not in_style and stripped.startswith('classDef '):
            style_lines.append(line)
            in_style = True
        elif in_style and stripped.startswith('classDef '):
            style_lines.append(line)
        elif in_style and not stripped.startswith('classDef '):
            in_style = False
            node_lines.append(line)
        else:
            node_lines.append(line)
    
    # Combine the parts with the new additions
    if header_lines and style_lines:
        # If we have header and style, put new additions after nodes
        combined = '\n'.join(header_lines + style_lines + node_lines)
        
        # Check if we need to add a new line
        if combined.endswith('\n'):
            combined += new_additions
        else:
            combined += '\n' + new_additions
            
        return combined
    elif header_lines:
        # If we only have header, put new additions after header
        combined = '\n'.join(header_lines + node_lines)
        
        # Check if we need to add a new line
        if combined.endswith('\n'):
            combined += new_additions
        else:
            combined += '\n' + new_additions
            
        return combined
    else:
        # If we don't have structure yet, just use new additions
        return new_additions

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
                    # Process and get just the NEW additions
                    new_additions, raw_response = process_text_with_gemini(
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
                    
                    # Combine previous mermaid code with new additions to get the full code
                    complete_mermaid = combine_mermaid_code(previous_mermaid, new_additions)
                    
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
                    
                    # Use error message for new additions to continue processing
                    new_additions = f"Error: {str(e)}"
                    complete_mermaid = combine_mermaid_code(previous_mermaid, new_additions)
                
                # Update the API log file after each response
                with open(api_log_file, 'w') as f:
                    json.dump(api_responses, f, indent=2)
                
                # Store both the new additions and the complete code
                processed_texts.append({
                    f"text_{i+1}": text_value,
                    f"mermaid_additions_{i+1}": new_additions,
                    f"complete_mermaid_{i+1}": complete_mermaid
                })
                
                # Update previous_mermaid for next iteration (use the complete code)
                previous_mermaid = complete_mermaid
                
                # Update the incremental file after each section
                chapter["mermaid_test"] = processed_texts
                with open(incremental_file, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"    Incremental file updated with section {i+1}")
                
                # Small delay to prevent rate limiting
                time.sleep(0.5)
            
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
        
    # Verify google-generativeai is installed
    try:
        import google.generativeai
    except ImportError:
        print("The 'google-generativeai' package is required but not installed.")
        print("Please install it using: pip install google-generativeai")
        sys.exit(1)
        
    main()