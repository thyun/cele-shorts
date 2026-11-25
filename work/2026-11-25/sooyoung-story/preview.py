import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
sys.path.insert(0, str(ROOT / "shorts"))
from crop import segment_crop


FONT = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 18)
PLAN = json.loads((WORK / "plan.json").read_text())


def frame_at(source, timestamp, target):
    if not target.exists():
        subprocess.run(
            ["ffmpeg", "-v", "error", "-n", "-ss", f"{timestamp:.6f}",
             "-i", str(source), "-frames:v", "1", "-q:v", "2", str(target)],
            check=True,
        )
    return Image.open(target).convert("RGB")


def sheet(items, path, width, height):
    canvas = Image.new("RGB", (4 * width, ((len(items) + 3) // 4) * (height + 40)), "#171717")
    draw = ImageDraw.Draw(canvas)
    for index, (image, label) in enumerate(items):
        x, y = index % 4 * width, index // 4 * (height + 40)
        canvas.paste(image.resize((width, height)), (x, y))
        draw.text((x + 5, y + height + 5), label, font=FONT, fill="white")
    canvas.save(path)


def preflight():
    directory = WORK / "preflight"
    directory.mkdir(exist_ok=True)
    os.environ.update({
        "SHORTS_PLAN": str(WORK / "plan.json"),
        "SHORTS_SOURCE": str(WORK / "long.mp4"),
        "SHORTS_OUTPUT": str(directory),
        "SHORTS_PNG": str(directory),
    })
    from build import title_png
    for short in PLAN["shorts"]:
        items = []
        first = None
        for index, (start, end, center) in enumerate(short["segments"]):
            width, height, top = segment_crop(short, index)
            for timestamp in [start + 0.06, (start + end) / 2, end - 0.06]:
                image = frame_at(
                    WORK / "long.mp4", timestamp,
                    directory / f"{short['id']}_{timestamp:.3f}.jpg",
                )
                x = max(0, min(1 - width, center - width / 2))
                crop = image.crop((
                    round(image.width * x), round(image.height * top),
                    round(image.width * (x + width)), round(image.height * (top + height)),
                ))
                items.append((crop, f"{index + 1}: {timestamp:.3f}s"))
                if first is None:
                    first = crop
        sheet(items, directory / f"{short['id']}_crops.jpg", 360, 360)
        overlay = directory / f"{short['id']}_title.png"
        title_png(str(overlay), short)
        thumbnail = Image.new("RGBA", (1080, 1920), "#202030")
        thumbnail.paste(first.resize((1080, 1080)), (0, 380))
        thumbnail = Image.alpha_composite(thumbnail, Image.open(overlay))
        thumbnail.convert("RGB").resize((270, 480)).save(
            directory / f"{short['id']}_thumbnail.jpg")


def final():
    output = ROOT / "output" / WORK.parent.name / WORK.name
    directory = output / "previews"
    directory.mkdir(exist_ok=True)
    raw = WORK / "final_frames"
    raw.mkdir(exist_ok=True)
    for short in PLAN["shorts"]:
        source = output / f"{short['id']}.mp4"
        duration = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(source)], text=True,
        ))
        times = [0.2, 1, 2, 3]
        offset = 0
        for start, end, _ in short["segments"]:
            length = (end - start) / 1.2
            times.extend([offset + min(0.1, length / 3), offset + length / 2])
            if offset:
                times.extend([max(0, offset - 0.08), offset + 0.08])
            offset += length
        times.extend([duration - 2, duration - 1, duration - 0.1])
        items = []
        for timestamp in sorted(set(round(t, 3) for t in times if 0 <= t < duration)):
            image = frame_at(source, timestamp, raw / f"{short['id']}_{timestamp:.3f}.jpg")
            items.append((image, f"out {timestamp:.3f}s"))
        sheet(items, directory / f"{short['id']}_contact.jpg", 270, 480)
        thumbnail = frame_at(source, 1, raw / f"{short['id']}_1.000.jpg")
        thumbnail.resize((270, 480)).save(directory / f"{short['id']}_thumbnail.jpg")


parser = argparse.ArgumentParser()
parser.add_argument("phase", choices=["preflight", "final"])
args = parser.parse_args()
preflight() if args.phase == "preflight" else final()
