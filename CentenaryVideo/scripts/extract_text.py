# scripts/extract_text.py
"""
Extract text from HTML, PDF, TXT files and write facts_raw.jsonl
Run: python .\scripts\extract_text.py --root "D:\centenary\Database" --out facts_raw.jsonl --workers 6 --sample 0
Set --sample to N to only process first N files for quick test.
"""
import argparse, json, os
from pathlib import Path
from bs4 import BeautifulSoup
import pdfplumber
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

parser = argparse.ArgumentParser()
parser.add_argument("--root", default=None, help="Root dataset path (default from DATASET_DIR env)")
parser.add_argument("--out", default="facts_raw.jsonl")
parser.add_argument("--workers", type=int, default=4)
parser.add_argument("--sample", type=int, default=0, help="If >0, process only this many files (useful for test)")
parser.add_argument("--maxchars", type=int, default=20000)
args = parser.parse_args()

root = Path(args.root) if args.root else Path(os.environ.get("DATASET_DIR", "."))
OUT = Path(args.out)

HTML_EXT = {'.html','.htm','.mhtml'}
PDF_EXT = {'.pdf'}
TXT_EXT = {'.txt','.text'}

def extract_html(path):
    try:
        raw = path.read_text(encoding='utf-8', errors='ignore')
        soup = BeautifulSoup(raw, "html.parser")
        # join <p> paragraphs
        paras = [p.get_text().strip() for p in soup.find_all('p') if p.get_text().strip()]
        text = "\n\n".join(paras)
        if not text:
            # fallback: whole visible text
            text = soup.get_text(separator="\n").strip()
        return text[:args.maxchars]
    except Exception as e:
        return ""

def extract_pdf(path):
    try:
        text_parts = []
        with pdfplumber.open(str(path)) as pdf:
            for p in pdf.pages:
                t = p.extract_text()
                if t:
                    text_parts.append(t)
                # keep first N pages to save time
                if len(text_parts) >= 5:
                    break
        return ("\n\n".join(text_parts))[:args.maxchars]
    except Exception:
        return ""

def extract_txt(path):
    try:
        return path.read_text(encoding='utf-8', errors='ignore')[:args.maxchars]
    except Exception:
        return ""

def process_file(p: Path):
    ext = p.suffix.lower()
    if ext in HTML_EXT:
        txt = extract_html(p)
    elif ext in PDF_EXT:
        txt = extract_pdf(p)
    elif ext in TXT_EXT:
        txt = extract_txt(p)
    else:
        return None
    if not txt or len(txt.strip()) < 30:
        return None
    return {"path": str(p.resolve()), "text": txt}

def iter_files():
    for p in root.rglob("*"):
        if p.is_file():
            if p.suffix.lower() in HTML_EXT.union(PDF_EXT).union(TXT_EXT):
                yield p

def main():
    files = list(iter_files())
    if args.sample and args.sample > 0:
        files = files[:args.sample]

    with OUT.open("w", encoding="utf-8") as fout:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(process_file, p): p for p in files}
            for fut in tqdm(as_completed(futures), total=len(futures), desc="extracting"):
                res = fut.result()
                if res:
                    fout.write(json.dumps(res, ensure_ascii=False) + "\n")
    print("Wrote", OUT, "entries:", sum(1 for _ in OUT.open(encoding='utf-8')))

if __name__ == "__main__":
    main()
