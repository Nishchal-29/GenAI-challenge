# data_ingest/extract_docs.py
import os, json
from pathlib import Path
from tika import parser
from tqdm import tqdm

DOCS_ROOT = Path("website_crawls/dataset/docs")
OUT = Path("preprocessed/docs_index.json")

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    items = []
    if not DOCS_ROOT.exists():
        print("Docs root not found:", DOCS_ROOT)
        return
    for p in tqdm(list(DOCS_ROOT.rglob("*"))):
        if p.is_file():
            try:
                parsed = parser.from_file(str(p))
                text = (parsed.get("content") or "").strip()
                items.append({"path": str(p), "text_snippet": text[:15000]})
            except Exception as e:
                print("Failed parse:", p, e)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    print("Wrote", OUT, "count:", len(items))

if __name__ == "__main__":
    main()
