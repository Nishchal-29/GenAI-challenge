# scripts/merge_narration_wave.py
"""
Merge all audio/narration_*.wav into audio/merged_narration.wav using Python's wave module.
Works only for PCM WAV files that share the same:
  - nchannels
  - sampwidth (bytes per sample)
  - framerate (sample rate)
If files differ, the script will print diagnostics and exit.
"""
import wave, contextlib, os
from pathlib import Path

AUDIO_DIR = Path("audio")
OUT = AUDIO_DIR / "merged_narration.wav"

def list_wavs():
    return sorted(AUDIO_DIR.glob("narration_*.wav"))

def inspect_wav(p):
    with contextlib.closing(wave.open(str(p),'rb')) as w:
        return {
            "path": str(p.resolve()),
            "nchannels": w.getnchannels(),
            "sampwidth": w.getsampwidth(),
            "framerate": w.getframerate(),
            "nframes": w.getnframes(),
            "comptype": w.getcomptype(),
            "compname": w.getcompname()
        }

def main():
    wavs = list_wavs()
    if not wavs:
        print("No narration WAVs found in ./audio")
        return

    print("Found", len(wavs), "files:")
    for p in wavs:
        print(" ", p.name)

    infos = [inspect_wav(p) for p in wavs]
    first = infos[0]
    mismatch = False
    for i,info in enumerate(infos[1:], start=2):
        for k in ("nchannels","sampwidth","framerate","comptype"):
            if info[k] != first[k]:
                print(f"FORMAT MISMATCH at file #{i} ({Path(info['path']).name}): {k} differs ({info[k]} != {first[k]})")
                mismatch = True

    if mismatch:
        print("\nFiles have different audio params. You can either:")
        print(" - Install ffmpeg and run the ffmpeg concat method (recommended), or")
        print(" - Re-generate narration WAVs with same params, or")
        print(" - Let this script convert via ffmpeg (if ffmpeg installed).")
        return

    # All good — concatenate frames
    with contextlib.closing(wave.open(str(OUT),'wb')) as outwav:
        outwav.setnchannels(first['nchannels'])
        outwav.setsampwidth(first['sampwidth'])
        outwav.setframerate(first['framerate'])
        total_frames = 0
        for p in wavs:
            with contextlib.closing(wave.open(str(p),'rb')) as r:
                frames = r.readframes(r.getnframes())
                outwav.writeframes(frames)
                total_frames += r.getnframes()
    print("Wrote", OUT, "total frames:", total_frames)

if __name__ == "__main__":
    main()
