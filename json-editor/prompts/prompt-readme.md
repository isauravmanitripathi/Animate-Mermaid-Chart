# Mermaid Diagram Generation Prompts

This README explains how to create, edit, and understand the prompt templates used for generating Mermaid diagrams with the Gemini API.

## Overview

These prompt templates guide the Gemini AI model to convert text descriptions into Mermaid diagram code. Each prompt is designed for a specific diagram type (flowchart, state diagram, sequence diagram, etc.) and follows a consistent structure.

## Prompt Directory Structure

All prompts should be placed in the `prompts/` directory and have a `.txt` extension:

```
prompts/
├── graph.txt            # For flowcharts
├── state_diagram.txt    # For state diagrams
├── sequence_diagram.txt # For sequence diagrams
└── requirements.txt     # For requirements diagrams
```

You can add as many prompt templates as needed, each tailored to different types of diagrams or analysis goals.

## Required Placeholders

Each prompt template must include these placeholders that will be replaced at runtime:

| Placeholder | Description | Required |
|-------------|-------------|----------|
| `{topic}` | The subject of the diagram | Yes |
| `{text}` | The text content to analyze | Yes |
| `{context_message}` | Context from previous diagrams | No |
| `{json_example}` | Expected JSON response format | Yes |

## Prompt Structure

A well-formed prompt should include these sections:

1. **Introduction**: Explains what the model should create
2. **Context**: The `{context_message}` placeholder for previous diagram content
3. **Input Text**: The `{text}` placeholder for text to analyze
4. **Structure Guidelines**: How to structure the specific diagram type
5. **Rules**: Specific instructions for diagram generation
6. **Output Format**: Expected JSON format with the `{json_example}` placeholder

## Example Prompt Template

Here's a simplified example for a flowchart prompt:

```
Create a sequential Mermaid diagram for the following text about {topic}.

{context_message}

Text to analyze:
{text}

Use a sequential node-connection pattern with the following structure:
1. Define a node
2. Define connections to previous nodes
3. Repeat

Follow these specific rules:
- Only generate new additions that start where the previous diagram left off
- Your new code must be compatible with the existing diagram
- Use descriptive node labels

CRITICAL: Your response MUST be ONLY a valid JSON object with EXACTLY these keys:
{json_example}
```

## Creating New Prompts

To create a new prompt template:

1. Create a new text file in the `prompts/` directory with a `.txt` extension
2. Include the required placeholders: `{topic}`, `{text}`, and `{json_example}`
3. Structure your prompt with clear instructions for the specific diagram type
4. Ensure the output format matches the expected JSON structure:
   ```json
   {
     "new_additions": "ONLY the new nodes and connections you've added"
   }
   ```

## Editing Existing Prompts

When editing prompt templates:

1. Maintain all required placeholders
2. Keep the overall structure consistent
3. Be precise about the Mermaid syntax you want the model to use
4. Test the prompt using the `--test` flag: `python main.py --test`

## Best Practices

1. **Be Specific**: Clearly describe the diagram structure you want
2. **Include Examples**: Show examples of good diagram code
3. **Define Boundaries**: Specify exactly what should be included/excluded
4. **Consistent Formatting**: Use consistent formatting instructions
5. **Error Prevention**: Include rules to prevent common mistakes

## Prompt Testing

To test if your prompts are properly formatted:

```bash
python main.py --test
```

This will validate all prompt files and report any missing required placeholders or other issues.

## Advanced Customization

You can create specialized prompts for different scenarios:

- **Domain-specific diagrams**: Add domain terminology and conventions
- **Different abstraction levels**: Create prompts for high-level or detailed diagrams
- **Style variations**: Customize node styles, colors, and layout preferences

## Troubleshooting

If the generated diagrams aren't meeting expectations:

1. Check the prompt for ambiguous instructions
2. Add more specific examples of desired output
3. Include explicit rules to address common issues
4. Review the JSON response format requirements
5. Test with smaller text inputs first

Remember that the quality of the generated diagrams depends greatly on the clarity and specificity of your prompt templates.