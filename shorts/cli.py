import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from title_style import highlight_color, title_parts
from narration import narration_clips
from history import record_generation, update_history, video_id

ROOT = Path(__file__).resolve().parent.parent


def valid_date(value):
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("날짜는 YYYY-MM-DD 형식이어야 합니다") from exc
    return value


def valid_job(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise argparse.ArgumentTypeError("작업명에는 영문, 숫자, 밑줄, 하이픈만 사용할 수 있습니다")
    return value


def youtube_url(value):
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {
        "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"
    } or parsed.username or parsed.password:
        raise argparse.ArgumentTypeError("https YouTube URL을 입력하세요")
    return value


def validate_visual_options(short):
    if short.get("editorial_position", "bottom") not in {"top", "bottom"}:
        raise ValueError(f"{short['id']}: editorial_position은 top 또는 bottom이어야 합니다")
    width = short.get("crop_width", 0.4)
    if not isinstance(width, (int, float)) or not 0 < width <= 1:
        raise ValueError(f"{short['id']}: crop_width는 0보다 크고 1 이하여야 합니다")
    height = short.get("crop_height", 0.75)
    if not isinstance(height, (int, float)) or not 0 < height <= 1:
        raise ValueError(f"{short['id']}: crop_height는 0보다 크고 1 이하여야 합니다")
    for start, end, text in short.get("editorial_notes", []):
        if not isinstance(text, str) or not text.strip() or "\n" in text:
            raise ValueError(f"{short['id']}: 추가 화면 문구는 비어 있지 않은 한 줄이어야 합니다")
        if not any(a <= start < end <= b for a, b, _ in short["segments"]):
            raise ValueError(f"{short['id']}: 추가 화면 문구가 한 영상 구간에 속해야 합니다")
    for start, end, text, x, y in short.get("visual_labels", []):
        if (not isinstance(text, str) or not text.strip() or "\n" in text
                or not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in (x, y))
                or not any(a <= start < end <= b for a, b, _ in short["segments"])):
            raise ValueError(f"{short['id']}: 잘못된 화면 부위 라벨")


def main():
    parser = argparse.ArgumentParser(description="날짜별 쇼츠 작업 준비 및 편집안 렌더링")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="롱폼 및 제공되는 한국어 자막 다운로드")
    prepare.add_argument("url", type=youtube_url)
    history = sub.add_parser("history", help="영상 ID 기준 참고·제작 이력 조회")
    history.add_argument("--url", type=youtube_url)
    for cmd in (prepare, sub.add_parser("render", help="검토된 plan.json으로 MP4, SRT 및 캡컷 초안 생성")):
        cmd.add_argument("--date", type=valid_date, default=date.today().isoformat())
        cmd.add_argument("--job", type=valid_job, required=True)
    args = parser.parse_args()
    if args.command == "history":
        data = update_history(ROOT)
        result = data["videos"].get(video_id(args.url)) if args.url else data
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    work = ROOT / "work" / args.date / args.job
    output = ROOT / "output" / args.date / args.job
    if args.command == "prepare":
        work.mkdir(parents=True, exist_ok=False)
        print(f"작업 폴더: {work}", flush=True)
        known = update_history(ROOT)["videos"].get(video_id(args.url))
        if known:
            print(f"기존 이력: 참고 {len(known['references'])}건, 제작 {len(known['generations'])}건", flush=True)
        subprocess.run([
            "yt-dlp", "--no-playlist", "--no-overwrites",
            "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]",
            "--merge-output-format", "mp4", "--write-info-json", "--write-subs", "--write-auto-subs",
            "--sub-langs", "ko-orig,ko", "--convert-subs", "srt",
            "-o", str(work / "long.%(ext)s"), "--", args.url,
        ], check=True)
        if not (work / "long.mp4").is_file():
            raise FileNotFoundError(f"다운로드된 MP4가 없습니다: {work / 'long.mp4'}")
        if not list(work.glob("long.*.srt")):
            print("한국어 자막이 없습니다. 전사 또는 수동 대본이 필요합니다.", file=sys.stderr)
        metadata = json.loads((work / "long.info.json").read_text(encoding="utf-8"))
        update_history(ROOT, [{
            "url": args.url, "title": metadata["title"], "channel": metadata.get("uploader"),
            "role": "prepared", "date": args.date, "job": args.job,
        }])
        print("소재 검토 후 plan.json을 작성하고 render 명령을 실행하세요.")
        return

    plan_path = work / "plan.json"
    source = work / "long.mp4"
    with plan_path.open(encoding="utf-8") as file:
        plan = json.load(file)
    if not source.is_file():
        raise FileNotFoundError(f"롱폼 영상이 없습니다: {source}")
    if not isinstance(plan.get("shorts"), list) or not plan["shorts"]:
        raise ValueError("plan.json에는 비어 있지 않은 shorts 목록이 필요합니다")
    seen = set()
    for short in plan["shorts"]:
        name = valid_job(short["id"])
        if name in seen:
            raise ValueError(f"중복 쇼츠 ID: {name}")
        seen.add(name)
        title_parts(short)
        highlight_color(short)
        if not short["segments"]:
            raise ValueError(f"{name}: 영상 구간이 없습니다")
        for start, end, center in short["segments"]:
            if not (0 <= start < end and 0 <= center <= 1):
                raise ValueError(f"{name}: 잘못된 영상 구간")
        for start, end, text in short["captions"]:
            if not text or not any(a <= start < end <= b for a, b, _ in short["segments"]):
                raise ValueError(f"{name}: 자막이 한 구간에 속해야 합니다")
        validate_visual_options(short)
        narration_clips(short, work)

    output.mkdir(parents=True, exist_ok=False)
    png = work / "renders" / args.job
    png.mkdir(parents=True, exist_ok=False)
    env = os.environ | {
        "SHORTS_PLAN": str(plan_path), "SHORTS_SOURCE": str(source),
        "SHORTS_WORK": str(work), "SHORTS_OUTPUT": str(output),
        "SHORTS_PNG": str(png), "SHORTS_DRAFTS": str(output / "capcut_drafts"),
    }
    for script in ("build.py", "capcut.py"):
        subprocess.run([sys.executable, str(ROOT / "shorts" / script)], env=env, check=True)
    (output / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if plan.get("source_url"):
        record_generation(ROOT, plan, output)
    else:
        print("source_url이 없어 중앙 제작 이력을 기록하지 못했습니다.", file=sys.stderr)
    print(f"결과: {output}")


if __name__ == "__main__":
    main()
