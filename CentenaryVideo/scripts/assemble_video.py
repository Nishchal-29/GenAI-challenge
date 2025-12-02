#!/usr/bin/env python3
"""
Offline Sync Video Pipeline:
 1. Reads narration.json.
 2. Generates Audio using OFFLINE TTS (pyttsx3) - No Internet Needed.
 3. Creates 1 Video Segment per ID.
 4. Creates 1 Subtitle Block per ID.
 5. Concatenates and Burns.
"""

import json
import subprocess
import os
import sys
import textwrap
import wave
import contextlib
from pathlib import Path

# --- Configuration ---
ROOT = Path.cwd()
ASSETS = ROOT / "assets"
AUDIO_DIR = ROOT / "audio"
NARRATION_JSON = ROOT / "narration.json"
TMP = ROOT / "tmp_video_segments"
OUT = ROOT / "final_video.mp4"

FPS = 30
WIDTH = 1280
HEIGHT = 720
CRF = 18
FONT_SIZE = 16
SUBTITLE_WIDTH = 60 

def run(cmd):
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error cmd: {cmd}")
        print(e.stderr.decode())
        sys.exit(1)

def ensure_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        print("ERROR: ffmpeg not found. Please install it.")
        sys.exit(1)

def load_narration():
    if not NARRATION_JSON.exists():
        print("ERROR: narration.json missing.")
        sys.exit(1)
    with open(NARRATION_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return sorted(data, key=lambda x: int(x.get("id", 0)))

def generate_missing_audio_offline(narration):
    """
    Generates audio files using pyttsx3 (Offline).
    """
    AUDIO_DIR.mkdir(exist_ok=True)
    
    try:
        import pyttsx3
    except ImportError:
        print("ERROR: 'pyttsx3' not found. Run: pip install pyttsx3")
        sys.exit(1)

    print("Checking audio files (Offline Engine)...")
    
    # Initialize Engine
    engine = pyttsx3.init()
    # You can adjust rate (speed) here. Default is usually around 200.
    engine.setProperty('rate', 200) 
    
    for item in narration:
        nid = item['id']
        text = item['text']
        wav_path = AUDIO_DIR / f"narration_{nid:02d}.wav"
        
        if wav_path.exists():
            continue

        print(f"Generating audio for ID {nid}...")
        
        # pyttsx3 saves directly to wav, no conversion needed!
        # We must use absolute paths for pyttsx3 sometimes
        abs_path = str(wav_path.resolve())
        
        engine.save_to_file(text, abs_path)
        engine.runAndWait() # Block until done

def get_audio_duration(path: Path):
    try:
        with contextlib.closing(wave.open(str(path), 'rb')) as w:
            return w.getnframes() / float(w.getframerate())
    except:
        # fallback ffprobe
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
        return float(subprocess.check_output(cmd).decode().strip())

def create_video_segment(img_path, duration, output_path):
    fade_d = 0.5
    vf = (
        f"scale=w={WIDTH}:h={HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,"
        f"fade=t=in:st=0:d={fade_d},"
        f"fade=t=out:st={duration-fade_d}:d={fade_d}"
    )
    
    cmd = [
        "ffmpeg", "-y", "-loop", "1",
        "-i", str(img_path),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(CRF),
        str(output_path)
    ]
    run(cmd)

def create_srt_file(narration, srt_path):
    current_time = 0.0
    
    def fmt_time(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, item in enumerate(narration, start=1):
            dur = item['real_duration']
            start = current_time
            end = current_time + dur - 0.1
            
            wrapped_text = textwrap.fill(item['text'], width=SUBTITLE_WIDTH)
            
            f.write(f"{i}\n")
            f.write(f"{fmt_time(start)} --> {fmt_time(end)}\n")
            f.write(f"{wrapped_text}\n\n")
            
            current_time += dur
    return srt_path

def main():
    ensure_ffmpeg()
    TMP.mkdir(exist_ok=True)
    ASSETS.mkdir(exist_ok=True)
    
    narration = load_narration()
    
    images = sorted([p for p in ASSETS.iterdir() if p.suffix.lower() in [".jpg", ".png", ".jpeg"]])
    if not images:
        print("ERROR: No images in assets/ folder.")
        sys.exit(1)
        
    # --- CHANGED: Use Offline Generator ---
    generate_missing_audio_offline(narration)
    
    segment_files = []
    audio_files = []
    
    print("Processing segments...")
    for i, item in enumerate(narration):
        nid = item['id']
        wav_path = AUDIO_DIR / f"narration_{nid:02d}.wav"
        
        if not wav_path.exists():
            print(f"CRITICAL ERROR: Audio file {wav_path} was not generated.")
            sys.exit(1)

        duration = get_audio_duration(wav_path)
        item['real_duration'] = duration
        
        img_path = images[i % len(images)]
        seg_path = TMP / f"seg_{nid:03d}.mp4"
        
        print(f" ID {nid}: Audio={duration:.2f}s | Img={img_path.name}")
        create_video_segment(img_path, duration, seg_path)
        
        segment_files.append(seg_path)
        audio_files.append(wav_path)

    print("Concatenating video...")
    concat_list = TMP / "concat_list.txt"
    with open(concat_list, "w") as f:
        for p in segment_files:
            f.write(f"file '{str(p).replace(chr(39), '')}'\n")
            
    video_only = TMP / "video_only.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(video_only)])

    print("Concatenating audio...")
    audio_list = TMP / "audio_list.txt"
    with open(audio_list, "w") as f:
        for p in audio_files:
            f.write(f"file '{str(p).replace(chr(39), '')}'\n")
            
    audio_full = TMP / "audio_full.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_list), "-c", "copy", str(audio_full)])

    print("Generating subtitles...")
    srt_path = TMP / "subs.srt"
    create_srt_file(narration, srt_path)

    print("Rendering final video...")
    style = (
        f"FontName=Arial,FontSize={FONT_SIZE},MarginV=30,Alignment=2,"
        "BorderStyle=3,Outline=1,Shadow=0,BackColour=&H80000000,Bold=1"
    )
    srt_arg = str(srt_path).replace("\\", "/").replace(":", "\\:")
    
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_only),
        "-i", str(audio_full),
        "-vf", f"subtitles='{srt_arg}':force_style='{style}'",
        "-c:v", "libx264", "-preset", "fast", "-crf", str(CRF),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(OUT)
    ]
    run(cmd)

    print(f"\nDONE! Output: {OUT}")

if __name__ == "__main__":
    main()