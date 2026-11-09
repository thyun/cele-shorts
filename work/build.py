import importlib, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
plan = importlib.import_module(os.environ.get("SHORTS_PLAN", "plan"))
SHORTS, SRC = plan.SHORTS, plan.SRC

OUT = os.environ.get("SHORTS_OUTPUT", "../output")
SPEED = float(os.environ.get("SHORTS_SPEED", "1"))
END_FADE = float(os.environ.get("SHORTS_END_FADE", "0"))
PNG_DIR = os.environ.get("SHORTS_PNG", "png")
if SPEED <= 0:
    raise ValueError("SHORTS_SPEED must be positive")
os.makedirs(OUT, exist_ok=True)
os.makedirs(PNG_DIR, exist_ok=True)
FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
W, H = 1080, 1920


def font(size):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_name("Bold")
    except Exception:
        pass
    return f


def text_png(path, text, size, y, fill, stroke, box=None):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(size)
    bb = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = (W - tw) // 2 - bb[0]
    if box:
        d.rounded_rectangle((x + bb[0] - 40, y + bb[1] - 24, x + bb[0] + tw + 40, y + bb[1] + th + 24), 28, fill=box)
    d.text((x, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke and (0, 0, 0, 255))
    im.save(path)


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"


def build(s):
    segs = s["segments"]
    offs, acc = [], 0.0
    for a, b, _ in segs:
        offs.append(acc)
        acc += (b - a) / SPEED
    total = acc

    def to_out(t):
        for (a, b, _), o in zip(segs, offs):
            if a - 1e-6 <= t <= b + 1e-6:
                return o + (t - a) / SPEED
        raise ValueError(t)

    inputs, fc = [], []
    for i, (a, b, cx) in enumerate(segs):
        inputs += ["-ss", f"{a}", "-t", f"{b-a}", "-i", SRC]
        x = max(0.0, min(0.6, cx - 0.2))
        fc.append(
            f"[{i}:v]split[bg{i}][fg{i}];"
            f"[bg{i}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=40,eq=brightness=-0.15[b{i}];"
            f"[fg{i}]crop=iw*0.4:ih*0.75:iw*{x:.3f}:0,scale=1080:-2[f{i}];"
            f"[b{i}][f{i}]overlay=0:(H-h)/2-40,setsar=1,setpts=(PTS-STARTPTS)/{SPEED},fps=30,format=yuv420p[v{i}];"
            f"[{i}:a]asetpts=PTS-STARTPTS,afade=t=in:d=0.04,afade=t=out:st={b-a-0.04:.3f}:d=0.04,atempo={SPEED}[a{i}]"
        )
    n = len(segs)
    fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca]")
    if END_FADE:
        fc.append(f"[ca]afade=t=out:st={max(0, total-END_FADE):.6f}:d={END_FADE}[audio]")

    # 오버레이 PNG: 상단 후킹 문구 + 하단 자막
    pngs = []
    tp = f"{PNG_DIR}/{s['id']}_title.png"
    text_png(tp, s["title"], 78, 190, (255, 255, 255, 255), 8, box=(255, 59, 92, 235))
    pngs.append((tp, 0.0, total))
    srt = []
    for k, (a, b, t) in enumerate(s["captions"], 1):
        oa, ob = to_out(a), to_out(b)
        p = f"{PNG_DIR}/{s['id']}_c{k}.png"
        text_png(p, t, 64, 1560, (255, 255, 255, 255), 9)
        pngs.append((p, oa, ob))
        srt.append(f"{k}\n{srt_time(oa)} --> {srt_time(ob)}\n{t}\n")
    open(f"{OUT}/{s['id']}.srt", "w", encoding="utf8").write("\n".join(srt))

    last = "cv"
    for j, (p, oa, ob) in enumerate(pngs):
        inputs += ["-i", p]
        idx = n + j
        fc.append(f"[{last}][{idx}:v]overlay=0:0:enable='between(t,{oa:.3f},{ob:.3f})'[o{j}]")
        last = f"o{j}"
    out = f"{OUT}/{s['id']}.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y"] + inputs + [
        "-filter_complex", ";".join(fc), "-map", f"[{last}]", "-map", "[audio]" if END_FADE else "[ca]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out,
    ]
    subprocess.run(cmd, check=True)
    print(out, f"{total:.1f}s")


if __name__ == "__main__":
    ids = sys.argv[1:]
    for s in SHORTS:
        if not ids or s["id"] in ids:
            build(s)
