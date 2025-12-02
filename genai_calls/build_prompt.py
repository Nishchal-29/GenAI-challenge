#!/usr/bin/env python3
"""
build_gemini_transcript_prompt.py

Purpose:
 - Read dataset index files (articles_filtered.json, docs_index.json, website_index.json).
 - Extract salient facts about IIT (ISM) Dhanbad (founding, campus, academics, achievements, events).
 - Compose a single, polished model prompt instructing Gemini-2.5-flash to generate a ~2-minute
   narrated transcript for a short video showcasing "The Journey of IIT (ISM) Dhanbad".
 - Save the prompt to genai_inputs/gemini_transcript_prompt.txt

Usage:
  python genai_calls/build_gemini_transcript_prompt.py

Output:
  - genai_inputs/gemini_transcript_prompt.txt
"""

import json
from pathlib import Path
from datetime import datetime

# INPUT files (adjust paths if needed)
ARTICLES_FILE = Path("preprocessed/articles_filtered.json")   # or 'articles_filtered.json' at repo root
# DOCS_FILE     = Path("preprocessed/docs_index.json")         # or 'docs_index.json'
WEBSITE_FILE  = Path("preprocessed/website_index.json")     # or 'website_index.json'

OUT_DIR = Path("genai_inputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PROMPT_FILE = OUT_DIR / "gemini_transcript_prompt.txt"

def load_json_safe(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return None

def gather_facts(articles, website):
    facts = {
        "founding": [],
        "campus": [],
        "academics": [],
        "research_achievements": [],
        "events_workshops": [],
        "community": [],
        "recent_news": []
    }

    # 1) docs (institution brochures, workshop PDFs often have canonical facts)
    # if docs:
    #     # docs_index usually is a list or dict mapping; handle both.
    #     # We'll scan the JSON text_snippets for common evidence phrases.
    #     def scan_docs(d):
    #         if isinstance(d, list):
    #             for item in d:
    #                 txt = item.get("text_snippet","") if isinstance(item, dict) else str(item)
    #                 yield txt
    #         elif isinstance(d, dict):
    #             # top-level mapping
    #             for k,v in d.items():
    #                 if isinstance(v, list):
    #                     for item in v:
    #                         if isinstance(item, dict):
    #                             yield item.get("text_snippet","")
    #                         else:
    #                             yield str(item)
    #                 elif isinstance(v, str):
    #                     yield v
    #         else:
    #             yield str(d)

        # for txt in scan_docs(docs):
        #     if not txt:
        #         continue
        #     t = txt.strip()
        #     # founding / history
        #     if "opened on 9th December 1926" in t or "09th December 1926" in t or "formally opened on 9th December 1926" in t:
        #         facts["founding"].append("The Indian School of Mines (now IIT(ISM) Dhanbad) was formally opened on 9 December 1926.")
        #     if "campus spread over an area of" in t or "campus spread over" in t:
        #         # pick the line if available
        #         if "campus spread" in t:
        #             facts["campus"].append(t.splitlines()[0][:400])
        #     if "Workshop on Fiber Optic Sensors" in t or "WFOSA" in t:
        #         facts["events_workshops"].append("Hosted workshops such as the 'Workshop on Fiber Optic Sensors and its Applications (WFOSA)-2024' providing hands-on training and industry-standard tools.")
        #     if "Swachhata" in t or "Swachhata Hi Sewa" in t:
        #         facts["community"].append("Organised community and campus initiatives like 'Swachhata Hi Sewa' (campus cleanliness, plantation drives and outreach).")
        #     # research/technology facts (look for 'Cost effective', 'Low noise', 'mining vehicles', etc.)
        #     if "Cost effective multi armed drilling equipment" in t or "Cost Efficient" in t or "Cost effective" in t:
        #         facts["research_achievements"].append("Researchers developed cost-effective, power-efficient systems and innovations for mining and engineering applications.")
        #     # generic fallback - add any line referencing 'IIT(ISM)'
        #     if "IIT(ISM)" in t or "Indian Institute of Technology (Indian School of Mines)" in t:
        #         facts["founding"].append(t[:500])

    # 2) website index (site pages containing headings and paragraph content)
    if website:
        # website is an array of page dicts in many dumps; scan headings and paragraphs
        pages = website if isinstance(website, list) else website.get("pages", website)
        if isinstance(pages, list):
            for page in pages:
                title = page.get("title","")
                if "IIT (ISM)" in title or "INDIAN INSTITUTE OF TECHNOLOGY" in title:
                    # headings and paragraphs commonly include canonical lines
                    paras = page.get("paragraphs",[]) or []
                    for p in paras:
                        if not p: 
                            continue
                        if "Standing tall since early decades of 20th century" in p:
                            facts["founding"].append("The institute has 'stood tall since the early decades of the 20th century' and has expanded into a full-fledged technology institute.")
                        if "offers" in p and ("B. Tech" in p or "PhD" in p or "M.Tech" in p or "postgraduate" in p.lower()):
                            facts["academics"].append("Offers undergraduate, postgraduate and PhD programmes across engineering, sciences, management and humanities.")
                        if "Recent Achievements" in p or "achievements" in p.lower():
                            facts["research_achievements"].append(p.strip()[:])
                # look for image captions mentioning 'Over 260 innovative minds' -> community/achievements
                for img in page.get("images", []):
                    cap = img.get("caption","") or img.get("alt","")
                    if cap:
                        if "innovative minds" in cap:
                            facts["research_achievements"].append(cap)
        else:
            # fallback: if site was parsed as dict with keys
            for k,v in website.items():
                if isinstance(v, list):
                    for page in v:
                        paras = page.get("paragraphs",[]) if isinstance(page, dict) else []
                        for p in paras:
                            if p and "offers" in p:
                                facts["academics"].append(p.strip()[:])

    # 3) articles_filtered.json (news snippets)
    if articles:
        # gather a handful of recent headlines/snippets referencing IIT(ISM)
        items = articles if isinstance(articles, list) else articles.get("items", [])
        picked = 0
        for it in items:
            if picked >= 100:
                break
            title = it.get("title","") or it.get("headline","")
            snippet = it.get("snippet","") or it.get("summary","")
            if not title and not snippet:
                continue
            # only choose pieces that mention IIT or ISM
            combined = " ".join([title, snippet]).strip()
            if "IIT" in combined or "ISM" in combined or "IIT(ISM)" in combined or "Dhanbad" in combined:
                facts["recent_news"].append((title.strip(), (snippet or "")[:]))
                picked += 1

    # dedupe short lists
    for k in facts:
        # keep unique preserving order
        seen = set()
        new = []
        for x in facts[k]:
            if x not in seen:
                new.append(x)
                seen.add(x)
        facts[k] = new

    return facts

def build_prompt_text(facts):
    """
    Build a single textual prompt that:
     - Gives context to the LLM about allowed source material (the facts we extracted)
     - Supplies the factual list
     - Issues an instruction to produce a ~2-minute transcript (300 +/- 40 words),
       narrated in an engaging, evocative tone, not verbatim copying.
     - Enforce: all factual claims must be drawn from the supplied facts only.
    """
    header = [
        "You are an expert scriptwriter for short documentary-style videos.",
        "Goal: produce a single narrated transcript (~300 words, +/- 40 words) designed to be spoken as a ~2-minute voiceover for a short video titled: 'The Journey of IIT (ISM) Dhanbad'.",
        "Constraints:",
        "  1) Use ONLY the factual points listed below (these are extracted from the official dataset). Do NOT invent dates or claims not present here.",
        "  2) Do NOT copy any paragraph verbatim from the dataset; instead, *rephrase and synthesize* those facts into a concise, vivid, narrative suitable for voiceover.",
        "  3) Tone: Proud, reflective, optimistic. Make it engaging for a general audience (prospective students, alumni, and the public).",
        "  4) Target length: approximately 300 words (2 minutes of narration).",
        "  5) Add short scene-break annotations in square brackets like [SCENE: Campus sunrise] at 2–3 places to suggest visuals for the video.",
        "",
        "Factual source points (ONLY use these directly or paraphrase them):",
        ""
    ]
    body_lines = []

    # Founding
    if facts["founding"]:
        body_lines.append("FOUNDING & HISTORY:")
        for f in facts["founding"]:
            body_lines.append(f"- " + f.strip())
        body_lines.append("")

    # Campus
    if facts["campus"]:
        body_lines.append("CAMPUS:")
        for f in facts["campus"]:
            body_lines.append(f"- " + f.strip())
        body_lines.append("")

    # Academics
    if facts["academics"]:
        body_lines.append("ACADEMICS & PROGRAMS:")
        for f in facts["academics"]:
            body_lines.append(f"- " + f.strip())
        body_lines.append("")

    # Research and achievements
    if facts["research_achievements"]:
        body_lines.append("RESEARCH & ACHIEVEMENTS:")
        for f in facts["research_achievements"][:6]:
            body_lines.append(f"- " + f.strip())
        body_lines.append("")

    # Events & workshops
    if facts["events_workshops"]:
        body_lines.append("EVENTS & WORKSHOPS:")
        for f in facts["events_workshops"]:
            body_lines.append(f"- " + f.strip())
        body_lines.append("")

    # Community
    if facts["community"]:
        body_lines.append("COMMUNITY & OUTREACH:")
        for f in facts["community"]:
            body_lines.append(f"- " + f.strip())
        body_lines.append("")

    # Recent news snippets
    if facts["recent_news"]:
        body_lines.append("SOME NEWS HIGHLIGHTS:")
        for title, snip in facts["recent_news"][:]:
            if title:
                body_lines.append(f"- {title.strip()} | {snip.strip()}")
            else:
                body_lines.append("- " + snip.strip())
        body_lines.append("")

    # Final instruction
    tail = [
        "",
        "INSTRUCTION TO THE MODEL:",
        "Write a single flowing voiceover transcript (no scene-by-scene split — just the full narration).",
        "Begin with a short hook (one or two sentences). Weave the institute's history, campus life, academic breadth, research achievements, community work, and recent highlights into a coherent narrative.",
        "Do NOT add references or citations in the transcript. Keep it natural and cinematic.",
        "End with a forward-looking short sentence that expresses optimism about the future.",
        "",
        "Deliverable format: plain text only (UTF-8), ~300 words. Save the transcript as the model output.",
        ""
    ]

    prompt_text = "\n".join(header + body_lines + tail)
    return prompt_text

def main():
    articles = load_json_safe(ARTICLES_FILE) or load_json_safe(Path("articles_filtered.json")) or []
    # docs     = load_json_safe(DOCS_FILE)     or load_json_safe(Path("docs_index.json")) or []
    website  = load_json_safe(WEBSITE_FILE)  or load_json_safe(Path("website_index.json")) or []

    facts = gather_facts(articles, website)
    prompt_text = build_prompt_text(facts)

    # write the prompt to disk
    with open(OUT_PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# GENERATED PROMPT (created: {datetime.utcnow().isoformat()}Z)\n")
        f.write(prompt_text)

    print("Prompt written to:", OUT_PROMPT_FILE)
    print("Summary of extracted fact categories (counts):")
    print(" - founding:", len(facts['founding']))
    print(" - campus:", len(facts['campus']))
    print(" - academics:", len(facts['academics']))
    print(" - research_achievements:", len(facts['research_achievements']))
    print(" - events_workshops:", len(facts['events_workshops']))
    print(" - community:", len(facts['community']))
    print(" - recent_news:", len(facts['recent_news']))
    print("\nNext steps:")
    print(" - Use the generated file genai_inputs/gemini_transcript_prompt.txt as the input prompt for Gemini-2.5-flash.")
    print(" - Optionally, I can add the exact Gemini API call to run this prompt and receive the transcript directly.")

if __name__ == "__main__":
    main()
