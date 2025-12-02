# scripts/dedupe_and_rank_facts.py
"""
Deduplicate and rank candidate facts.
Outputs:
 - facts_deduped.jsonl (all unique)
 - facts_top.jsonl (top N by score)
 - facts_top.csv (human inspect)
Run:
python .\\scripts\\dedupe_and_rank_facts.py --in facts_extracted.jsonl --out facts_deduped.jsonl --top 200
"""
import argparse, json, re
from pathlib import Path
from collections import defaultdict
from difflib import SequenceMatcher
import csv

parser = argparse.ArgumentParser()
parser.add_argument("--in", dest="inp", default="facts_extracted.jsonl")
parser.add_argument("--out", default="facts_deduped.jsonl")
parser.add_argument("--top", type=int, default=200)
parser.add_argument("--threshold", type=float, default=0.85, help="text similarity threshold for dedupe")
args = parser.parse_args()

def similarity(a,b):
    return SequenceMatcher(None, a, b).ratio()

def load_all(p):
    res=[]
    with open(p, encoding='utf-8') as f:
        for line in f:
            try:
                res.append(json.loads(line))
            except:
                continue
    return res

records = load_all(args.in)
# sort by score desc then tokens desc
records.sort(key=lambda r:(-r.get('score',0), -r.get('tokens',0)))

kept = []
texts = []

for r in records:
    s = r['sentence']
    skip=False
    for t in texts:
        if similarity(s, t) >= args.threshold:
            skip=True
            break
    if not skip:
        kept.append(r)
        texts.append(s)

# write deduped all
with open(args.out, 'w', encoding='utf-8') as fout:
    for r in kept:
        fout.write(json.dumps(r, ensure_ascii=False) + '\n')

# write top N
topn = kept[:args.top]
with open("facts_top.jsonl", "w", encoding='utf-8') as fout:
    for r in topn:
        fout.write(json.dumps(r, ensure_ascii=False) + '\n')

# csv for inspect
with open("facts_top.csv", "w", encoding='utf-8', newline='') as csvf:
    writer = csv.writer(csvf)
    writer.writerow(["rank","score","year","tokens","sentence","source"])
    for i,r in enumerate(topn, start=1):
        writer.writerow([i, r.get('score'), r.get('year'), r.get('tokens'), r.get('sentence'), r.get('source')])

print("Deduped:", len(kept), "Top saved:", len(topn))
