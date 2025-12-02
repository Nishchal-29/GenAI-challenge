# scripts/index_dataset.py
"""
Windows-ready dataset indexer.
Usage:
  python scripts\\index_dataset.py
Options:
  - By default writes metadata.jsonl in the current working dir.
  - To also compute SHA256 hashes, run with --hash (slower).
"""

import os
import json
import hashlib
from pathlib import Path
from bs4 import BeautifulSoup
import pdfplumber
import argparse
from tqdm import tqdm

parser = argparse.ArgumentParser()
parser.add_argument("--root", default=None, help="Root dataset path. If empty, uses DATASET_DIR env var.")
parser.add_argument("--out", default="metadata.jsonl", help="Output file (jsonl).")
parser.add_argument("--hash", action="store_true", help="Compute sha256 hash for each file (slow).")
parser.add_argument("--max-snippet-chars", type=int, default=2000, help="Max chars for snippet")
args = parser.parse_args()

ROOT = Path("D:\centenary\Database")
OUT = Path(args.out)

EXT_HTML = {'.html', '.htm', '.mhtml'}
EXT_IMG = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff'}
EXT_PDF = {'.pdf'}

def file_sha256(path: Path, block_size=8192):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(block_size), b''):
            h.update(chunk)
    return h.hexdigest()

def extract_html_title_and_snippet(path: Path, max_chars=500):
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
        soup = BeautifulSoup(text, 'html.parser')
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        h1 = ""
        first_p = ""
        h1_tag = soup.find('h1')
        if h1_tag:
            h1 = h1_tag.get_text().strip()
        p_tag = soup.find('p')
        if p_tag:
            first_p = p_tag.get_text().strip()
        snippet = first_p or h1 or ""
        return title[:max_chars], snippet[:max_chars]
    except Exception as e:
        return "", ""

def extract_pdf_snippet(path: Path, max_chars=500):
    try:
        with pdfplumber.open(str(path)) as pdf:
            if len(pdf.pages) > 0:
                txt = pdf.pages[0].extract_text() or ""
                return txt.strip()[:max_chars]
    except Exception:
        return ""
    return ""

def main():
    print("Indexing root:", ROOT)
    if not ROOT.exists():
        print("ERROR: root path does not exist:", ROOT)
        return
    with OUT.open('w', encoding='utf-8') as fout:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            for fn in filenames:
                p = Path(dirpath) / fn
                try:
                    rec = {
                        "path": str(p.resolve()),
                        "name": fn,
                        "size": p.stat().st_size,
                        "ext": p.suffix.lower(),
                        "modified_time": p.stat().st_mtime
                    }
                except Exception as e:
                    # skip files we can't stat
                    continue

                ext = rec["ext"]
                if ext in EXT_HTML:
                    title, snippet = extract_html_title_and_snippet(p, args.max_snippet_chars)
                    if title: rec["title"] = title
                    if snippet: rec["snippet"] = snippet
                elif ext in EXT_PDF:
                    sn = extract_pdf_snippet(p, args.max_snippet_chars)
                    if sn: rec["snippet"] = sn

                if args.hash:
                    try:
                        rec["sha256"] = file_sha256(p)
                    except Exception:
                        rec["sha256"] = None

                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("Wrote metadata:", OUT)

if __name__ == "__main__":
    main()
