import json
import os
import google.generativeai as genai
import sys
from dotenv import load_dotenv
import re
import traceback
from datetime import datetime
import time
import glob

# Load environment variables from .env file
load_dotenv()

# Initialize the Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("Warning: GEMINI_API_KEY not found in environment variables or .env file.")
    print("Please make sure you have a .env file with GEMINI_API_KEY=...")
    sys.exit(1)

genai.configure(api_key=api_key)

# Define paths
PROMPTS_DIR = "./prompts"  # Directory containing prompt templates

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

def get_available_prompts():
    """
    Scan the prompts directory and return a list of available prompt files.
    
    Returns:
        list: List of prompt files found
    """
    if not os.path.exists(PROMPTS_DIR):
        print(f"Prompts directory '{PROMPTS_DIR}' not found.")
        return []
    
    # Get all .txt files in the prompts directory
    prompt_files = glob.glob(os.path.join(PROMPTS_DIR, "*.txt"))
    return [os.path.basename(file) for file in prompt_files]

def read_prompt_file(filename):
    """
    Read a prompt file from the prompts directory.
    
    Args:
        filename (str): Name of the prompt file
        
    Returns:
        str: Content of the prompt file or None if file not found
    """
    file_path = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(file_path):
        print(f"Prompt file '{filename}' not found.")
        return None
    
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading prompt file '{filename}': {e}")
        return None

def validate_prompt(prompt_content):
    """
    Validate prompt file content to ensure it has the required placeholders.
    
    Args:
        prompt_content (str): Content of the prompt file
        
    Returns:
        tuple: (is_valid, message)
    """
    # Check for required placeholders
    required_placeholders = ["{topic}", "{text}"]
    optional_placeholders = ["{context_message}", "{json_example}"]
    
    missing_required = [p for p in required_placeholders if p not in prompt_content]
    
    if missing_required:
        return False, f"Missing required placeholders: {', '.join(missing_required)}"
    
    # Check for JSON example
    if "{json_example}" not in prompt_content:
        return True, "Warning: No JSON example placeholder found, which might affect output formatting."
    
    return True, "Prompt is valid."

def test_prompt_files():
    """
    Test all prompt files in the prompts directory.
    
    Returns:
        bool: True if all prompts are valid, False otherwise
    """
    prompts = get_available_prompts()
    if not prompts:
        print("No prompt files found in the prompts directory.")
        return False
    
    all_valid = True
    print("\nTesting prompt files...")
    for prompt_file in prompts:
        content = read_prompt_file(prompt_file)
        if content is None:
            all_valid = False
            continue
        
        is_valid, message = validate_prompt(content)
        status = "✅ Valid" if is_valid else "❌ Invalid"
        print(f"{prompt_file}: {status} - {message}")
        
        if not is_valid:
            all_valid = False
    
    return all_valid

def process_text_with_gemini(text, topic="", prompt_template="", retry_count=3):
    """
    Send text to Gemini API to generate standalone mermaid code for each text section
    
    Returns:
        tuple: (mermaid_code, raw_response_dict)
    """
    # Initialize raw response tracking
    raw_response = {
        "timestamp": datetime.now().isoformat(),
    }

    # Default JSON example if not provided in template
    json_example = """
{
  "new_additions": "A complete standalone mermaid diagram that represents the text"
}
"""

    # If we have a prompt template, use it with placeholders replaced
    if prompt_template:
        # Empty context_message since we don't want to use previous diagram
        context_message = ""
        
        prompt = prompt_template.format(
            topic=topic if topic else 'the topic',
            context_message=context_message,
            text=text,
            json_example=json_example
        )
    else:
        # This shouldn't happen if validation is in place
        print("Error: No prompt template provided.")
        raw_response["error"] = "No prompt template provided"
        return f"Error: No prompt template provided", raw_response

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
                
                # Extract the mermaid code
                mermaid_code = response_json.get("new_additions", "")
                
                # Format the mermaid code with proper indentation
                formatted_mermaid = format_mermaid_code(mermaid_code)
                
                # Count the number of lines to estimate how many elements were created
                mermaid_lines = formatted_mermaid.split('\n')
                num_lines = len([line for line in mermaid_lines if line.strip()])
                print(f"    Generated a diagram with {num_lines} lines")
                
                raw_response["extraction_method"] = "json_parsing"
                raw_response["extraction_success"] = True
                
                return formatted_mermaid, raw_response
                
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
                    return format_mermaid_code(mermaid_code), raw_response
                
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

def select_prompt():
    """
    Display available prompts and let the user select one.
    
    Returns:
        tuple: (prompt_filename, prompt_content) or (None, None) if no selection made
    """
    prompts = get_available_prompts()
    if not prompts:
        print("No prompts found in the prompts directory.")
        return None, None
    
    print("\nAvailable prompts:")
    for i, prompt_file in enumerate(prompts, 1):
        print(f"{i}. {prompt_file}")
    
    try:
        selection = input("\nSelect a prompt by number (or 'q' to quit): ")
        if selection.lower() == 'q':
            return None, None
        
        selection_idx = int(selection) - 1
        if selection_idx < 0 or selection_idx >= len(prompts):
            print("Invalid selection.")
            return None, None
        
        selected_prompt = prompts[selection_idx]
        prompt_content = read_prompt_file(selected_prompt)
        if prompt_content is None:
            return None, None
        
        # Validate the selected prompt
        is_valid, message = validate_prompt(prompt_content)
        if not is_valid:
            print(f"Selected prompt is invalid: {message}")
            return None, None
        
        return selected_prompt, prompt_content
    
    except ValueError:
        print("Please enter a valid number.")
        return None, None

def main():
    # Check if prompts directory exists
    if not os.path.exists(PROMPTS_DIR):
        print(f"Error: Prompts directory '{PROMPTS_DIR}' not found.")
        print(f"Please create a '{PROMPTS_DIR}' directory with prompt templates.")
        sys.exit(1)
    
    # Get available prompts
    prompts = get_available_prompts()
    if not prompts:
        print(f"Error: No prompt files found in '{PROMPTS_DIR}'.")
        print("Please add prompt template files (*.txt) to the prompts directory.")
        sys.exit(1)
    
    # Check if we're in test mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_result = test_prompt_files()
        if test_result:
            print("\nAll prompt files are valid.")
        else:
            print("\nSome prompt files have issues. Please fix them before proceeding.")
        sys.exit(0 if test_result else 1)
    
    # Select a prompt
    selected_prompt_file, prompt_template = select_prompt()
    if not selected_prompt_file or not prompt_template:
        print("No prompt selected. Exiting.")
        sys.exit(1)
    
    print(f"Using prompt template: {selected_prompt_file}")
    
    # Check if input is provided
    if len(sys.argv) > 1 and sys.argv[1] != "--test":
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
                
                # Generate a complete standalone mermaid diagram for this text
                try:
                    mermaid_code, raw_response = process_text_with_gemini(
                        text_value,
                        topic=f"{chapter_name} - {chapter.get('section_name', '')}",
                        prompt_template=prompt_template
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
                    
                    # Use error message for mermaid code to continue processing
                    mermaid_code = f"Error: {str(e)}"
                
                # Update the API log file after each response
                with open(api_log_file, 'w') as f:
                    json.dump(api_responses, f, indent=2)
                
                # Store the text and its complete mermaid diagram
                processed_texts.append({
                    f"text_{i+1}": text_value,
                    f"mermaid_diagram_{i+1}": mermaid_code
                })
                
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