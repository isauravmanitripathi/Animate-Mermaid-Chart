# json parser and automatic mermaid code generator

Generate code and then automatically builds a video based with audio and generates video. 

# 1st step

First step: Create a json parser which will take the input json file which has text, and then break it down into multiple rows and put them properly in text.

Takes the json file with AI written code as input. Which has this structure:

```json
[
  {
    "chapter_name": "string",
    "chapter_id": "integer",
    "section_number": "string",
    "section_name": "string",
    "text": "string"
  }
]
```

From this we use nlp or nltk library to break down text into multiple rows. So take the entire text and split into multiple fraction. It can split into as many fractions it wants, but in one column there should be around 2-3 lines minimum. 

The output json should look like this with proper nlp parsing:

```json
[
  {
    "chapter_name": "string",
    "chapter_id": "integer",
    "section_number": "string",
    "section_name": "string",
    "mermaid_test": [
      {
        "text_1": "string"
      },
      {
        "text_2": "string"
      }
    ]
  }
]

```


# 2nd step

Second step: Create  a file which will talk to the api to generate mermaid code. 

Now in this step we take newly json file we extract the entire text from the previous json file send it to the api and generate mermaid code. 

With mermaid code added the new file should look like this

```json 

[
  {
    "chapter_name": "string",
    "chapter_id": "integer",
    "section_number": "string",
    "section_name": "string",
    "mermaid_test": [
      {
        "text_1": "string",
        "mermaid_code_1": "Meramid code"
      },
      {
        "text_2": "string",
        "mermaid_code_2": "Mermaid Code"
      }
    ]
  }
]
```

So in this case we also send it a prompt which specifies that we need the mermaid code to be seuqnetial. 


we can use this prompt:

```text
Create a sequential Mermaid diagram that builds line by line as you process the following text about [TOPIC]. For each paragraph or logical section of the text:

Read and analyze a single paragraph/section
Identify key concepts, entities, or events that should become nodes
Determine relationships between the new nodes and any previously created nodes
Add only the new nodes and connections to the growing Mermaid diagram
Continue to the next paragraph/section

Follow these specific rules:

Use the 'graph TD' Mermaid syntax for a top-down directed graph
Each new component should build upon the previous diagram
Format node labels clearly with relevant information (<entity><br><detail>)
Add connecting arrows to show relationships (-->, ---, <-->, etc.)
Include comments (using %%) to label each new section addition
Color-code different types of nodes using appropriate classDef definitions
Add the style definitions only at the very end

For example, if processing text about historical events:

First paragraph → Add initial nodes
Second paragraph → Add new nodes + connections to previous nodes
Continue this pattern until the entire text is processed

Show your work as you go, displaying:

The paragraph/section being analyzed
The new Mermaid code snippets being added
A brief explanation of what elements you're adding and why

At the end, include the complete Mermaid diagram code that shows the entirety of the [TOPIC] as described in the text.
```

Here we also do one thing. We get the entire mermaid code, extract the mermaid and create a png file, so we can verify the entire process run, if there is an error generating the mermaid image, we send the code back along with prompt and the original json and also the error and ask it to rewrite the mermaid code so it works. 

# 3rd step

third step: Get mermaid code. save it, and run it with cli to generate an image file, if there is an error with mermaid syntax the program sends that snippet back to the api to fix it . 

Third steps ask the json file as input which is this

```json 
[
  {
    "chapter_name": "string",
    "chapter_id": "integer",
    "section_number": "string",
    "section_name": "string",
    "mermaid_test": [
      {
        "text_1": "string",
        "mermaid_code_1":"Meramid code"
      },
      {
        "text_2": "string",
        "mermaid_code_2":"Mermaid Code"
      }
    ]
  }
]

```

In this step we get the mermaid code, generate an image for each of them save all of the mermaid images in one folder and update the path.

```json
[
  {
    "chapter_name": "string",
    "chapter_id": "integer",
    "section_number": "string",
    "section_name": "string",
    "mermaid_test": [
      {
        "text_1": "string",
        "mermaid_code_1":"Meramid code",
        "mermaid_image_path_1":"path to mermaid image"
      },
      {
        "text_2": "string",
        "mermaid_code_2":"Mermaid Code",
        "mermaid_image_path_2":"path to mermaid image"
      }
    ]
  }
]

```

# 4th step

fourth step: convert text to audio using tts 

Now in this step we get the text and convert the text to audio. Using Edgetts and other mechanism. After that audio is convert it is stored in a temporary folder. and it should update the path of mermaid json with the audio path so we can accesss it.  

In this code it also adds the audio length, detect the length of audio using ffprobe and it adds the length.

```json 

[
  {
    "chapter_name": "string",
    "chapter_id": "integer",
    "section_number": "string",
    "section_name": "string",
    "mermaid_test": [
      {
        "text_1": "string",
        "mermaid_code_1":"Meramid code",
        "mermaid_image_path_1":"path to mermaid image",
        "audio_path_sectionId":"path to audio",
        "length_of_audio":"time"
      },
      {
        "text_2": "string",
        "mermaid_code_2":"Mermaid Code",
        "mermaid_image_path_2":"path to mermaid image",
        "audio_path_sectionId_2":"path to audio",
        "length_of_audio":"time"
      }
    ]
  }
]

```

# 5th step

fifth: get the audio length and get the path of images from directory and process them by combining them together  and save the video 




# Final

Generate the final video