# scripts/tts_offline_pyttsx3_run.py
import json, time, os
from pathlib import Path
import pyttsx3

narr = json.load(open("narration.json", encoding="utf-8"))
outdir = Path("audio")
outdir.mkdir(exist_ok=True)

engine = pyttsx3.init()
rate = engine.getProperty("rate")
engine.setProperty("rate", int(rate * 0.95))  # slightly slower
voices = engine.getProperty("voices")
# print voice list once (comment out after picking)
print("voices:", [v.name for v in voices])
if voices:
    # pick first voice (change index if you want another)
    engine.setProperty("voice", voices[0].id)

for item in narr:
    idx = int(item["id"])
    outpath = outdir / f"narration_{idx:02d}.wav"
    text = item["text"]
    engine.save_to_file(text, str(outpath))
    engine.runAndWait()
    # short pause so OS flushes file
    time.sleep(0.15)
    print("Wrote", outpath, "size KB:", round(os.path.getsize(outpath)/1024,2))
