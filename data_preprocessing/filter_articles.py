# filter_and_score.py
"""
Filter the extracted articles for IIT/ISM related content; compute a relevance score; dedupe similar items.
Outputs: preprocessed/articles_filtered.json
"""

import json, os, re
from collections import defaultdict
from difflib import SequenceMatcher
from tqdm import tqdm

IN_FN = "preprocessed/articles_raw.json"
OUT_FN = "preprocessed/articles_filtered.json"

# keywords / variants to match IIT (ISM) mentions
KEYWORDS = [
    r"\bIIT\b", r"\bISM\b", r"\bIIT\s*\(ISM\)\b", r"\bIIT\s*ISM\b",
    r"\bIndian School of Mines\b", r"\bDhanbad\b", r"\bI\.I\.T\b"
]
KEYWORD_REGEX = re.compile("|".join(KEYWORDS), re.I)

# extra tokens that raise importance if present
IMPORTANCE_WORDS = ["centenary", "students", "established", "inaugur", "campus", "department", "alumni", "rank", "award", "research", "laboratory", "campus", "admission", "convocation", "faculty", "placements"]

def score_text_snippet(txt):
    score = 0
    if not txt:
        return 0
    # base: count keyword hits
    kw_hits = len(re.findall(KEYWORD_REGEX, txt))
    score += kw_hits * 3
    # importance terms
    for w in IMPORTANCE_WORDS:
        if re.search(r"\b"+re.escape(w)+r"\b", txt, re.I):
            score += 1
    # length bonus (presence of context)
    words = txt.split()
    if len(words) > 30:
        score += min(3, len(words)//100)
    return score

def similarity(a,b):
    return SequenceMatcher(None, a, b).ratio()

def main():
    if not os.path.exists(IN_FN):
        print("Run extract_articles.py first. Missing:", IN_FN)
        return
    with open(IN_FN, "r", encoding="utf8") as f:
        articles = json.load(f)
    candidates = []
    for art in articles:
        # combine title + headings + first several paragraphs
        title = art.get("title","") or ""
        heads = " ".join(art.get("headings",[]))
        paras = " ".join(art.get("paragraphs",[]))
        combined = " ".join([title, heads, paras])[:10000]
        # compute base hits of keywords
        if not re.search(KEYWORD_REGEX, combined):
            # skip if no IIT/ISM mention anywhere
            continue
        sc = score_text_snippet(combined)
        # pick best image (prefer local file path)
        image = None
        for im in art.get("images",[]):
            src = im.get("src")
            if src and (src.startswith("/") or src.startswith("news_articles") or src.startswith("news_articles/") or src.startswith("./")):
                image = src; break
        if not image and art.get("images"):
            image = art["images"][0]["src"]
        # prepare snippet: first 2 meaningful sentences mentioning keywords
        sentences = re.split(r'(?<=[.!?])\s+', combined)
        snippet = ""
        for s in sentences:
            if re.search(KEYWORD_REGEX, s):
                snippet += (s.strip()+" ")
                if len(snippet.split()) > 40:
                    break
        if not snippet:
            snippet = " ".join(sentences[:2])[:300]
        candidates.append({
            "source_html": art.get("source_html"),
            "title": title,
            "date": art.get("extracted_date"),
            "snippet": snippet.strip(),
            "score": sc,
            "image": image
        })
    # deduplicate by similar snippet (keep highest score)
    final = []
    used = [False]*len(candidates)
    for i,a in enumerate(sorted(candidates, key=lambda x:-x["score"])):  # process from high score
        if used[i]:
            continue
        group = [a]
        used[i] = True
        for j,b in enumerate(candidates):
            if used[j]: continue
            if similarity(a["snippet"], b["snippet"]) > 0.85:
                used[j] = True
                group.append(b)
        # merge group -> pick highest score entry as canonical
        canonical = sorted(group, key=lambda x:-x["score"])[0]
        # add provenance list
        canonical["provenance_group"] = [{"source_html":g["source_html"], "score":g["score"]} for g in group]
        final.append(canonical)
    # sort by date (newest first if date present) then score
    def keyfn(x):
        date = x.get("date") or ""
        return (date, x.get("score",0))
    final = sorted(final, key=keyfn, reverse=True)
    os.makedirs(os.path.dirname(OUT_FN), exist_ok=True)
    with open(OUT_FN, "w", encoding="utf8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)
    print("Wrote", OUT_FN, "articles:", len(final))

if __name__ == "__main__":
    main()
