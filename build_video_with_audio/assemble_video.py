#!/usr/bin/env python3
"""
Assemble video strictly synced to narration audio parts.

Creates:
  audio/merged_narration_sync.wav
  tmp_video_segments/seg_###.mp4
  tmp_video_segments/full_nosound.mp4
  tmp_video_segments/captions_sync.srt
  final_video_sync.mp4
"""
import json
import subprocess
import tempfile
import os
import sys
import textwrap
import uuid
from pathlib import Path

ROOT = Path.cwd()
ASSETS = ROOT / "assets"
NARR_JSON = ROOT / "narration.json"
AUDIO_DIR = ROOT / "audio"
TMP = ROOT / "tmp_video_segments"
OUT = ROOT / "final_video_sync.mp4"

FPS = 30
WIDTH = 1280
HEIGHT = 720
CRF = 20

# tiny padding for each segment (seconds)
SEGMENT_PADDING = 0.00
# fallback silence length for completely missing files (seconds)
FALLBACK_SILENCE = 0.6

def run(cmd, capture=False):
    printable = " ".join(cmd)
    print("RUN:", printable)
    if capture:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    subprocess.run(cmd, check=True)

def check_tools():
    try:
        subprocess.run(["ffmpeg","-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ffprobe","-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        print("ERROR: ffmpeg and/or ffprobe not found on PATH. Install them and re-run.")
        sys.exit(1)

def ffprobe_duration(path: Path):
    cmd = ["ffprobe","-v","error","-show_entries","format=duration",
           "-of","default=noprint_wrappers=1:nokey=1", str(path)]
    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    try:
        return float(out)
    except:
        return None

def load_narration_items():
    if not NARR_JSON.exists():
        print("ERROR: narration.json missing in project root.")
        sys.exit(1)
    data = json.load(open(NARR_JSON, encoding="utf-8"))
    try:
        data = sorted(data, key=lambda x: int(x.get("id",0)))
    except:
        pass
    items=[]
    for i,it in enumerate(data, start=1):
        text = it.get("text") or it.get("caption") or it.get("fact") or ""
        id_ = int(it.get("id", i))
        items.append({"id": id_, "text": text})
    return items

def find_narration_files(items):
    # returns list aligned with items: Path or None
    files=[]
    missing=[]
    for it in items:
        p = AUDIO_DIR / f"narration_{it['id']:02d}.wav"
        if p.exists():
            files.append(p)
        else:
            files.append(None)
            missing.append(p)
    return files, missing

def normalize_to_tmp(src: Path, dst: Path):
    # convert to 44.1k stereo PCM WAV
    cmd = ["ffmpeg","-y","-i", str(src), "-ar","44100","-ac","2","-c:a","pcm_s16le", str(dst)]
    run(cmd)

def create_silence(duration: float, out_path: Path):
    # create silence wav via anullsrc
    cmd = ["ffmpeg","-y","-f","lavfi","-i", f"anullsrc=channel_layout=stereo:sample_rate=44100", "-t", str(duration), "-c:a","pcm_s16le", str(out_path)]
    run(cmd)

def build_merged_audio_per_item(item_aligned_files, out_merged: Path):
    """
    item_aligned_files: list of Paths or None, order matches narration items
    Produces out_merged as 44.1k stereo PCM WAV by:
      - normalizing each existing file to tmp WAV
      - creating tmp silence WAVs for missing files with estimated lengths
      - concat all tmp WAVs using filter_complex concat
    Returns list of tmp files (in order) and durations list
    """
    tmp_files = []
    durations = []
    # first pass: compute durations for existing files
    existing_durs=[]
    for p in item_aligned_files:
        if p is not None:
            d = ffprobe_duration(p)
            if d is None:
                # try normalizing quickly to tmp to ensure ffprobe works
                pass
            else:
                existing_durs.append(d)
    avg = (sum(existing_durs)/len(existing_durs)) if existing_durs else 2.0

    # create normalized tmp files or silence placeholders
    try:
        for idx, p in enumerate(item_aligned_files):
            tmp = AUDIO_DIR / f"tmp_norm_{uuid.uuid4().hex[:8]}.wav"
            if p is not None:
                # normalize
                normalize_to_tmp(p, tmp)
                d = ffprobe_duration(tmp)
                if d is None:
                    d = avg
                tmp_files.append(tmp)
                durations.append(d)
            else:
                # create silence of avg or FALLBACK_SILENCE
                sil_len = avg if avg>0 else FALLBACK_SILENCE
                create_silence(sil_len, tmp)
                tmp_files.append(tmp)
                durations.append(sil_len)
        # now concat via filter_complex (no concat list)
        cmd = ["ffmpeg","-y"]
        for t in tmp_files:
            cmd += ["-i", str(t)]
        n = len(tmp_files)
        # build input stream tags [0:0][1:0]...
        inputs = "".join(f"[{i}:0]" for i in range(n))
        fc = f"{inputs}concat=n={n}:v=0:a=1[outa]"
        cmd += ["-filter_complex", fc, "-map", "[outa]", "-c:a", "pcm_s16le", "-ar","44100","-ac","2", str(out_merged)]
        run(cmd)
        # recompute durations from tmp_files (ensure exact)
        durations = [ffprobe_duration(t) or d for t,d,t in zip(tmp_files, durations, tmp_files)]
        return tmp_files, durations
    except Exception as e:
        # cleanup on error
        for t in tmp_files:
            try: t.unlink()
            except: pass
        raise

def pick_images_for_items(n_items):
    imgs = sorted([p for p in ASSETS.iterdir() if p.is_file() and p.suffix.lower() in (".jpg",".jpeg",".png",".webp",".bmp")])
    if not imgs:
        print("ERROR: No images in assets/. Put images there.")
        sys.exit(1)
    mapped = []
    for i in range(n_items):
        mapped.append(imgs[i % len(imgs)])
    return mapped

def make_image_segment(img: Path, dur: float, outseg: Path):
    fade = 0.5
    vf = "scale=w={w}:h={h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p".format(w=WIDTH,h=HEIGHT)
    vf = vf + ",fade=t=in:st=0:d={d},fade=t=out:st={st}:d={d}".format(d=fade, st=max(0, dur-fade))
    cmd = ["ffmpeg","-y","-loop","1","-i", str(img), "-t", str(dur), "-r", str(FPS), "-vf", vf, "-c:v","libx264","-crf",str(CRF),"-preset","veryfast","-pix_fmt","yuv420p", str(outseg)]
    run(cmd)

def concat_segments(segments, outvideo):
    listf = outvideo.with_suffix(".txt")
    with open(listf,"w",encoding="utf-8") as f:
        for s in segments:
            f.write("file '{}'\n".format(str(s).replace("'", "")))
    cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i", str(listf), "-c","copy", str(outvideo)]
    run(cmd)
    try: os.remove(listf)
    except: pass

def build_srt(items, durations, out_srt):
    start = 0.0
    gap = 0.04
    def fmt(t):
        h=int(t//3600); m=int((t%3600)//60); s=int(t%60); ms=int((t-int(t))*1000)
        return "{:02d}:{:02d}:{:02d},{:03d}".format(h,m,s,ms)
    with open(out_srt, "w", encoding="utf-8") as f:
        for i,(it,dur) in enumerate(zip(items,durations), start=1):
            st = start
            et = st + dur
            f.write(str(i) + "\n")
            f.write(fmt(st) + " --> " + fmt(et) + "\n")
            for w in textwrap.wrap(it["text"], width=50):
                f.write(w + "\n")
            f.write("\n")
            start = et + gap

def burn_audio_subs(video_no_audio, audio_file, srt_file, out_final):
    srt_path = str(srt_file).replace("\\","/")
    srt_escaped = srt_path.replace(":", r"\:").replace("'", r"\'")
    style = "FontName=Arial,FontSize=20,MarginV=40,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2"
    vf = "subtitles='{}':force_style='{}'".format(srt_escaped, style)
    cmd = ["ffmpeg","-y","-i", str(video_no_audio), "-i", str(audio_file), "-vf", vf, "-map","0:v:0","-map","1:a:0","-c:v","libx264","-crf",str(CRF),"-preset","veryfast","-c:a","aac","-b:a","192k","-shortest", str(out_final)]
    run(cmd)

def cleanup_tmp(tmp_list):
    for p in tmp_list:
        try:
            p.unlink()
        except: pass

def main():
    check_tools()
    TMP.mkdir(parents=True, exist_ok=True)
    items = load_narration_items()
    print(f"Loaded {len(items)} narration items.")
    aligned_files, missing = find_narration_files(items)
    if missing:
        print("Missing narration files (will use silence placeholders):")
        for m in missing:
            print("  -", m)
    else:
        print("All narration files present.")

    # Build merged audio: normalize + concat via filter_complex
    merged = AUDIO_DIR / "merged_narration_sync.wav"
    print("Normalizing & merging narration files into:", merged)
    tmp_converted, durations = build_merged_audio_per_item(aligned_files, merged)
    print("Per-item durations (s):")
    for i,d in enumerate(durations, start=1):
        print(f"  {i:02d}: {d:.3f}")

    # Build image segments using these durations
    images = pick_images_for_items(len(items))
    segments=[]
    for idx,(it,dur) in enumerate(zip(items, durations), start=1):
        seg_dur = dur + SEGMENT_PADDING
        img = images[idx-1]
        outseg = TMP / f"seg_{idx:03d}.mp4"
        print(f"Creating segment {idx}: {img.name} duration={seg_dur:.3f}s -> {outseg.name}")
        make_image_segment(img, seg_dur, outseg)
        segments.append(outseg)

    # Concatenate segments
    full_no_audio = TMP / "full_nosound.mp4"
    print("Concatenating segments into:", full_no_audio)
    concat_segments(segments, full_no_audio)

    # Build SRT from exact durations
    srt = TMP / "captions_sync.srt"
    print("Writing SRT to:", srt)
    build_srt(items, durations, srt)

    # Burn audio & subtitles into final video
    print("Burning audio & subtitles into final:", OUT)
    burn_audio_subs(full_no_audio, merged, srt, OUT)

    # cleanup tmp normalized files
    print("Cleaning up temporary normalized files...")
    cleanup_tmp(tmp_converted)
    print("DONE ->", OUT)

if __name__ == "__main__":
    main()
