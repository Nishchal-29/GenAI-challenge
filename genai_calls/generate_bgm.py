#!/usr/bin/env python3
import os
from pathlib import Path
import scipy.io.wavfile
import torch
from transformers import AutoProcessor, MusicgenForConditionalGeneration

# Config
OUTPUT_DIR = Path("bgm")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "iitism_bgm.wav"

PROMPT_TEXT = [
    "A slow, soft, inspiring instrumental soundtrack suitable as background music for a short documentary video. Uplifting, hopeful, reflective, cinematic. Gentle strings, soft piano."
]

def main():
    print("Loading MusicGen model (this may take a minute)...")
    
    # Load model and processor
    # using "small" for speed. Use "facebook/musicgen-medium" for better quality.
    processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
    model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")

    # Generate Audio
    print("Generating music...")
    inputs = processor(
        text=PROMPT_TEXT,
        padding=True,
        return_tensors="pt",
    )

    # max_new_tokens determines length. 
    # 256 tokens is roughly 5 seconds. For 30 secs, you need ~1500. 
    # Generating 2 full minutes locally takes a LONG time and lots of RAM.
    # We will generate a shorter loop (30s) effectively.
    audio_values = model.generate(**inputs, max_new_tokens=1500)

    # Save to file
    sampling_rate = model.config.audio_encoder.sampling_rate
    # Squeeze to remove batch dimension
    scipy.io.wavfile.write(OUTPUT_FILE, rate=sampling_rate, data=audio_values[0, 0].numpy())
    
    print(f"Saved background music to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()