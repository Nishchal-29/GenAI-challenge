# genai_calls/generate_tts_gemini_fixed.py
import os, json, wave, base64
from pathlib import Path
from google import genai
from google.genai import types

PROMPTS_FILE = Path("genai_inputs/narration_prompts.json")
OUT_DIR = Path("assets/tts")
OUT_DIR.mkdir(parents=True, exist_ok=True)

from dotenv import load_dotenv
load_dotenv()

def write_pcm_to_wav(pcm_bytes: bytes, out_path: Path, channels=1, sample_rate=24000, width_bytes=2):
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width_bytes)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY in environment")

    client = genai.Client(api_key=api_key)
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    manifest = []
    for entry in prompts:
        idx = entry.get("scene_index")
        prompt = entry.get("narration_prompt", "").strip()
        if not prompt:
            continue

        print(f"[Scene {idx}] -> sending to Gemini TTS ...")
        resp = client.models.generate_content(
            model="gemini-2.5-pro-preview-tts",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                    )
                )
            )
        )
        # Get base64-encoded audio
        b64 = resp.candidates[0].content.parts[0].inline_data.data
        if not b64 or not isinstance(b64, str):
            print("❌ Scene", idx, " — no audio data returned or wrong type:", type(b64))
            manifest.append({"scene_index": idx, "status": "error", "error": "no audio data"})
            continue

        pcm = base64.b64decode(b64)
        if len(pcm) == 0:
            print("❌ Scene", idx, " — decoded audio is empty")
            manifest.append({"scene_index": idx, "status": "error", "error": "empty audio"})
            continue

        out_file = OUT_DIR / f"scene_{idx:02d}.wav"
        write_pcm_to_wav(pcm, out_file)
        print("✅ Scene", idx, " — WAV written:", out_file)
        manifest.append({"scene_index": idx, "status": "ok", "filename": str(out_file)})

    with open("genai_inputs/tts_manifest.json", "w", encoding="utf-8") as f:
        json.dump({"entries": manifest}, f, indent=2)
    print("Done — manifest saved.")
    
if __name__ == "__main__":
    main()
