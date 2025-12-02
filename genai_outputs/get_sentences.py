#!/usr/bin/env python3
import re, json
from pathlib import Path

INPUT = Path("genai_outputs/transcript.txt")
OUTPUT = Path("genai_outputs/transcript_sentences.json")

# adjustable speaking speed in words per minute (wpm)
WORDS_PER_MINUTE = 500  

def split_into_sentences(text):
    # split on sentence end punctuations followed by whitespace
    sentences = re.split(r'(?<=[\.!\?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]

def estimate_duration(sentence, wpm=WORDS_PER_MINUTE):
    words = sentence.split()
    if not words:
        return 1
    secs = (len(words) / wpm) * 60.0
    return max(1, round(secs))

def main():
    text = INPUT.read_text(encoding="utf-8").strip()
    sents = split_into_sentences(text)
    arr = []
    for idx, s in enumerate(sents, start=1):
        arr.append({
            "id": idx,
            "text": s,
            "duration": estimate_duration(s)
        })
    OUTPUT.parent.mkdir(exist_ok=True, parents=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(arr, f, indent=2, ensure_ascii=False)
    print("Wrote", OUTPUT, "with", len(arr), "utterances.")

if __name__ == "__main__":
    main()
