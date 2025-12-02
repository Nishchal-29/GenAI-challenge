# GenAI Challenge — IIT (ISM) Dhanbad's Journey Video Generation

A complete data-driven Generative-AI pipeline for producing a 2-minute documentary-style video narrated and scored entirely by AI.

## Project Overview

This project implements an end-to-end, automated pipeline that transforms raw historical and institutional data into a narrated, visually compelling video showcasing the Journey of IIT (ISM) Dhanbad.

The challenge strictly required that:

* All content must originate from the provided dataset (HTML pages, documents, news articles, images).

* Transcript, narration, visuals, and background music must be fully generated or transformed using GenAI.

* A clean extraction → filtering → prompting → generation pipeline must be established.

## Overall Architecture
Dataset  →  HTML/Docs/Articles Extraction  →  Content Filtering  
         →  Prompt Construction (LLM)     →  Transcript Generation (Gemini LLM)
         →  Sentence JSON Builder         →  TTS Generation (pyttsx3)
         →  Image Filtering + Selection   →  Music Generation (MusicGen)
         →  Audio Assembly                →  Final Video Rendering

## Tech Stack
* Programming Language -> Python 3.10
* LLM Transcript Generation -> Google Gemini API (gemini-2.5-flash)
* Text-to-Speech (TTS) -> pyttsx3
* Music Generation -> Meta Transformer MusicGen
* HTML Parsing -> BeautifulSoup4
* Image Inspection -> PIL (Pillow)
* Video Assembly -> FFmpeg
* JSON Manipulation	-> Python's json module

## Repo Structure

```bash
GenAI-challenge/
│
├── data_preprocessing/
│   ├── build_narration_inputs.py // to get narration from the extracted json 
│   ├── extract_articles.py // to extract articles from the news_articles dataset into json
│   ├── extract_docs.py // to extract docs from website_crawls/docs dataset into json
│   ├── extract_websites.py // to extract html files from website_crawls/html dataset into json
│   └── filter_articles.py // to filter articles relevant to the institute
│
├── genai_calls/
│   ├── build_prompt.py // to build the prompt to get the transcript
│   ├── build_transcript.py // to generate transcript using gemini API
│   └── generate_bgm.py // to generate background music from transformer MusicGen library
│
├── genai_inputs/
│   └── transcript_prompt.txt
│
├── genai_outputs/
│   └── get_sentences.py // divide the transcript into sentences for audio conversion
│
├── build_video_with_audio/
│   ├── assemble_video.py
│   ├── ocr_images.py
│   ├── tts_pyttsx3_run.py
│   └── merge_narration.py
│
└── assets/
    ├── visuals/
    ├── audio/
    └── bgm/
```

# Methodology

This section explains, in detail, how each stage of the pipeline works and how every script in the repository contributes to generating the final AI-powered 2-minute video showcasing the Journey of IIT (ISM) Dhanbad.


Every script and every folder plays a role in completing this pipeline.

---

## 1. Data Preprocessing Pipeline (`data_preprocessing/`)

This folder contains all scripts responsible for reading, cleaning, and structuring the raw dataset into machine-usable JSON files.

### `extract_websites.py`
- Parses raw HTML pages from `website_crawls/dataset/html/**`.
- Uses **BeautifulSoup4** to extract:
  - Title  
  - Headings  
  - Page text  
  - Image references  
- Saves structured clean JSON entries for each page.

### `extract_articles.py`
- Extracts headline, sub-heading, and full article text from news article HTML files.
- Builds a raw consolidated article dataset.

### `filter_articles.py`
- Filters raw articles to keep only those **related to IIT (ISM)**.
- Uses keyword filtering:  
  - “IIT (ISM)”  
  - “Dhanbad”  
  - “Indian School of Mines”
- Saves the final curated dataset as `articles_filtered.json`.

### `extract_docs.py`
- Reads institutional documents (PDFs, handbook text, workshop files).
- Extracts clean text chunks from each document.
- Produces `docs_index.json` containing:
  - History
  - Academic program descriptions
  - Research highlights
  - Events & workshops information

### `build_narration_inputs.py`
- Combines extracted HTML, articles, and document data.
- Processes images:
  - Matches HTML image references with local image paths.
  - Falls back to “select one high-quality image per subfolder” when links fail.
- Produces the ready-to-use inputs (website_index.json, image lists) for narration generation.

---

## 2. LLM Prompt + Transcript Generation (`genai_calls/`)

### `build_prompt.py`
- Collects curated information from:
  - `articles_filtered.json`
  - `docs_index.json`
  - `website_index.json`
- Synthesizes a **master narrative prompt** combining:
  - History  
  - Academic expansion  
  - Key achievements  
  - Research breakthroughs  
  - Rankings & recognitions  
  - Campus life and community impact  
- Writes this final LLM prompt to:  
  **`genai_inputs/transcript_prompt.txt`**

### `build_transcript.py`
- Sends `transcript_prompt.txt` to the **Gemini LLM (gemini-2.5-flash)** via API.
- Receives ~2-minute documentary-style narration text.
- Stores it in:  
  **`genai_outputs/transcript.txt`**

### `generate_bgm.py`
- Uses **MusicGen** (Meta's transformer-based model) to generate:
  - Slow  
  - Soft  
  - Inspiring  
  - Cinematic  
  background music.
- Saves the instrumental soundtrack to:  
  **`assets/bgm/iitism_bgm.wav`**

---

## 3. Transcript → Sentence JSON → TTS (`genai_outputs/` & `build_video_with_audio/`)

### `get_sentences.py`  (in `genai_outputs/`)
- Reads the LLM-generated transcript.
- Splits narration into individual sentences using regex.
- Computes approximate duration per sentence (based on word count).
- Produces a structured JSON array like:

```json
{
  "id": 1,
  "text": "From its humble beginnings...",
  "duration": 8
}
```

### `tts_pyttsx3_run.py` (in `build_video_with_audio/`)

This script converts each sentence from the structured narration JSON into spoken audio using **pyttsx3**.

**Why pyttsx3?**
- Fully offline  
- Deterministic and reproducible  
- No API limits or external dependencies  
- Perfectly aligned with challenge constraints  

**Output:**
- One `.wav` file generated per sentence.

---

### `merge_narration.py`

After generating sentence-level audio files, this script merges them into a single clean narration track.

**Final Output:**
- **`assets/audio/narration.wav`**

---

## 4. Visual Processing (`build_video_with_audio/`)

### `ocr_images.py`

This optional script performs OCR on the selected images.

**Use cases:**
- Extracting embedded text from images.
- Validating image relevance.
- Ensuring image quality before video assembly.

(OCR is optional and used only for additional verification.)

---

## 5. Final Video Assembly (`build_video_with_audio/assemble_video.py`)

### `assemble_video.py`

This is the final stage where all assets come together into a polished video.

**It loads:**
- Narration timeline from the sentence JSON  
- Final narration audio (`narration.wav`)  
- AI-generated background music (`iitism_bgm.wav`)  
- Filtered curated visuals (`assets/visuals/`)  

**Creates the full video timeline:**
- Each narration segment is paired with one or more images.
- Uses transitions such as:
  - Crossfades  
  - Cuts  
  - Smooth visual movement  

**Audio Mixing:**
- Background music volume is reduced below narration (ducking).
- Final soundtrack = Narration + BGM.

**Output Video:**
- **`final_output/iitism_journey_video.mp4`**

This is the final fully AI-generated documentary video, using:
- Dataset-derived visuals
- Gemini-generated transcript
- pyttsx3-generated narration
- MusicGen-generated soundtrack
- Automated timeline editing via Python


## Summary of Pipeline
1. Extract raw text & images from dataset
2. Clean + filter IIT (ISM) relevant content
3. Build structured JSON indexes
4. Construct master LLM prompt using extracted facts
5. Generate transcript using Gemini LLM
6. Convert transcript → sentence JSON
7. Create TTS audio for each sentence (pyttsx3)
8. Generate background music with MusicGen
9. Merge narration audio
10. Assemble video with visuals, narration, and BGM
