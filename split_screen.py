"""Split screen "talking to yourself" renderer.

One person plays both sides of a conversation: one take standing on the left half of the frame, one take on the
right half, phone locked on a tripod. This script joins the two takes down a soft vertical seam and lines the
conversation up: whoever is talking plays at real speed and is the only audio; the listening side plays its own
footage from between its lines.

Usage:
  python split_screen.py plan.json            render the plan
  python split_screen.py plan.json --pieces   print the cut plan only (no render)

Plan (JSON):
  {
    "left":    "left_take.mov",        the take where you stand on the LEFT half
    "right":   "right_take.mov",       the take where you stand on the RIGHT half
    "out":     "split.mp4",
    "seam_x":  540,                    where the seam sits, in pixels on a 1080-wide frame (540 = centre)
    "feather": 48,                     width of the soft blend across the seam, in pixels
    "gap":     0.15,                   pause kept after each line before the reply, in seconds
    "mode":    "1x",                   "1x" or "fit" (see below)
    "lines": [                         the conversation, in the order it should play
      {"side": "R", "win": [7.5, 11.0], "note": "I've got the best power bank."},
      {"side": "L", "win": [13.0, 16.5], "note": "No, I've got the best power bank."}
    ]
  }
  "win" is a rough window, in seconds, in THAT side's own take, that contains the spoken line (a little loose on
  both ends is fine). The script finds the voice inside the window and trims tight to it.

Modes for the listening side:
  1x   real speed. It plays on from where that side last stopped talking and jumps into its next line.
       Looks the most natural; this is the default.
  fit  one continuous stretch from where that side stopped talking to where it next talks, sped up or slowed
       down to fill the other side's talking time exactly. No jump, but big speed changes look odd.

Needs: Python 3.9+, numpy, and ffmpeg + ffprobe version 7 or newer on the PATH
(or set the FFMPEG / FFPROBE environment variables to their full paths).
Output: 1080x1920, 30 fps, H.264 + AAC, audio levelled to -14 LUFS, plus a frame sheet PNG next to the video
(first / middle / last frame of every line) for checking the seam.
"""
import json, math, os, subprocess, sys, tempfile, wave
import numpy as np

FF = os.environ.get("FFMPEG", "ffmpeg")
FP = os.environ.get("FFPROBE", "ffprobe")
FPS = 30.0
W, H = 1080, 1920
# Voice finder settings. sp = how loud counts as speech (dB), edge = how quiet a word's tail must fall before the
# cut (dB), gapmax = pauses shorter than this inside a line are kept (s), headn / tailn = how far the cut may reach
# out for the soft start / end of a word (in 20 ms steps). Override any of them with a "cut" object in the plan.
CUT_DEFAULTS = {"sp": -45, "edge": -58, "gapmax": 0.12, "headn": 4, "tailn": 12}
X = os.path.expanduser


def run(cmd): subprocess.run(cmd, check=True)


def nframes(f):
    return int(subprocess.check_output([FP, "-v", "error", "-select_streams", "v", "-count_packets", "-show_entries",
                                        "stream=nb_read_packets", "-of", "csv=p=0", f]).split()[0])


def src_dur(f):
    return float(subprocess.check_output([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]))


# ---------- voice finder ----------
def load(src, hp):
    """Mono 16 kHz copy of the audio with the rumble filtered off (300 Hz copy finds the voice, 80 Hz copy finds word edges)."""
    p = os.path.join(tempfile.mkdtemp(), "a.wav")
    af = f"highpass=f={hp}:poles=2,highpass=f={hp}:poles=2" if hp == 300 else f"highpass=f={hp}:poles=2"
    run([FF, "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-af", af, p])
    w = wave.open(p); return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768


_cache = {}
def audio(src):
    if src not in _cache: _cache[src] = (load(src, 300), load(src, 80))
    return _cache[src]


def cut(src, win, c):
    """One rough window [a, b] -> tight pieces [[a, b], ...] on the frame grid, never overlapping."""
    (Xv, XE), SR = audio(src), 16000
    a, b = win
    def db(t0, t1, A):
        s = A[int(max(t0, 0) * SR):int(t1 * SR)]
        return -99 if len(s) == 0 else 20 * np.log10(np.sqrt((s ** 2).mean()) + 1e-9)
    on = [db(a + i * 0.02, a + i * 0.02 + 0.02, Xv) > c["sp"] for i in range(int((b - a) / 0.02))]
    runs = []; i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]: j += 1
            if runs and (i - runs[-1][1]) * 0.02 <= c["gapmax"]: runs[-1][1] = j
            else: runs.append([i, j])
            i = j
        else: i += 1
    P = []
    for i, j in runs:
        if (j - i) * 0.02 < 0.04: continue
        st, en = a + i * 0.02, a + j * 0.02
        k = 0
        while k < c["headn"] and db(st - 0.02, st, XE) > c["edge"]: st -= 0.02; k += 1
        k = 0
        while k < c["tailn"] and max(db(en + d, en + d + 0.02, XE) for d in (0, 0.02, 0.04)) > c["edge"]: en += 0.02; k += 1
        st, en = max(a, st - 0.02), min(b, en + 0.03)
        if P and st <= P[-1][1]: P[-1][1] = en
        else: P.append([st, en])
    snap = lambda t: round(t * FPS) / FPS
    P = [[snap(s), snap(e)] for s, e in P if snap(e) - snap(s) >= 2 / FPS]
    for i in range(1, len(P)):
        if P[i][0] < P[i - 1][1]: P[i][0] = P[i - 1][1]
    return [p for p in P if p[1] - p[0] >= 2 / FPS]


# ---------- line-up ----------
def slots(plan):
    """Each line -> its tight pieces and frame count. The pause before the reply stays on the talker."""
    c = {**CUT_DEFAULTS, **plan.get("cut", {})}; gap = plan.get("gap", 0.15); out = []
    for n, l in enumerate(plan["lines"], 1):
        if l["side"] not in ("L", "R"): sys.exit(f'line {n}: "side" must be "L" or "R"')
        P = cut(plan["_src"][l["side"]], l["win"], c)
        if not P: sys.exit(f"line {n}: no voice found in {l['win']} of the {l['side']} take. Check the window.")
        P[-1][1] = round((P[-1][1] + gap) * FPS) / FPS
        out.append({**l, "P": P, "n": sum(round((b - a) * FPS) for a, b in P)})
    return out


def side_segments(plan, S, side, mode):
    """[(start, end, frames, rate)] video segments for one side. rate 1 = real speed."""
    D = src_dur(plan["_src"][side]); segs = []; i = 0
    while i < len(S):
        if S[i]["side"] == side:
            segs += [(a, b, round((b - a) * FPS), 1.0) for a, b in S[i]["P"]]; i += 1; continue
        j = i
        while j < len(S) and S[j]["side"] != side: j += 1
        run_ = S[i:j]; T = sum(s["n"] for s in run_)     # frames this side has to listen for
        prev = next((s["P"][-1][1] for s in reversed(S[:i]) if s["side"] == side), None)   # where it last stopped talking
        nxt = next((s["P"][0][0] for s in S[j:] if s["side"] == side), None)               # where it next talks
        if prev is None: prev = max(0.0, nxt - T / FPS) if nxt is not None else 0.0
        if nxt is None: nxt = min(D - 0.1, prev + T / FPS)
        room = nxt - prev
        if mode == "fit" or room <= T / FPS:
            segs.append((prev, nxt, T, room * FPS / T))
        elif len(run_) == 1:
            segs.append((prev, prev + T / FPS, T, 1.0))
        else:   # 1x across several of the other side's lines: jump once, at a moment the talker also cuts
            k = len(run_) // 2; A = sum(s["n"] for s in run_[:k]); B = T - A
            segs += [(prev, prev + A / FPS, A, 1.0), (nxt - B / FPS, nxt, B, 1.0)]
        i = j
    return segs


# ---------- render ----------
def sheet(f, frames, out, cols):
    sel = "+".join(f"eq(n,{n})" for n in frames); rows = math.ceil(len(frames) / cols)
    run([FF, "-v", "error", "-y", "-i", f, "-vf", f"select='{sel}',scale=270:480,tile={cols}x{rows}", "-frames:v", "1", "-update", "1", out])


def render(plan, pieces_only=False):
    mode = plan.get("mode", "1x")
    if mode not in ("1x", "fit"): sys.exit('"mode" must be "1x" or "fit"')
    S = slots(plan); N = sum(s["n"] for s in S)
    side = {s: side_segments(plan, S, s, mode) for s in "LR"}
    for s in "LR": assert sum(n for _, _, n, _ in side[s]) == N, (s, side[s], N)

    t = 0.0
    print(f"\nConversation ({N / FPS:.2f}s, listening side: {mode})")
    for sl in S:
        print(f"  {t:6.2f}s  {sl['side']}  " + "  ".join(f"{a:.2f}-{b:.2f}" for a, b in sl["P"]) + f"   {sl.get('note', '')}")
        t += sl["n"] / FPS
    for s in "LR":
        print(f"  {s} side footage: " + "  ".join(f"{a:.2f}-{b:.2f}" + ("" if r == 1 else f" @{r:.2f}x") for a, b, n, r in side[s]))
    if pieces_only: return

    tmp = tempfile.mkdtemp()
    x, fe = plan.get("seam_x", 540), max(plan.get("feather", 48), 1)
    mask = os.path.join(tmp, "mask.png")   # white = right take shows; a soft ramp `feather` px wide, centred on the seam
    run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}", "-vf",
         f"format=gray,geq=lum='255*clip((X-{x - fe / 2})/{fe},0,1)'", "-frames:v", "1", mask])
    idx = {"L": 0, "R": 1}; g = []
    for s in "LR":
        for m, (a, b, n, r) in enumerate(side[s]):
            g.append(f"[{idx[s]}:v]fps=30,trim=start_frame={round(a * FPS)}:end_frame={max(round(b * FPS), round(a * FPS) + 1)},"
                     f"setpts=(PTS-STARTPTS)/{r:.6f},fps=30,tpad=stop_mode=clone:stop=3,trim=end_frame={n},"
                     f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1[{s}{m}];")
        g.append("".join(f"[{s}{m}]" for m in range(len(side[s]))) + f"concat=n={len(side[s])}:v=1:a=0,fps=30,settb=1/30[{s}];")
    A = [(idx[sl["side"]], a, b) for sl in S for a, b in sl["P"]]   # audio: only ever the side that is talking
    for m, (ki, a, b) in enumerate(A):
        f = min(0.012, (b - a) / 4)
        g.append(f"[{ki}:a]atrim=start={a:.6f}:end={b:.6f},asetpts=PTS-STARTPTS,afade=t=in:d={f:.3f},afade=t=out:st={b - a - f:.6f}:d={f:.3f}[sa{m}];")
    g.append("".join(f"[sa{m}]" for m in range(len(A))) + f"concat=n={len(A)}:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11[ao];")
    g.append(f"[2:v]format=gray,loop=-1:1,trim=end_frame={N},setpts=N/30/TB[mk];[R]format=yuva420p[Ra];[Ra][mk]alphamerge[Rm];"
             f"[L][Rm]overlay=0:0:format=auto,format=yuv420p[vo]")
    gs = os.path.join(tmp, "graph.txt"); open(gs, "w").write("\n".join(g))
    out = X(plan["out"]); os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    run([FF, "-v", "error", "-y", "-i", plan["_src"]["L"], "-i", plan["_src"]["R"], "-i", mask, "-/filter_complex", gs,
         "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", "30",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out])
    got = nframes(out); assert got == N, f"rendered {got} frames, planned {N}"
    fr, f0 = [], 0
    for sl in S: fr += [f0, f0 + sl["n"] // 2, f0 + sl["n"] - 1]; f0 += sl["n"]
    sh = os.path.splitext(out)[0] + " - frame sheet.png"; sheet(out, fr, sh, 3)
    print(f"\nVideo:       {out}\nFrame sheet: {sh}   (one row per line: first / middle / last frame)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1: sys.exit(__doc__)
    plan = json.load(open(args[0])); base = os.path.dirname(os.path.abspath(args[0]))
    path = lambda p: X(p) if os.path.isabs(X(p)) else os.path.join(base, p)   # paths are relative to the plan file
    plan["_src"] = {"L": path(plan["left"]), "R": path(plan["right"])}
    plan["out"] = path(plan["out"])
    for s, f in plan["_src"].items():
        if not os.path.exists(f): sys.exit(f"{s} take not found: {f}")
    render(plan, "--pieces" in sys.argv)
