import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
from title_style import highlight_color, title_parts
from narration import narration_clips
with open(os.environ["SHORTS_PLAN"], encoding="utf-8") as plan_file:
    plan = json.load(plan_file)
SHORTS, SRC = plan["shorts"], os.environ["SHORTS_SOURCE"]

OUT = os.environ["SHORTS_OUTPUT"]
SPEED = float(os.environ.get("SHORTS_SPEED", "1.2"))
END_FADE = float(os.environ.get("SHORTS_END_FADE", "0.2"))
PNG_DIR = os.environ["SHORTS_PNG"]
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


def text_png(path, text, size, y, fill, stroke, box=None, max_width=None):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(size)
    if max_width:
        while size > 20 and d.textlength(text, font=f) > max_width:
            size -= 2
            f = font(size)
    bb = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = (W - tw) // 2 - bb[0]
    if box:
        d.rounded_rectangle((x + bb[0] - 40, y + bb[1] - 24, x + bb[0] + tw + 40, y + bb[1] + th + 24), 28, fill=box)
    d.text((x, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke and (0, 0, 0, 255))
    im.save(path)


def title_png(path, short):
    lines = title_parts(short)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    size = 78
    while size > 35:
        f = font(size)
        if max(d.textlength(line, font=f) for line, _ in lines) <= W - 150:
            break
        size -= 2
    f = font(size)
    height = size + 22
    for row, (line, spans) in enumerate(lines):
        x = (W - d.textlength(line, font=f)) / 2
        y = 110 + row * height
        d.rounded_rectangle((x - 30, y - 10, W - x + 30, y + height), 22, fill=(175, 20, 50, 235))
        d.text((x, y), line, font=f, fill="white", stroke_width=7, stroke_fill="black")
        for start, end in spans:
            pos = x + d.textlength(line[:start], font=f)
            d.text((pos, y), line[start:end], font=f,
                   fill=tuple(round(c * 255) for c in highlight_color(short)),
                   stroke_width=7, stroke_fill="black")
    im.save(path)


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"


def build(s):
    clips = narration_clips(s, os.environ["SHORTS_WORK"])
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
    crop_width = s.get("crop_width", 0.4)
    crop_height = s.get("crop_height", 0.75)
    for i, (a, b, cx) in enumerate(segs):
        inputs += ["-ss", f"{a}", "-t", f"{b-a}", "-i", SRC]
        x = max(0.0, min(1 - crop_width, cx - crop_width / 2))
        fc.append(
            f"[{i}:v]split[bg{i}][fg{i}];"
            f"[bg{i}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=40,eq=brightness=-0.15[b{i}];"
            f"[fg{i}]crop=iw*{crop_width}:ih*{crop_height}:iw*{x:.6f}:0,scale=1080:-2[f{i}];"
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
    title_png(tp, s)
    pngs.append((tp, 0.0, total))
    source_png = f"{PNG_DIR}/{s['id']}_source.png"
    text_png(source_png, f"출처: {s['source']}", 32, 1810, (255, 255, 255, 255), 3)
    pngs.append((source_png, 0.0, total))
    srt = []
    intro_duration = clips.get("intro", {}).get("duration", 0)
    if "intro" in clips:
        srt.append((0, intro_duration, clips["intro"]["text"]))
    for k, (a, b, t) in enumerate(s["captions"], 1):
        oa, ob = to_out(a), to_out(b)
        p = f"{PNG_DIR}/{s['id']}_c{k}.png"
        text_png(p, t, 64, 1560, (255, 255, 255, 255), 9)
        pngs.append((p, oa, ob))
        srt.append((oa + intro_duration, ob + intro_duration, t))

    for k, (a, b, text) in enumerate(s.get("editorial_notes", []), 1):
        p = f"{PNG_DIR}/{s['id']}_note{k}.png"
        note_y = 320 if s.get("editorial_position") == "top" else 1680
        text_png(p, f"채널 체크 | {text}", 44, note_y, (170, 239, 255, 255),
                 2, box=(13, 30, 45, 245), max_width=930)
        pngs.append((p, to_out(a), to_out(b)))

    for k, (a, b, text, x, y) in enumerate(s.get("visual_labels", []), 1):
        p = f"{PNG_DIR}/{s['id']}_label{k}.png"
        image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.text((W * x, H * y), text, font=font(48), anchor="mm",
                  fill=(170, 239, 255, 255), stroke_width=4, stroke_fill="black")
        image.save(p)
        pngs.append((p, to_out(a), to_out(b)))

    last = "cv"
    for j, (p, oa, ob) in enumerate(pngs):
        inputs += ["-i", p]
        idx = n + j
        fc.append(f"[{last}][{idx}:v]overlay=0:0:enable='between(t,{oa:.3f},{ob:.3f})'[o{j}]")
        last = f"o{j}"
    out = f"{OUT}/{s['id']}.mp4"
    base = os.path.join(PNG_DIR, f"{s['id']}_base.mp4") if clips else out
    cmd = ["ffmpeg", "-v", "error", "-n"] + inputs + [
        "-filter_complex", ";".join(fc), "-map", f"[{last}]", "-map", "[audio]" if END_FADE else "[ca]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", base,
    ]
    subprocess.run(cmd, check=True)
    if clips:
        base_duration = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", base], text=True))
        paths = ([clips["intro"]["path"]] if "intro" in clips else []) + [base] + ([clips["outro"]["path"]] if "outro" in clips else [])
        inputs = [arg for path in paths for arg in ("-i", path)]
        filters = []
        for i in range(len(paths)):
            filters.append(f"[{i}:v]setpts=PTS-STARTPTS,fps=30,setsar=1,format=yuv420p[v{i}]")
            filters.append(f"[{i}:a]asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[a{i}]")
        filters.append("".join(f"[v{i}][a{i}]" for i in range(len(paths))) + f"concat=n={len(paths)}:v=1:a=1[v][a]")
        subprocess.run([
            "ffmpeg", "-v", "error", "-n", *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264",
            "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out,
        ], check=True)
        if "outro" in clips:
            start = intro_duration + base_duration
            srt.append((start, start + clips["outro"]["duration"], clips["outro"]["text"]))
    with open(f"{OUT}/{s['id']}.srt", "x", encoding="utf8") as subtitle:
        subtitle.write("\n\n".join(
            f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{text}"
            for i, (a, b, text) in enumerate(srt, 1)
        ) + "\n")
    print(out, f"{total + sum(clip['duration'] for clip in clips.values()):.1f}s")


if __name__ == "__main__":
    ids = sys.argv[1:]
    for s in SHORTS:
        if not ids or s["id"] in ids:
            build(s)
