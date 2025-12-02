# scripts/select_beats.py
"""
Select beats (final storyboard) from facts_top.jsonl.
Outputs beats.json with entries:
{
 "id": 1,
 "fact": "...",
 "year": "YYYY" or null,
 "source": "path",
 "images": ["D:\\...\\img1.jpg"] (maybe empty),
 "duration": 9,
 "caption": "short caption"
}
Run:
python .\\scripts\\select_beats.py --in facts_top.jsonl --out beats.json --beats 12
"""
import argparse, json, os
from pathlib import Path
from collections import defaultdict

parser = argparse.ArgumentParser()
parser.add_argument("--in", dest="inp", default="facts_top.jsonl")
parser.add_argument("--out", default="beats.json")
parser.add_argument("--beats", type=int, default=12)
parser.add_argument("--image_extensions", default=".jpg,.jpeg,.png,.webp,.png,.gif")
args = parser.parse_args()

image_exts = set([e.strip().lower() for e in args.image_extensions.split(",")])

def find_images_near(source_path, limit=3):
    p = Path(source_path)
    candidates = []
    # if source is an HTML folder, look in same dir and parent dirs
    search_dirs = [p.parent, p.parent.parent, p.parent.parent.parent]
    for d in search_dirs:
        if not d or not d.exists(): continue
        for ext in image_exts:
            for f in d.glob(f"*{ext}"):
                candidates.append(str(f.resolve()))
    # fallback: empty
    return candidates[:limit]

# load top facts
facts=[]
with open(args.in, encoding='utf-8') as f:
    for line in f:
        try:
            facts.append(json.loads(line))
        except:
            continue

selected=[]
used_years=set()
i=0
for f in facts:
    if len(selected) >= args.beats:
        break
    year = f.get('year')
    # try diversity by year: allow at most 2 facts per year
    if year:
        # count usage
        c = sum(1 for s in selected if s.get('year')==year)
        if c >= 2:
            continue
    # add
    images = find_images_near(f.get('source','')) or []
    caption = f['sentence'][:80] if len(f['sentence'])>80 else f['sentence']
    i += 1
    beat = {
        "id": i,
        "fact": f['sentence'],
        "year": year,
        "source": f.get('source'),
        "images": images,
        "duration": 9,
        "caption": caption
    }
    selected.append(beat)

# adjust durations to match ~120s: compute total current and scale
total = sum(b['duration'] for b in selected) + 4 + 6  # + intro/outro
target = 120
if total != target and selected:
    scale = (target - 10) / (total - 10)  # subtract intro/outro
    for b in selected:
        b['duration'] = max(6, round(b['duration'] * scale))

with open(args.out, "w", encoding='utf-8') as fout:
    json.dump(selected, fout, ensure_ascii=False, indent=2)

print("Wrote beats:", args.out, "beats:", len(selected))
