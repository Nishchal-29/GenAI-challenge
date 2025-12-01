# data_ingest/extract_website.py
import os, json, re
from pathlib import Path
from bs4 import BeautifulSoup
from readability import Document
from dateutil import parser as dateparser
from tqdm import tqdm

HTML_ROOT = Path("website_crawls/dataset/html")    # adjust if your dataset uses a different path
IMAGES_ROOT = Path("website_crawls/dataset/images")  # for resolving relative image files
OUT_JSON = Path("preprocessed/website_index.json")

def guess_date(soup, filepath):
    # search many possible meta/time fields
    selectors = [
        ("meta", {"property":"article:published_time"}),
        ("meta", {"name":"pubdate"}),
        ("meta", {"name":"publishdate"}),
        ("meta", {"name":"date"}),
        ("meta", {"itemprop":"datePublished"}),
        ("time", {}),
    ]
    for tag, attrs in selectors:
        if tag == "time":
            t = soup.find("time")
            if t:
                v = t.get("datetime") or t.text
                if v:
                    try:
                        return dateparser.parse(v)
                    except Exception:
                        pass
        else:
            m = soup.find(tag, attrs=attrs)
            if m:
                v = m.get("content") or m.get("value") or m.get("datetime") or m.text
                if v:
                    try:
                        return dateparser.parse(v)
                    except Exception:
                        pass
    # fallback: try filename
    fn = os.path.basename(filepath)
    m = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", fn)
    if m:
        try:
            return dateparser.parse(m.group(1))
        except Exception:
            pass
    return None

def extract_main(html_bytes):
    try:
        doc = Document(html_bytes)
        summary_html = doc.summary()
        soup = BeautifulSoup(summary_html, "lxml")
    except Exception:
        soup = BeautifulSoup(html_bytes, "lxml")
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1","h2","h3"])][:5]
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")][:40]

    # images in main content
    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original")
        if not src: continue
        alt = img.get("alt") or ""
        caption = ""
        fig = img.find_parent("figure")
        if fig:
            cap = fig.find("figcaption")
            if cap:
                caption = cap.get_text(" ", strip=True)
        images.append({"src": src, "alt": alt, "caption": caption})
    return headings, paragraphs, images

def normalize_src(src, html_path):
    if not src: return None
    src = src.strip()
    if src.startswith("http://") or src.startswith("https://"):
        return src
    # relative: resolve relative to html file
    candidate = os.path.normpath(os.path.join(os.path.dirname(html_path), src))
    if os.path.exists(candidate):
        return candidate
    # try within dataset images root by basename
    bn = os.path.basename(src)
    for root,_,files in os.walk(IMAGES_ROOT):
        if bn in files:
            return os.path.join(root, bn)
    # fallback: return original relative path
    return src

def main():
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    records = []
    if not HTML_ROOT.exists():
        print("HTML root not found:", HTML_ROOT)
        return
    html_files = [str(p) for p in HTML_ROOT.rglob("*.html")] + [str(p) for p in HTML_ROOT.rglob("*.htm")]
    for fp in tqdm(html_files, desc="Parsing HTML"):
        try:
            with open(fp, "rb") as f:
                raw = f.read()
            soup_top = BeautifulSoup(raw, "lxml")
            title = (soup_top.title.string.strip() if soup_top.title and soup_top.title.string else "")
            author = ""
            ma = soup_top.find("meta", {"name":"author"}) or soup_top.find("meta", {"property":"author"})
            if ma:
                author = (ma.get("content") or ma.get("value") or "").strip()
            headings, paragraphs, images = extract_main(raw)
            date = guess_date(soup_top, fp)
            norm_images = []
            for im in images:
                resolved = normalize_src(im.get("src"), fp)
                norm_images.append({"src": resolved, "alt": im.get("alt",""), "caption": im.get("caption","")})
            rec = {
                "source_html": fp,
                "title": title,
                "author": author,
                "date": date.isoformat() if date else None,
                "headings": headings,
                "paragraphs": paragraphs,
                "images": norm_images
            }
            records.append(rec)
        except Exception as e:
            print("Error parsing", fp, e)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print("Wrote", OUT_JSON, "entries:", len(records))

if __name__ == "__main__":
    main()
