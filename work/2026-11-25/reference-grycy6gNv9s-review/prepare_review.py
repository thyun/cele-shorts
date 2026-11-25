import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


WORK = Path(__file__).resolve().parent
SOURCE = WORK / "source.mp4"
info = json.loads((WORK / "source.info.json").read_text())
probe = json.loads(subprocess.check_output([
    "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(SOURCE),
], text=True))
duration = float(probe["format"]["duration"])
subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(SOURCE), "-f", "null", "-"],
               check=True)
scene_log = subprocess.run([
    "ffmpeg", "-hide_banner", "-i", str(SOURCE), "-an",
    "-vf", "select='gt(scene,0.28)',showinfo", "-fps_mode", "vfr", "-f", "null", "-",
], capture_output=True, text=True, check=True).stderr
scenes = [float(t) for t in re.findall(r"pts_time:([0-9.]+)", scene_log)]
times = sorted({round(t, 3) for t in [
    0.1, *range(int(duration) + 1), duration - 0.1,
    *(max(0, min(duration - 0.1, cut + offset))
      for cut in scenes for offset in (-0.05, 0.05)),
]})
frames = WORK / "frames"
frames.mkdir(exist_ok=True)
for index, time in enumerate(times):
    image = frames / f"{index:03d}-{time:06.3f}.jpg"
    if not image.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-ss", str(time), "-i", str(SOURCE),
                        "-frames:v", "1", "-pix_fmt", "yuvj420p", "-n", str(image)], check=True)
    if index % 9 == 0:
        sheet = Image.new("RGB", (1080, 1992), "#181818")
        draw = ImageDraw.Draw(sheet)
    x, y = index % 9 % 3 * 360, index % 9 // 3 * 664
    with Image.open(image) as frame:
        sheet.paste(frame.resize((360, 640)), (x, y))
    draw.text((x + 8, y + 643), f"{time:.3f}s", fill="white")
    if index % 9 == 8 or index == len(times) - 1:
        sheet.save(WORK / f"contact-{index // 9 + 1:02d}.jpg")
metadata = {
    key: info.get(key)
    for key in ("id", "webpage_url", "title", "channel", "upload_date", "view_count",
                "like_count", "description", "availability", "age_limit")
}
metadata.update({
    "checked_on": "2026-11-17", "duration_seconds": duration,
    "streams": [{k: s.get(k) for k in ("codec_type", "codec_name", "width", "height")}
                for s in probe["streams"]],
    "full_decode": "passed",
    "scene_detection": {"threshold": 0.28, "timestamps": scenes},
    "sampled_timestamps": times, "audio_listened": False, "continuous_playback": False,
    "access_note": "공개 URL에서 쿠키·로그인 없이 확보. 영어 자동번역 자막 요청만 HTTP 429로 실패했고 한국어 자동 자막과 영상·메타데이터는 확보했다.",
})
(WORK / "public-metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"duration": duration, "frames": len(times), "scenes": len(scenes),
                  "contact_sheets": (len(times) + 8) // 9}, ensure_ascii=False))
