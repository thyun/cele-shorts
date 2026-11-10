import json
import subprocess
from pathlib import Path


def narration_clips(short, work):
    clips = {}
    for position in ("intro", "outro"):
        key = f"narration_{position}"
        if key not in short:
            continue
        item = short[key]
        if not isinstance(item, dict) or not isinstance(item.get("video"), str) or not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError(f"{short['id']}: {key}에 영상 경로와 자막이 필요합니다")
        path = (Path(work) / item["video"]).resolve()
        if not path.is_relative_to(Path(work).resolve()) or not path.is_file():
            raise ValueError(f"{short['id']}: {key} 영상은 작업 폴더 안의 파일이어야 합니다")
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height", "-of", "json", str(path)],
            check=True, capture_output=True, text=True,
        )
        info = json.loads(probe.stdout)
        duration = float(info["format"]["duration"])
        videos = [stream for stream in info["streams"] if stream["codec_type"] == "video"]
        if not 2 <= duration <= 4 or not videos or (videos[0].get("width"), videos[0].get("height")) != (1080, 1920) or not any(stream["codec_type"] == "audio" for stream in info["streams"]):
            raise ValueError(f"{short['id']}: {key}는 영상과 음성이 있는 2~4초 길이의 1080x1920 클립이어야 합니다")
        clips[position] = {"path": str(path), "text": item["text"], "duration": duration}
    return clips
