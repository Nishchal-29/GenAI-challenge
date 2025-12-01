#!/usr/bin/env python3
"""
build_concise_narration_prompt.py

Reads narration_prompts.json and produces a single concise, appealing narration
string suitable to feed directly into a TTS model.

Rules:
- Uses only text in each scene's 'narration_prompt' (verbatim segments extracted).
- Removes provenance/source lines entirely.
- Extracts up to N_SENTENCES_PER_SCENE (configurable) from each narration_prompt,
  then trims to MAX_WORDS_PER_SCENE to keep it concise.
- Sorts scenes chronologically (oldest -> newest) using robust date parsing.
- Inserts short, neutral transitions to improve flow ("Over the years," etc.).
- Outputs:
    - genai_inputs/full_narration_prompt.txt  (single text prompt for TTS)
    - genai_inputs/full_narration_manifest.json (metadata: scenes used, words)
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from dateutil import parser as dateparser
import textwrap

# Config
INPUT_PATHS = [Path("/mnt/data/narration_prompts.json"), Path("genai_inputs/narration_prompts.json")]
OUT_PROMPT = Path("genai_inputs/full_narration_prompt.txt")
OUT_MANIFEST = Path("genai_inputs/full_narration_manifest.json")

N_SENTENCES_PER_SCENE = 2       # extract up to this many sentences from each scene's narration_prompt
MAX_WORDS_PER_SCENE = 35        # trim extracted sentences to this many words per scene
CONNECTORS = [""]
HEADER = (
    "VOICE INSTRUCTIONS: Speak in a warm, clear, and engaging narrative tone. "
    "Maintain moderate pace, natural emphasis, and brief pauses between sections. "
    "Do not add facts beyond the text provided. Read the narration below verbatim.\n\n"
)

# Utilities
def load_prompts():
    for p in INPUT_PATHS:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data, str(p)
    raise FileNotFoundError(f"Could not find narration_prompts.json at any of {INPUT_PATHS}")

def parse_date_for_sort(d):
    if not d:
        return datetime.max.replace(tzinfo=timezone.utc)
    try:
        dt = dateparser.parse(d)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return datetime.max.replace(tzinfo=timezone.utc)

def split_into_sentences(text):
    # Very lightweight sentence splitter using punctuation.
    # Keeps abbreviations naive; good enough for short narration prompts.
    text = text.replace("\n", " ").strip()
    # split on . ? !
    import re
    parts = re.split(r'(?<=[\.\?\!])\s+', text)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [text]

def trim_to_word_limit(text, limit):
    words = text.split()
    return " ".join(words[:]).rstrip() + "."

def make_scene_excerpt(scene):
    raw = scene.get("narration_prompt") or scene.get("prompt") or ""
    if not raw:
        # fallback to title if present
        raw = scene.get("title","")
    # remove any leading provenance markers if present (e.g., "(SOURCE:")
    if raw.lstrip().startswith("("):
        # remove leading parenthetical up to first ')'
        idx = raw.find(")")
        if idx != -1 and idx < 120:
            raw = raw[idx+1:].strip()
    sentences = split_into_sentences(raw)
    take = sentences[:]
    combined = " ".join(take).strip()
    excerpt = trim_to_word_limit(combined, MAX_WORDS_PER_SCENE)
    return excerpt

def assemble_full_narration(scenes):
    # sort
    ordered = sorted(scenes, key=lambda s: parse_date_for_sort(s.get("date")))
    parts = [HEADER]
    manifest_entries = []
    for i, s in enumerate(ordered):
        excerpt = make_scene_excerpt(s)
        if not excerpt:
            continue
        # clean up whitespace
        excerpt = " ".join(excerpt.split())
        # choose connector for flow (skip connector before very first scene)
        if i == 0:
            parts.append(excerpt)
        else:
            connector = CONNECTORS[(i-1) % len(CONNECTORS)]
            parts.append(connector + " " + excerpt)
        manifest_entries.append({
            "scene_index": s.get("scene_index"),
            "title": s.get("title"),
            "date": s.get("date"),
            "excerpt_words": len(excerpt.split())
        })
    full_text = "\n\n".join(parts).strip()
    return full_text, manifest_entries

def enforce_total_limit(full_text, max_total_words=10000):
    words = full_text.split()
    truncated = False
    if len(words) > max_total_words:
        truncated = True
        full_text = " ".join(words[:max_total_words])
        # ensure it ends with a period
        if not full_text.endswith("."):
            full_text = full_text.rstrip() + "."
    return full_text, truncated, len(words)

def main():
    scenes, src = load_prompts()
    print(f"Loaded {len(scenes)} scenes from {src}")

    full_text, manifest_entries = assemble_full_narration(scenes)
    full_text, truncated, total_words = enforce_total_limit(full_text)

    OUT_PROMPT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PROMPT, "w", encoding="utf-8") as f:
        f.write(full_text)
    manifest = {
        "source_file": src,
        "num_scenes": len(manifest_entries),
        "total_words": total_words,
        "truncated": bool(truncated),
        "scenes": manifest_entries
    }
    with open(OUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("Wrote concise narration prompt to:", OUT_PROMPT)
    print("Manifest written to:", OUT_MANIFEST)
    if truncated:
        print("NOTE: narration was truncated to a total word limit. Consider splitting into chunks for TTS if needed.")

if __name__ == "__main__":
    main()
