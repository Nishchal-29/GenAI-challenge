# build_narration_inputs.py
"""
Take filtered articles and produce narration prompts and a scene plan suitable for TTS and visuals.
Outputs:
 - genai_inputs/narration_prompts.json  (list of scenes: text to speak, duration preference, source provenance, image path)
 - copies any referenced local images into assets/visuals/ (keeping provenance)
"""

import json, os, shutil, re
from datetime import datetime
from tqdm import tqdm

IN_FN = "preprocessed/articles_filtered.json"
OUT_JSON = "genai_inputs/narration_prompts.json"
ASSETS_DIR = "assets/visuals"

TARGET_WORDS = 30  

def clean_text_for_narration(txt):
    # remove excessive whitespace, bracketed citations, URLs
    txt = re.sub(r"\[.*?\]", "", txt)
    txt = re.sub(r"http\S+", "", txt)
    txt = re.sub(r"\s+", " ", txt)
    txt = txt.strip()
    # limit to 60 words for safety
    words = txt.split()
    return " ".join(words[:60])

def make_prompt(title, date, snippet, provenance):
    # ensure the prompt explicitly references dataset provenance
    date_str = date if date else "date unknown in dataset"
    prov_files = "; ".join([os.path.basename(p["source_html"]) for p in provenance[:3]])
    short = clean_text_for_narration(snippet)
    # Construct conservative, dataset-grounded narration line
    # Keep it factual and concise
    prompt = f"(SOURCE: dataset files: {prov_files}) {date_str} — {title}. {short}"
    return prompt

def main():
    if not os.path.exists(IN_FN):
        print("Run filter_and_score.py first. Missing:", IN_FN)
        return
    with open(IN_FN, "r", encoding="utf8") as f:
        items = json.load(f)
    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs("genai_inputs", exist_ok=True)
    outputs = []
    for idx, it in enumerate(items):
        title = it.get("title") or ""
        date = it.get("date")
        snippet = it.get("snippet") or ""
        provenance = it.get("provenance_group") or [{"source_html": it.get("source_html"), "score": it.get("score")}]
        prompt = make_prompt(title, date, snippet, provenance)
        # pick image: if local file, copy to assets; if external URL, just record the URL (do not download)
        image_src = it.get("image")
        local_copy = None
        if image_src:
            if image_src.startswith("http://") or image_src.startswith("https://"):
                # external: keep URL as provenance but do not download automatically
                local_copy = image_src
            else:
                # local path - copy
                if os.path.exists(image_src):
                    ext = os.path.splitext(image_src)[1]
                    dest = os.path.join(ASSETS_DIR, f"scene_{idx:02d}{ext}")
                    try:
                        shutil.copy2(image_src, dest)
                        local_copy = dest
                    except Exception as e:
                        print("Could not copy image", image_src, e)
                        local_copy = image_src
                else:
                    local_copy = image_src  # unresolved path; still record
        outputs.append({
            "scene_index": idx,
            "title": title,
            "date": date,
            "narration_prompt": prompt,
            "provenance_files": provenance,
            "image": local_copy,
            "preferred_duration_sec": 12 + (it.get("score",0) // 2)  # naive duration allocation; tune later
        })
    # save
    with open(OUT_JSON, "w", encoding="utf8") as f:
        json.dump(outputs, f, indent=2, ensure_ascii=False)
    print("Wrote", OUT_JSON, "and copied images to", ASSETS_DIR)

if __name__ == "__main__":
    main()
