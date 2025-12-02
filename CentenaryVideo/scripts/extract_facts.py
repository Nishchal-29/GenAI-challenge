# scripts/extract_facts_and_ner.py
"""
Create facts_extracted.jsonl from facts_raw.jsonl + ocr_results.jsonl.
Outputs one JSON per candidate fact:
{
  "id": "auto uuid",
  "source": "/full/path/origin",
  "sentence": "...",
  "year": "YYYY" or null,
  "dates": ["2024-10-16", ...] optional,
  "ents": [{"text":"IIT Dhanbad","label":"ORG"},...],
  "score": float (0-10),
  "tokens": N
}
Run:
python .\\scripts\\extract_facts_and_ner.py --facts facts_raw.jsonl --ocr ocr_results.jsonl --out facts_extracted.jsonl --workers 4 --sample 0
"""
import argparse, json, re, uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import spacy
from dateutil import parser as dateparser

parser = argparse.ArgumentParser()
parser.add_argument("--facts", default="facts_raw.jsonl")
parser.add_argument("--ocr", default="ocr_results.jsonl")
parser.add_argument("--out", default="facts_extracted.jsonl")
parser.add_argument("--workers", type=int, default=4)
parser.add_argument("--sample", type=int, default=0, help="if >0 process only this many source docs")
args = parser.parse_args()

nlp = spacy.load("en_core_web_sm", disable=["parser"])  # we only need NER / tokenization

YEAR_RE = re.compile(r'\b(18|19|20)\d{2}\b')
DATE_RE = re.compile(r'\b(?:\d{1,2}[-/]\d{1,2}[-/](?:\d{2,4})|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b')

def load_sources():
    sources = []
    for fn in (args.facts, args.ocr):
        p = Path(fn)
        if not p.exists():
            continue
        with p.open(encoding='utf-8') as f:
            for line in f:
                try:
                    r = json.loads(line)
                    sources.append(r)
                except:
                    continue
    return sources

def sentences_from_text(text, max_sent_len=400):
    # naive split using spaCy sentencizer
    doc = nlp(text)
    sents = []
    for sent in doc.sents:
        t = sent.text.strip()
        if len(t) < 20: 
            continue
        if len(t) > max_sent_len:
            t = t[:max_sent_len]  # clip
        sents.append(t)
    return sents

def find_years(sent):
    years = YEAR_RE.findall(sent)
    # YEAR_RE.findall returns tuples due to grouping; use a different findall:
    years = re.findall(r'\b(18|19|20)(\d{2})\b', sent)
    if years:
        return [y[0]+y[1] for y in years]
    # fallback try parse any date-like text
    try:
        d = dateparser.parse(sent, fuzzy=True)
        if d:
            return [str(d.year)]
    except:
        pass
    return []

def process_source(src):
    out = []
    text = src.get("text","")
    source_path = src.get("path", src.get("source", "<unknown>"))
    # split into sentences using spaCy (nlp)
    doc = nlp(text)
    for sent in doc.sents:
        s = sent.text.strip()
        if len(s) < 20: 
            continue
        # skip if it's a boilerplate line (very short or contains 'copyright' etc)
        low = s.lower()
        if "copyright" in low or "advertisement" in low or "cookie" in low:
            continue
        # get entities
        sdoc = nlp(s)
        ents = [{"text":e.text, "label":e.label_} for e in sdoc.ents]
        years = find_years(s)
        # build score heuristics
        score = 0.0
        if years: score += 3.0
        # entities boost
        for e in ents:
            if e['label'] in ('ORG','PERSON','GPE','EVENT','DATE'):
                score += 1.0
        # length penalty/bonus
        toks = len([t for t in sdoc if not t.is_punct and not t.is_space])
        score += min(2, toks/25.0)
        out.append({
            "id": str(uuid.uuid4()),
            "source": source_path,
            "sentence": s,
            "year": years[0] if years else None,
            "years_all": years,
            "ents": ents,
            "score": round(score,3),
            "tokens": toks
        })
    return out

def main():
    sources = load_sources()
    if args.sample and args.sample>0:
        sources = sources[:args.sample]
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(process_source, s): s for s in sources}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="processing sources"):
            try:
                res = fut.result()
                if res:
                    results.extend(res)
            except Exception as e:
                continue
    # write out
    outp = Path(args.out)
    with outp.open('w', encoding='utf-8') as fout:
        for r in results:
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("Wrote", outp, "with", len(results), "candidate facts")

if __name__ == "__main__":
    main()
