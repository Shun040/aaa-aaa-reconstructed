# Vertical (1080x1920) video for short-video platforms: heads frames + archive frames + text, with matched-loudness audio.
import json, os, subprocess, wave
import numpy as np
import pyloudnorm as pyln
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 1080, 1920, 25, 48000
CJK = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
CJK_L = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Light.ttc"
LAT_I = "/usr/share/texmf/fonts/opentype/public/lm/lmroman10-italic.otf"
LAT = "/usr/share/texmf/fonts/opentype/public/lm/lmroman10-regular.otf"
f = lambda path, size, idx=2: ImageFont.truetype(path, size, index=idx) if path.endswith(".ttc") else ImageFont.truetype(path, size)
F_TITLE, F_SMALL, F_CAP, F_CAP_EN = f(CJK, 44), f(CJK_L, 26), f(CJK, 40), f(LAT_I, 30)
F_LABEL, F_LABEL_EN, F_SUB = f(CJK, 30), f(LAT, 22), f(LAT, 46)
INK, DIM, U_COL, M_COL = (233, 228, 218), (139, 134, 124), (127, 178, 255), (255, 138, 122)

intro = json.load(open("build/intro_plan.json"))

def R(a, b, label="重建"):  # a run of reconstruction audio/score time
    return dict(src="R", a=a, b=b, label=label)

def A(a, b):
    return dict(src="A", a=a, b=b, label="档案")

SHOTS = [
    dict(name="A", t0=509.0, t1=512.4, parts=[R(509.0, 512.4)], caps=[(0, "以下所有声音均为重建", "All sound that follows is reconstructed")]),
    dict(name="B", t0=0.0, t1=7.1, parts=[R(0.0, 7.1, "重建 · 朗读")], caps=[(0, "朗读，依据文字说明与录音重建", "A reading, reconstructed from a text and a recording")], words=True),
    dict(name="C", t0=19.0, t1=28.2, parts=[R(19.0, 28.2)], caps=[(0, "两具身体同时吸入，随后各自维持一个音", "Two bodies inhale together, then each holds a tone"), (25.8, "闭口，经由鼻腔吸入", "Mouths closed, breath drawn through the nose")]),
    dict(name="D", t0=40.0, t1=50.6, parts=[R(40.0, 45.3), A(45.3, 50.6)], archive=True, caps=[(0, "1978 年的档案录音，与它的重建", "The 1978 recording and its reconstruction")]),
    dict(name="E", t0=515.6, t1=526.6, parts=[R(515.6, 518.7), A(518.7, 521.23), R(521.23, 524.0), A(524.0, 526.6)], archive=True, caps=[(0, "每一次发声都从高处开始，随即下落", "Each sound begins high and falls")]),
    dict(name="F", t0=150.0, t1=158.0, parts=[R(150.0, 158.0)], caps=[(0, "此后，两个声音在录音中不再可分", "From here, the two voices cannot be told apart in the recording")]),
    dict(name="G", t0=567.3, t1=576.5, parts=[R(567.3, 576.5)], caps=[(572.6, "发声停止。记录中没有停止的原因", "The sound stops. The record gives no reason")]),
]
END_CARD = 5.0

# ---------------------------------------------------------------- audio
def read_raw(p):
    return np.fromfile(p, dtype=np.float32)

U, M = read_raw("/tmp/U2.raw"), read_raw("/tmp/M2.raw")
pan = 0.55
gl = lambda p: (np.cos((p + 1) * np.pi / 4), np.sin((p + 1) * np.pi / 4))
(uL, uR), (mL, mR) = gl(-pan), gl(pan)
REC = np.stack([U * uL + M * mL, U * uR + M * mR], 1)
w = wave.open("analysis/audio.wav")
arc = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2).astype(np.float32) / 32768
assert w.getframerate() == SR
ARC = np.stack([arc[:, 0], arc[:, 0]], 1)  # the archive is effectively mono (left channel)
meter = pyln.Meter(SR)
TARGET = -16.0

def clip(src, a, b):
    x = (REC if src == "R" else ARC)[int(a * SR):int(b * SR)].copy()
    lufs = meter.integrated_loudness(x) if len(x) > SR * 0.5 else -30
    if np.isfinite(lufs):
        x *= 10 ** ((TARGET - lufs) / 20)
    n = int(0.012 * SR)
    ramp = np.linspace(0, 1, n)[:, None]
    x[:n] *= ramp
    x[-n:] *= ramp[::-1]
    return x

# normalise each source over the whole shot (not each fragment) so loud and quiet moments keep their shape
def shot_audio(s):
    out = []
    for p in s["parts"]:
        out.append((p, None))
    gains = {}
    for src in ("R", "A"):
        segs = [p for p in s["parts"] if p["src"] == src]
        if not segs:
            continue
        x = np.concatenate([(REC if src == "R" else ARC)[int(p["a"] * SR):int(p["b"] * SR)] for p in segs])
        lufs = meter.integrated_loudness(x)
        gains[src] = 10 ** ((TARGET - lufs) / 20) if np.isfinite(lufs) else 1.0
    pieces = []
    for p in s["parts"]:
        x = (REC if p["src"] == "R" else ARC)[int(p["a"] * SR):int(p["b"] * SR)].copy() * gains[p["src"]]
        n = int(0.012 * SR); ramp = np.linspace(0, 1, n)[:, None]
        x[:n] *= ramp; x[-n:] *= ramp[::-1]
        pieces.append(x)
    x = np.concatenate(pieces)
    pk = np.abs(x).max()
    return x * (0.89 / pk) if pk > 0.89 else x   # keep isolated plosives from clipping

audio = []
for s in SHOTS:
    x = shot_audio(s)
    n = int(round((s["t1"] - s["t0"]) * FPS)) * SR // FPS
    x = x[:n] if len(x) >= n else np.concatenate([x, np.zeros((n - len(x), 2), np.float32)])
    audio.append(x)
audio.append(np.zeros((int(END_CARD * SR), 2), np.float32))
audio = np.concatenate(audio)
audio = np.clip(audio, -0.98, 0.98)
with wave.open("/tmp/video_audio.wav", "wb") as wv:
    wv.setnchannels(2); wv.setsampwidth(2); wv.setframerate(SR)
    wv.writeframes((audio * 32767).astype(np.int16).tobytes())

# ---------------------------------------------------------------- picture
def text_c(d, y, s, font, fill):
    tw = d.textlength(s, font=font)
    d.text(((W - tw) / 2, y), s, font=font, fill=fill)

def wrap_en(d, s, font, maxw):
    words, lines, cur = s.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=font) > maxw and cur:
            lines.append(cur); cur = w_
        else:
            cur = t
    lines.append(cur)
    return lines

def frame_for(s, i):
    t = s["t0"] + i / FPS
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    # header
    d.text((60, 92), "AAA-AAA（重建）", font=F_TITLE, fill=INK)
    d.text((60, 156), "After Marina Abramović & Ulay, AAA-AAA, 1978", font=F_CAP_EN.font_variant(size=24), fill=DIM)
    part = next(p for p in s["parts"] if p["a"] <= t < p["b"] + 1e-6) if any(p["a"] <= t < p["b"] + 1e-6 for p in s["parts"]) else s["parts"][-1]
    lab = part["label"]
    col = M_COL if part["src"] == "A" else INK
    lw = d.textlength(lab, font=F_LABEL)
    d.text((W - 60 - lw, 96), lab, font=F_LABEL, fill=col)
    en = "ARCHIVE" if part["src"] == "A" else "RECONSTRUCTION"
    ew = d.textlength(en, font=F_LABEL_EN)
    d.text((W - 60 - ew, 140), en, font=F_LABEL_EN, fill=DIM)
    heads = Image.open(f"/tmp/frames/{s['name']}/{i:04d}.png").convert("RGB")
    if s.get("archive"):
        ai = min(i + 1, len(os.listdir(f"/tmp/arch/{s['name']}")))
        arc_img = Image.open(f"/tmp/arch/{s['name']}/{ai:04d}.png").convert("RGB")
        if part["src"] == "R":  # the archive picture stays, dimmed, while the reconstruction is heard
            arc_img = Image.blend(Image.new("RGB", arc_img.size), arc_img, 0.45)
        img.paste(arc_img, (0, 250))
        crop = heads.crop((0, 200, 1080, 760))
        img.paste(crop, (0, 1110))
        cap_y = 1700
    else:
        img.paste(heads.crop((0, 0, 1080, 1000)), (0, 380))
        cap_y = 1500
    # captions
    cap = None
    for (ct, zh, en_) in s["caps"]:
        if t >= (s["t0"] if ct == 0 else ct):
            cap = (zh, en_)
    if cap:
        text_c(d, cap_y, cap[0], F_CAP, INK)
        for k, line in enumerate(wrap_en(d, cap[1], F_CAP_EN, 900)):
            text_c(d, cap_y + 62 + k * 40, line, F_CAP_EN, DIM)
    # the reading, word by word
    if s.get("words"):
        ws = [x for x in intro["words"] if x["t0"] < s["t1"]]
        phrase = [x for x in ws if x["t0"] < 4.6] if t < 4.6 else [x for x in ws if x["t0"] >= 4.6]
        lines = []
        cur = []
        for x in phrase:
            cur.append(x)
            if d.textlength(" ".join(y["w"] for y in cur), font=F_SUB) > 900:
                cur.pop(); lines.append(cur); cur = [x]
        lines.append(cur)
        y0 = 1300
        for k, line in enumerate(lines):
            full = " ".join(y["w"] for y in line)
            x0 = (W - d.textlength(full, font=F_SUB)) / 2
            for x in line:
                c = M_COL if t >= x["t0"] else (70, 67, 62)
                d.text((x0, y0 + k * 64), x["w"], font=F_SUB, fill=c)
                x0 += d.textlength(x["w"] + " ", font=F_SUB)
    return img

def end_card(i):
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    a = min(1, i / 12)
    c = tuple(int(v * a) for v in INK); cd = tuple(int(v * a) for v in DIM)
    text_c(d, 760, "AAA-AAA（重建）", f(CJK, 60), c)
    text_c(d, 860, "2026", F_SMALL, cd)
    text_c(d, 910, "网页，物理声道模型实时合成，机器聆听", F_SMALL, cd)
    text_c(d, 1120, "After Marina Abramović & Ulay, AAA-AAA, 1978. R.T.B.F., Liège", F_CAP_EN.font_variant(size=24), cd)
    text_c(d, 1160, "Sound engine: CHIMERA by Jameson Hodge (MIT License)", F_CAP_EN.font_variant(size=24), cd)
    return img

ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                       "-i", "/tmp/video_audio.wav", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                       "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", "dist/AAA-AAA_reconstructed_vertical.mp4"], stdin=subprocess.PIPE)
total = 0
for s in SHOTS:
    n = int(round((s["t1"] - s["t0"]) * FPS))
    have = len(os.listdir(f"/tmp/frames/{s['name']}"))
    for i in range(min(n, have)):
        ff.stdin.write(frame_for(s, i).tobytes()); total += 1
    for i in range(have, n):  # pad if a frame is missing
        ff.stdin.write(frame_for(s, have - 1).tobytes()); total += 1
for i in range(int(END_CARD * FPS)):
    ff.stdin.write(end_card(i).tobytes()); total += 1
ff.stdin.close(); ff.wait()
print("frames", total, "seconds", total / FPS)
