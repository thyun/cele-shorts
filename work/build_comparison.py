import os
import shutil
import subprocess
from pathlib import Path

os.environ["SHORTS_PLAN"] = "plan_comparison"
os.environ["SHORTS_SPEED"] = "1.2"
os.environ["SHORTS_END_FADE"] = "0.2"
os.environ["SHORTS_OUTPUT"] = "../output/comparison_20261110"
os.environ["SHORTS_PNG"] = "narration_comparison/png"

import build
from plan_comparison import SHORTS

out = Path("../output/comparison_20261110")
assets = out / "assets"
assets.mkdir(parents=True, exist_ok=True)
for short in SHORTS:
    build.build(short)

base = out / "s1_cushion_hook.mp4"
frame = assets / "cushion_frame.png"
caption = assets / "cushion_narration.png"
voice = Path("narration_comparison/cushion.aiff")
outro = assets / "cushion_outro.mp4"
final = out / "s1_cushion_hook_with_narration.mp4"

duration = float(subprocess.check_output([
    "ffprobe", "-v", "error", "-show_entries", "format=duration",
    "-of", "default=nw=1:nk=1", str(base),
], text=True))
voice_duration = float(subprocess.check_output([
    "ffprobe", "-v", "error", "-show_entries", "format=duration",
    "-of", "default=nw=1:nk=1", str(voice),
], text=True))
tail_duration = max(2.0, voice_duration + 0.35)
if tail_duration > 4:
    raise ValueError(f"Narration outro exceeds 4 seconds: {tail_duration}")

subprocess.run([
    "ffmpeg", "-v", "error", "-y", "-ss", "9",
    "-i", str(base), "-frames:v", "1", str(frame),
], check=True)
build.text_png(str(caption), "피부 톤에 맞는 색상도 확인하세요", 58, 1560,
               (255, 255, 255, 255), 9)
subprocess.run([
    "ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30",
    "-i", str(frame), "-i", str(voice), "-loop", "1", "-framerate", "30",
    "-i", str(caption), "-filter_complex",
    "[0:v]drawbox=x=0:y=1500:w=iw:h=160:color=black:t=fill[bg];"
    "[bg][2:v]overlay=0:0:shortest=1[v];"
    "[1:a]aresample=48000,apad,afade=t=out:st="
    f"{tail_duration - 0.2:.3f}:d=0.2[a]",
    "-map", "[v]", "-map", "[a]", "-t", f"{tail_duration:.3f}",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", str(outro),
], check=True)
subprocess.run([
    "ffmpeg", "-v", "error", "-y", "-i", str(base), "-i", str(outro),
    "-filter_complex", "[0:v:0][0:a:0][1:v:0][1:a:0]concat=n=2:v=1:a=1[v][a]",
    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
    "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
    "-movflags", "+faststart", str(final),
], check=True)
subtitle = out / "s1_cushion_hook.srt"
text = subtitle.read_text(encoding="utf-8").rstrip()
end = duration + tail_duration
subtitle.with_name("s1_cushion_hook_with_narration.srt").write_text(
    text + f"\n\n8\n{build.srt_time(duration)} --> {build.srt_time(end)}\n"
    "쿠션은 내 피부 톤에 맞는 색상도 확인하세요.\n",
    encoding="utf-8",
)
shutil.move(str(base), str(assets / base.name))
shutil.move(str(subtitle), str(assets / subtitle.name))
print(f"Narration: {voice_duration:.2f}s; cushion with outro: {end:.2f}s")
