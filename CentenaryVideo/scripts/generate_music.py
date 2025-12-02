# scripts/generate_music_better.py
from pydub import AudioSegment, effects
from pydub.generators import Sine, WhiteNoise
from pathlib import Path
import math, random

OUT = Path("audio/music.wav")
DURATION_MS = 120 * 1000
BPM = 60
BAR_MS = 4 * (60_000 // BPM)

def make_pad(chord_freqs, dur_ms, detune_cents=(0, -6, 7), gain=-24):
    seg = AudioSegment.silent(duration=dur_ms)
    for d in detune_cents:
        for f in chord_freqs:
            freq = f * (2 ** (d / 1200.0))
            tone = Sine(freq).to_audio_segment(duration=dur_ms).apply_gain(gain)
            seg = seg.overlay(tone)
    seg = seg.low_pass_filter(7000).high_pass_filter(30)
    chorus = seg.overlay(seg - 3, position=150).overlay(seg - 6, position=330)
    return chorus

def make_bell(freq, length_ms=900, gain=-8):
    t = Sine(freq).to_audio_segment(duration=length_ms).apply_gain(gain)
    t = t.high_pass_filter(400).low_pass_filter(8000)
    t = t.fade_in(5).fade_out(int(length_ms * 0.9))
    return t

def make_soft_kick(dur_ms=300, gain=-6):
    s = Sine(60).to_audio_segment(duration=dur_ms).apply_gain(gain)
    s = s.low_pass_filter(200).fade_out(int(dur_ms*0.8))
    return s

def make_shimmer_noise(dur_ms, gain=-30):
    n = WhiteNoise().to_audio_segment(duration=dur_ms).apply_gain(gain)
    return n.high_pass_filter(800).low_pass_filter(12000)

def chord_to_freq(root_midi, intervals):
    freqs = []
    for iv in intervals:
        midi = root_midi + iv
        freq = 440.0 * (2 ** ((midi - 69) / 12.0))
        freqs.append(freq)
    return freqs

progression = [
    (48, [0, 3, 7, 10]),  # Cmin7
    (50, [0, 3, 7]),      # Dmin
    (55, [0, 4, 7]),      # Gmaj
    (53, [0, 3, 7])       # Fmin
]

pad = AudioSegment.silent(duration=0)

for i, (root, ivs) in enumerate(progression):
    freqs = chord_to_freq(root, ivs)
    seg = make_pad(freqs, dur_ms=BAR_MS * 8, detune_cents=(0, -4, 6), gain=-24)

    # First chord → no crossfade
    if len(pad) == 0:
        pad = seg
    else:
        pad = pad.append(seg, crossfade=1500)

if len(pad) < DURATION_MS:
    pad = pad * (int(DURATION_MS / len(pad)) + 1)
pad = pad[:DURATION_MS].fade_in(3000).fade_out(3000)

arp = AudioSegment.silent(duration=0)
pattern = [0, 2, 4, 7]
beat_ms = 60_000 // BPM
time_cursor = 0

while time_cursor < DURATION_MS:
    prog_idx = (time_cursor // (BAR_MS * 8)) % len(progression)
    root, ivs = progression[prog_idx]
    midi = root + random.choice(pattern) + 12
    freq = 440.0 * (2 ** ((midi - 69) / 12.0))

    bell = make_bell(freq, gain=-10 - random.uniform(0,4))
    pan = -0.35 if (time_cursor // beat_ms) % 2 == 0 else 0.35
    # if arp is empty, append without crossfade
    if len(arp) == 0:
        arp = bell.pan(pan)
    else:
        arp = arp.append(bell.pan(pan), crossfade=60)

    time_cursor += beat_ms * 2

arp = arp[:DURATION_MS]

pulse = AudioSegment.silent(duration=0)
step = beat_ms * 2
t = 0
while t < DURATION_MS:
    if len(pulse) == 0:
        pulse = make_soft_kick(gain=-18)
    else:
        pulse = pulse.append(make_soft_kick(gain=-18), crossfade=20)
    t += step
pulse = pulse[:DURATION_MS]

shimmer = make_shimmer_noise(DURATION_MS, gain=-40)

mix = AudioSegment.silent(duration=DURATION_MS)
mix = mix.overlay(pad)
mix = mix.overlay(arp, gain_during_overlay=-2)
mix = mix.overlay(pulse, gain_during_overlay=-6)
mix = mix.overlay(shimmer, gain_during_overlay=-6)

def slow_pan(seg, period_ms=8000, amount=0.25):
    out = AudioSegment.silent(duration=0)
    i = 0
    while i < len(seg):
        chunk = seg[i:i+period_ms]
        pan_val = amount * math.sin(2 * math.pi * (i / period_ms) / 4)
        out = out.append(chunk.pan(pan_val), crossfade=40)
        i += period_ms
    return out

mix = slow_pan(mix).low_pass_filter(12000).fade_in(2000).fade_out(2000)
mix = effects.normalize(mix).apply_gain(-3)

OUT.parent.mkdir(exist_ok=True)
mix.export(str(OUT), format="wav")
print("Wrote", OUT, "Duration:", len(mix)/1000, "seconds")
