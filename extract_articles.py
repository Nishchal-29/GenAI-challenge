# extract_articles.py
"""
Extract structured content from news_articles HTML files.
Outputs: preprocessed/articles_raw.json
Each record includes provenance: file path, extracted date, title, headings, paragraphs, images (with alt text / caption).
"""

import os, json, re
from bs4 import BeautifulSoup
from readability import Document
from dateutil import parser as dateparser
from tqdm import tqdm

INPUT_ROOT = "news_articles/dataset/html"       # change if your path differs
IMAGES_ROOT = "news_articles/dataset/images"    # optional root for resolving images
OUT_JSON = "preprocessed/articles_raw.json"

# helper: guess date from meta or filename
def extract_date(soup, filepath):
    # check meta tags common in news sites
    meta_keys = [
        ("meta", {"name":"pubdate"}),
        ("meta", {"name":"publishdate"}),
        ("meta", {"name":"publication_date"}),
        ("meta", {"property":"article:published_time"}),
        ("meta", {"name":"date"}),
        ("meta", {"itemprop":"datePublished"}),
        ("time", {}),
    ]
    for tag, attrs in meta_keys:
        if tag == "time":
            t = soup.find("time")
            if t and t.get("datetime"):
                try:
                    return dateparser.parse(t.get("datetime"))
                except Exception:
                    pass
            if t and t.text:
                try:
                    return dateparser.parse(t.text.strip())
                except Exception:
                    pass
        else:
            m = soup.find(tag, attrs=attrs)
            if m:
                v = m.get("content") or m.get("value") or m.get("datetime") or m.text
                if v:
                    try:
                        return dateparser.parse(v.strip())
                    except Exception:
                        pass
    # fallback: try to parse date from filepath name YYYY-MM-DD or YYYYMMDD
    fn = os.path.basename(filepath)
    m = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", fn)
    if m:
        try:
            return dateparser.parse(m.group(1))
        except Exception:
            pass
    m = re.search(r"(\d{8})", fn)
    if m:
        try:
            return dateparser.parse(m.group(1))
        except Exception:
            pass
    return None

def extract_main_text(html_bytes):
    # Use readability to extract main article HTML then parse with BeautifulSoup for structure
    try:
        doc = Document(html_bytes)
        content_html = doc.summary()
        soup = BeautifulSoup(content_html, "lxml")
        # headings
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1","h2","h3"]) if h.get_text(strip=True)]
        # paragraphs limited to first N meaningful ones
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        # image candidates inside main content
        images = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if not src:
                continue
            alt = img.get("alt") or ""
            # try to find nearby caption text
            caption = ""
            parent = img.parent
            if parent:
                # look for figcaption or sibling small text
                fc = parent.find("figcaption")
                if fc:
                    caption = fc.get_text(" ", strip=True)
                else:
                    # sibling small or span
                    s = parent.find("small") or parent.find("span", {"class":"caption"})
                    if s:
                        caption = s.get_text(" ", strip=True)
            images.append({"src": src, "alt": alt, "caption": caption})
        return headings, paragraphs, images
    except Exception as e:
        # fallback: basic bs4 parse
        soup = BeautifulSoup(html_bytes, "lxml")
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1","h2","h3"])][:5]
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")][:50]
        images = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src:
                images.append({"src": src, "alt": img.get("alt",""), "caption": ""})
        return headings, paragraphs, images

def normalize_src(src, base_path, images_root=IMAGES_ROOT):
    # if src is data URI, ignore
    if not src or src.strip().startswith("data:"):
        return None
    src = src.strip()
    # if absolute URL, keep as-is (we'll not download external content — but we record provenance)
    if src.startswith("http://") or src.startswith("https://"):
        return src
    # relative path: try to resolve inside the dataset folder
    # base_path is the html file folder; join and normalize
    candidate = os.path.normpath(os.path.join(os.path.dirname(base_path), src))
    if os.path.exists(candidate):
        return candidate
    # try inside images root with same basename
    bn = os.path.basename(src)
    for root,_,files in os.walk(images_root):
        if bn in files:
            return os.path.join(root, bn)
    # fallback: return original relative path (provenance only)
    return src

def main():
    os.makedirs("preprocessed", exist_ok=True)
    records = []
    if not os.path.isdir(INPUT_ROOT):
        print("Input root not found:", INPUT_ROOT)
        return
    all_files = []
    for root,dirs,files in os.walk(INPUT_ROOT):
        for fn in files:
            if fn.lower().endswith(".html") or fn.lower().endswith(".htm"):
                all_files.append(os.path.join(root,fn))
    for fp in tqdm(all_files, desc="Parsing HTML files"):
        try:
            with open(fp, "rb") as f:
                data = f.read()
            # use BeautifulSoup to get <title> and author meta
            soup_top = BeautifulSoup(data, "lxml")
            title = (soup_top.title.string.strip() if soup_top.title and soup_top.title.string else "").strip()
            # try author meta
            author = ""
            m = soup_top.find("meta", {"name":"author"}) or soup_top.find("meta", {"property":"author"})
            if m:
                author = (m.get("content") or m.get("value") or "").strip()
            # main content
            headings, paragraphs, images = extract_main_text(data)
            date = extract_date(soup_top, fp)
            rec = {
                "source_html": fp,
                "title": title,
                "author": author,
                "extracted_date": date.isoformat() if date else None,
                "headings": headings,
                "paragraphs": paragraphs,
                "images_raw": images
            }
            # normalize image src paths
            norm_images = []
            for im in images:
                resolved = normalize_src(im.get("src"), fp)
                if resolved:
                    norm_images.append({"src": resolved, "alt": im.get("alt",""), "caption": im.get("caption","")})
            rec["images"] = norm_images
            records.append(rec)
        except Exception as e:
            print("Error parsing", fp, e)
    with open(OUT_JSON, "w", encoding="utf8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print("Wrote", OUT_JSON)

if __name__ == "__main__":
    main()
