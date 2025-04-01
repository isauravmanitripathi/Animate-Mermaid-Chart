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

# 3rd step

third step: Get mermaid code. save it, and run it with cli to generate an image file, if there is an error with mermaid syntax the program sends that snippet back to the api to fix it  

# 4th step

fourth step: convert text to audio using tts  

# 5th step

fifth: get the audio length and get the path of images from directory and process them by combining them together  and save the video  


# Final

Generate the final video