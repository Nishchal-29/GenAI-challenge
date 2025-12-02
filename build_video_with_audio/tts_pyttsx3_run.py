# scripts/tts_offline_pyttsx3_run.py
import json, time, os
from pathlib import Path
import pyttsx3

narr = json.load(open("narration.json", encoding="utf-8"))
outdir = Path("audio")
outdir.mkdir(exist_ok=True)

print("Total narration items:", len(narr))

engine = pyttsx3.init()
rate = engine.getProperty("rate")
engine.setProperty("rate", int(rate * 0.95))  # slightly slower
voices = engine.getProperty("voices")
print("voices:", [v.name for v in voices])
if voices:
    engine.setProperty("voice", voices[0].id)

queued = 0
for i, item in enumerate(narr, start=1):
    # Basic validation
    if not isinstance(item, dict) or "text" not in item:
        print(f"Skipping item #{i}: invalid structure:", item)
        continue

    # Use enumerated index to guarantee unique files even if IDs are missing/duplicate
    outpath = outdir / f"narration_{i:03d}.wav"
    text = str(item.get("text", "")).strip()
    if not text:
        print(f"Skipping item #{i}: empty text")
        continue

    try:
        engine.save_to_file(text, str(outpath))
        queued += 1
        print(f"Queued {outpath}")
    except Exception as e:
        print(f"Error queueing item #{i}: {e}")

# Run all queued TTS jobs once (more reliable)
print("Running engine.runAndWait() for", queued, "items...")
engine.runAndWait()
# short pause to allow OS to flush file handles
time.sleep(0.25)

# Print actual sizes
for i in range(1, len(narr)+1):
    p = outdir / f"narration_{i:03d}.wav"
    if p.exists():
        print("Wrote", p, "size KB:", round(os.path.getsize(p)/1024, 2))
