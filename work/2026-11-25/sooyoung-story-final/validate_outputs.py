import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path


WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
OUTPUT = ROOT / "output" / WORK.parent.name / WORK.name
sys.path.insert(0, str(ROOT / "shorts"))
from crop import segment_crop


def seconds(value):
    hours, minutes, rest = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(rest)


plan = json.loads((OUTPUT / "plan.json").read_text())
results = []
project_ids = []
meta_ids = []
for short in plan["shorts"]:
    identifier = short["id"]
    video = OUTPUT / f"{identifier}.mp4"
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video),
    ], text=True))
    duration = float(probe["format"]["duration"])
    planned = sum((end - start) / 1.2 for start, end, _ in short["segments"])
    stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (stream["width"], stream["height"], stream["codec_name"]) == (1080, 1920, "h264")
    assert any(s["codec_type"] == "audio" and s["codec_name"] == "aac" for s in probe["streams"])
    assert abs(duration - planned) <= 1 / 30 + 0.002, (identifier, duration, planned)
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"],
                   check=True)
    cues = re.findall(
        r"(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})",
        (OUTPUT / f"{identifier}.srt").read_text(),
    )
    intervals = [(seconds(a), seconds(b)) for a, b in cues]
    assert len(intervals) == len(short["captions"])
    assert all(0 <= start < end <= duration + 0.001 for start, end in intervals)
    assert all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:]))
    directory = OUTPUT / "capcut_drafts" / identifier
    content = json.loads((directory / "draft_content.json").read_text())
    meta = json.loads((directory / "draft_meta_info.json").read_text())
    project_ids.append(content["id"])
    meta_ids.append(meta["draft_id"])
    materials = {m["id"]: m for m in content["materials"]["videos"]}
    tracks = {t["name"]: t["segments"] for t in content["tracks"]}
    assert set(tracks) == {"main", "title", "caption", "source"}
    assert len(tracks["main"]) == len(short["segments"])
    for index, (segment, (start, end, center)) in enumerate(zip(tracks["main"], short["segments"])):
        material = materials[segment["material_id"]]
        assert Path(material["path"]).is_file()
        assert Path(material["path"]).resolve() == (ROOT / plan["source_file"]).resolve()
        width, height, top = segment_crop(short, index)
        left = max(0, min(1 - width, center - width / 2))
        expected = {
            "upper_left_x": left, "upper_left_y": top,
            "upper_right_x": left + width, "upper_right_y": top,
            "lower_left_x": left, "lower_left_y": top + height,
            "lower_right_x": left + width, "lower_right_y": top + height,
        }
        assert all(math.isclose(material["crop"][key], value, abs_tol=1e-8)
                   for key, value in expected.items())
        assert abs(segment["source_timerange"]["start"] / 1e6 - start) < 1e-5
        assert abs(segment["source_timerange"]["duration"] / 1e6 - (end - start)) < 1e-5
    for track in tracks.values():
        ranges = [s["target_timerange"] for s in track]
        assert all(a["start"] + a["duration"] <= b["start"] for a, b in zip(ranges, ranges[1:]))
    results.append({
        "id": identifier, "file": video.name,
        "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "duration_seconds": duration, "planned_duration_seconds": round(planned, 6),
        "resolution": [1080, 1920], "codecs": ["h264", "aac"],
        "full_decode": "passed", "srt_cues": len(cues),
        "srt_bounds_order_and_nonoverlap": "passed",
        "capcut_source_paths_and_segment_crops": "passed",
        "capcut_track_nonoverlap": "passed",
    })
assert len(set(project_ids)) == len(results)
assert len(set(meta_ids)) == len(results)
review = {
    "reviewer": "production-agent",
    "output_directory": str(OUTPUT.relative_to(ROOT)),
    "permission": plan["permission"],
    "videos": results,
    "capcut_project_ids_unique": True,
    "visual_inspection": {
        "method": "최종 MP4 정지 프레임과 270×480 축소 썸네일 육안 검토",
        "coverage": "첫 0.2·1·2·3초, 각 컷 전후, 제품·반응, 마지막 2초",
        "observations": [
            "두 줄 타이틀과 하단 실제 대사 자막을 사용하며 타이틀 아래 별도 해설을 넣지 않았다.",
            "모자 문구와 크림 용기, 티파니의 반응 동작을 확인했다.",
            "모자 후반은 모자 문구 중심의 근접 구도이며 인물이 고개를 숙이는 장면이 있다. 모든 동작의 자연스러움을 스틸로 보증하지 않는다."
        ]
    },
    "audio_listened": False,
    "continuous_playback": False,
    "capcut_app_opened": False,
    "youtube_mobile_ui_checked": False,
    "rights_documents_independently_verified": False,
    "affiliate_disclosure_publication_checked": False,
    "publication_status": "게시 전 확인 필요",
    "archives": [
        "output/2026-11-17/sooyoung-story",
        "work/2026-11-17/sooyoung-story-final/pre-trim-render",
        "work/2026-11-17/sooyoung-story-final/candidate-final"
    ]
}
(OUTPUT / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(results, ensure_ascii=False, indent=2))
