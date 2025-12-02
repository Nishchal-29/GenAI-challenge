#!/usr/bin/env python3
"""
run_gemini_transcript.py

Reads the prompt at genai_inputs/gemini_transcript_prompt.txt,
sends it to Gemini-2.5-flash via google-genai SDK, obtains the LLM transcript,
and writes the result to genai_outputs/transcript.txt
"""

import os
from pathlib import Path
from google import genai
from google.genai import types

from dotenv import load_dotenv
load_dotenv()

# Configuration
PROMPT_FILE = Path("genai_inputs/gemini_transcript_prompt.txt")
OUTPUT_DIR = Path("genai_outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "transcript.txt"

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Please set environment variable GEMINI_API_KEY to your API key")

    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        prompt = f.read()

    client = genai.Client(api_key=api_key)

    print("Sending prompt to Gemini (gemini-2.5-flash)...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        # optionally you can configure other settings, e.g. temperature, maximum tokens etc.
        config=types.GenerateContentConfig(
            # use default settings; adjust if needed
        )
    )

    # By default, the SDK returns a .text attribute for text output. :contentReference[oaicite:3]{index=3}
    transcript = getattr(response, "text", None)
    if transcript is None:
        # fallback: maybe response.candidates[0].content.parts[0].text
        try:
            transcript = response.candidates[0].content.parts[0].text
        except Exception as e:
            raise RuntimeError(f"Unexpected response format: {e}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(transcript)

    print("Transcript saved to:", OUTPUT_FILE)
    print("Transcript preview:\n")
    print(transcript[:300] + "\n---\n...")

if __name__ == "__main__":
    main()
