#!/usr/bin/env python3
import os
import glob
import re
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_mmd_files(directory):
    """Find all .mmd files in the specified directory."""
    if not os.path.exists(directory):
        logger.error(f"Directory does not exist: {directory}")
        return []
    
    pattern = os.path.join(directory, "*.mmd")
    mmd_files = glob.glob(pattern)
    return mmd_files

def replace_pattern_in_file(file_path, search_pattern, replacement):
    """Replace all occurrences of search_pattern with replacement in the file."""
    try:
        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Count occurrences of the pattern
        occurrences = content.count(search_pattern)
        
        if occurrences == 0:
            logger.info(f"No occurrences of '{search_pattern}' found in {file_path}")
            return 0
        
        # Replace the pattern
        new_content = content.replace(search_pattern, replacement)
        
        # Write the modified content back to the file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(new_content)
        
        logger.info(f"Replaced {occurrences} occurrences in {file_path}")
        return occurrences
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")
        return 0

def main():
    # Ask for directory containing .mmd files
    default_dir = "/Volumes/hard-drive/auto-mermaid-chart/temp-charts/flowchart_sequence"
    directory = input(f"Enter the directory path to search for .mmd files [default: {default_dir}]: ")
    
    # Use default if nothing is entered
    if not directory.strip():
        directory = default_dir
        logger.info(f"Using default directory: {directory}")
    
    # Find all .mmd files
    mmd_files = find_mmd_files(directory)
    file_count = len(mmd_files)
    
    if file_count == 0:
        logger.info(f"No .mmd files found in {directory}")
        return
    
    logger.info(f"Found {file_count} .mmd files in {directory}")
    
    # Display a sample of found files (maximum 5)
    sample_count = min(5, file_count)
    logger.info(f"Sample of files (showing {sample_count} of {file_count}):")
    for i in range(sample_count):
        logger.info(f"  {i+1}. {os.path.basename(mmd_files[i])}")
    
    # Get search pattern from user
    search_pattern = input("\nEnter the pattern to search for (e.g., '(('): ")
    if not search_pattern:
        logger.error("Search pattern cannot be empty.")
        return
    
    # Get replacement from user
    replacement = input(f"Enter the replacement for '{search_pattern}': ")
    
    # Confirm before proceeding
    confirm = input(f"\nReplace all instances of '{search_pattern}' with '{replacement}' in {file_count} files? (y/n): ")
    if confirm.lower() != 'y':
        logger.info("Operation cancelled.")
        return
    
    # Process each file
    total_replacements = 0
    processed_files = 0
    files_with_replacements = 0
    
    for file_path in mmd_files:
        replacements = replace_pattern_in_file(file_path, search_pattern, replacement)
        total_replacements += replacements
        processed_files += 1
        if replacements > 0:
            files_with_replacements += 1
        
        # Show progress periodically
        if processed_files % 10 == 0 or processed_files == file_count:
            logger.info(f"Progress: {processed_files}/{file_count} files processed")
    
    # Summary
    logger.info(f"\nSummary:")
    logger.info(f"- Total files processed: {processed_files}")
    logger.info(f"- Files with replacements: {files_with_replacements}")
    logger.info(f"- Total replacements made: {total_replacements}")
    logger.info(f"- Pattern replaced: '{search_pattern}' → '{replacement}'")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
