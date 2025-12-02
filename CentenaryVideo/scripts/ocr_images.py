# scripts/ocr_images_debug.py
"""
Debug OCR runner. Writes partial output and logs exceptions.
Usage (example):
python .\\scripts\\ocr_images_debug.py --root "D:\\centenary\\Database" --out ocr_results_debug.jsonl --workers 2 --sample 200
"""
import argparse, json, os, traceback, sys
from pathlib import Path
from PIL import Image
import pytesseract
import pdfplumber
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument("--root", default=None)
parser.add_argument("--out", default="ocr_results_debug.jsonl")
parser.add_argument("--workers", type=int, default=2)
parser.add_argument("--sample", type=int, default=0)
parser.add_argument("--maxchars", type=int, default=5000)
parser.add_argument("--tesseract-cmd", default=None, help="Optional: full path to tesseract.exe")
args = parser.parse_args()

if args.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = args.tesseract_cmd

root = Path(args.root) if args.root else Path(os.environ.get("DATASET_DIR", "."))
OUT = Path(args.out)
ERRLOG = Path("ocr_errors.log")
IMG_EXT = {'.jpg','.jpeg','.png','.tif','.tiff','.bmp','.webp','.avif'}

def safe_ocr_image(path: Path):
    try:
        img = Image.open(path)
        img = img.convert("L")  # grayscale
        txt = pytesseract.image_to_string(img, lang='eng')
        txt = txt.strip()
        if txt and len(txt) > 20:
            return {"path": str(path.resolve()), "text": txt[:args.maxchars]}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc(), "path": str(path.resolve())}

def safe_ocr_pdf(path: Path):
    try:
        results = []
        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages[:5]):
                im = page.to_image(resolution=150).original
                txt = pytesseract.image_to_string(im, lang='eng')
                txt = txt.strip()
                if txt and len(txt) > 20:
                    results.append({"path": f"{path.resolve()}::page_{i+1}", "text": txt[:args.maxchars]})
        return results
    except Exception as e:
        return [{"error": str(e), "trace": traceback.format_exc(), "path": str(path.resolve())}]

def iter_candidates():
    for p in root.rglob("*"):
        if p.is_file():
            if p.suffix.lower() in IMG_EXT or p.suffix.lower() == ".pdf":
                yield p

def main():
    files = list(iter_candidates())
    if args.sample and args.sample > 0:
        files = files[:args.sample]

    count = 0
    written = 0
    with OUT.open("w", encoding="utf-8") as fout, ERRLOG.open("a", encoding="utf-8") as elog:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {}
            for p in files:
                if p.suffix.lower() == ".pdf":
                    futures[ex.submit(safe_ocr_pdf, p)] = p
                else:
                    futures[ex.submit(safe_ocr_image, p)] = p

            for fut in tqdm(as_completed(futures), total=len(futures), desc="ocr-debug"):
                count += 1
                res = fut.result()
                # if res is a list (pdf pages)
                if isinstance(res, list):
                    for item in res:
                        if "error" in item:
                            elog.write(json.dumps(item, ensure_ascii=False) + "\n")
                        else:
                            fout.write(json.dumps(item, ensure_ascii=False) + "\n")
                            written += 1
                else:
                    if res is None:
                        pass
                    elif "error" in res:
                        elog.write(json.dumps(res, ensure_ascii=False) + "\n")
                    else:
                        fout.write(json.dumps(res, ensure_ascii=False) + "\n")
                        written += 1

                # flush every 100 processed files so we have partial output
                if count % 100 == 0:
                    fout.flush()
                    elog.flush()
        # final flush
        fout.flush()
        elog.flush()
    print(f"Processed {count} tasks, wrote {written} OCR outputs. Errors logged to {ERRLOG}")

if __name__ == "__main__":
    main()
