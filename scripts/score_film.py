"""Write the film's soundtrack: a short score made with code, cut to the film's own cues.

Standard library only (math, random, struct, wave). render_film.py asks the film for its cues (film.cues: a list of
{"t": seconds, "k": kind}) and calls score() to write a WAV, which it muxes into the MP4. The same cues always
give the same sound: the noise comes from a seeded generator.

Kinds of cue: "hit" (a cut: kick and snap), "press" (the Play press: click and drop), "whoosh" (noise that rises
until the next cue at "until"), "tick" (a soft blip, for typing and counters), "mute" (the music stops until
"until": the film's "starts still" beat is silent), "end" (the last hit, then the chord rings out).

    python3 scripts/score_film.py cues.json output/score.wav   # cues.json: {"duration": 16, "cues": [...]}
"""
import json
import math
import random
import struct
import sys
import wave

RATE = 48000


def score(cues, duration, path, rate=RATE):
    n = int(duration * rate)
    mix = [0.0] * n
    rnd = random.Random(7)
    ends = [c["t"] for c in cues if c["k"] == "end"]
    end = ends[0] if ends else duration
    mutes = [(c["t"], c["until"]) for c in cues if c["k"] == "mute"]

    def add(t0, samples, gain=1.0):
        i0 = int(t0 * rate)
        for j, v in enumerate(samples):
            i = i0 + j
            if 0 <= i < n:
                mix[i] += v * gain

    def kick(gain=1.0, length=0.45):
        out, ph = [], 0.0
        for j in range(int(length * rate)):
            t = j / rate
            ph += 2 * math.pi * (45 + 110 * math.exp(-t / 0.035)) / rate
            out.append(math.sin(ph) * math.exp(-t / 0.16) * gain + (0.6 * math.exp(-t / 0.002) if j < 120 else 0))
        return out

    def snap(gain=1.0, decay=0.09, length=0.3):
        out, prev = [], 0.0
        for j in range(int(length * rate)):
            w = rnd.uniform(-1, 1)
            out.append((w - prev) * 0.5 * math.exp(-(j / rate) / decay) * gain)
            prev = w
        return out

    def blip(freq=1600, gain=0.25, length=0.018):
        return [math.sin(2 * math.pi * freq * j / rate) * (1 - j / (length * rate)) * gain for j in range(int(length * rate))]

    def whoosh(length, gain=0.5):
        out, lp = [], 0.0
        m = int(length * rate)
        for j in range(m):
            k = j / m
            a = 0.02 + 0.5 * k * k  # the filter opens as it rises
            lp += a * (rnd.uniform(-1, 1) - lp)
            out.append(lp * (k ** 1.6) * gain * 2.2)
        return out

    # the bed: a low A minor pad and steady hats, under everything but the silent beat and the end
    notes = [55.0, 82.41, 110.0, 130.81, 164.81]
    beat = 60 / 132 / 2
    lp = 0.0
    for i in range(n):
        t = i / rate
        if any(a <= t < b for a, b in mutes):
            continue
        if t < end:
            s = sum(math.sin(2 * math.pi * f * t) + 0.3 * math.sin(4 * math.pi * f * t + 0.5) for f in notes) / len(notes)
            lp += 0.05 * (s - lp)
            pulse = 0.55 + 0.45 * math.exp(-((t % beat) / 0.12))
            mix[i] += lp * 0.16 * pulse * min(1.0, t / 0.05)
    for k in range(int(end / beat)):
        t0 = k * beat
        if not any(a <= t0 < b for a, b in mutes):
            add(t0, snap(0.12 if k % 2 else 0.07, decay=0.018, length=0.05))

    for c in cues:
        t, k = c["t"], c["k"]
        if k == "hit":
            add(t, kick(0.9))
            add(t, snap(0.35))
        elif k == "press":
            add(t, [0.9 if (j // 24) % 2 else -0.9 for j in range(144)], 0.5)
            add(t + 0.03, kick(1.0, 0.8))
            add(t + 0.03, snap(0.4, 0.2, 0.5))
        elif k == "whoosh":
            length = c["until"] - t
            add(t, whoosh(length, c.get("gain", 0.5)))
        elif k == "tick":
            add(t, blip(c.get("freq", 1600), c.get("gain", 0.18)))
        elif k == "end":
            add(t, kick(1.1, 1.2))
            add(t, snap(0.5, 0.35, 1.2))
            # the chord rings out over the end card, an octave up, with a few soft echoes
            m = int((duration - t) * rate)
            ring = []
            for j in range(m):
                tt = j / rate
                env = (1 - math.exp(-tt / 0.02)) * math.exp(-tt / 1.6) * min(1.0, (m - j) / (0.4 * rate))
                ring.append(env * sum(math.sin(2 * math.pi * 2 * f * tt) for f in notes[1:]) / 4)
            for d, g in ((0, 0.32), (0.21, 0.12), (0.43, 0.06)):
                add(t + d, ring, g)

    # a gentle limiter, then peaks at -3.4 dBFS: about -14 LUFS for this mix, with room for the AAC encoder's
    # overshoot so the encoded file stays under -1 dBTP
    for i in range(n):
        mix[i] = math.tanh(mix[i] * 1.2) / math.tanh(1.2)
    peak = max(1e-9, max(abs(v) for v in mix))
    g = (10 ** (-3.4 / 20)) / peak
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<hh", int(v * g * 32767), int(v * g * 32767)) for v in mix))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: score_film.py CUES.json OUTPUT.wav", file=sys.stderr)
        return 2
    data = json.loads(open(argv[0], encoding="utf-8").read())
    score(data["cues"], data["duration"], argv[1])
    print("Wrote " + argv[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
