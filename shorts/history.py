import fcntl
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def video_id(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("https YouTube URL이 필요합니다")
    if parsed.hostname == "youtu.be":
        identifier = parsed.path.lstrip("/").split("/")[0]
    elif parsed.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        parts = parsed.path.strip("/").split("/")
        identifier = (parse_qs(parsed.query).get("v", [""])[0] if parts == ["watch"]
                      else parts[1] if len(parts) == 2 and parts[0] in {"shorts", "embed", "live"} else "")
    else:
        identifier = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", identifier):
        raise ValueError(f"YouTube 영상 ID를 확인할 수 없습니다: {url}")
    return identifier


def update_history(root, references=(), generation=None):
    path = Path(root) / "references" / "history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
            "schema_version": 1, "videos": {},
        }
        for ref in references:
            identifier = video_id(ref["url"])
            entry = data["videos"].setdefault(identifier, {
                "id": identifier,
                "url": f"https://www.youtube.com/watch?v={identifier}",
                "references": [], "generations": [],
            })
            for key in ("title", "channel", "format", "published_kst", "duration_seconds"):
                if ref.get(key):
                    entry[key] = ref[key]
            event = {key: ref[key] for key in ("role", "record", "date", "job", "use") if key in ref}
            if event and event not in entry["references"]:
                entry["references"].append(event)
        if generation:
            identifier = video_id(generation["source_url"])
            entry = data["videos"][identifier]
            key = generation["output_directory"]
            previous = next((g for g in entry["generations"] if g["output_directory"] == key), None)
            if previous:
                previous.update(generation)
            else:
                entry["generations"].append(generation)
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".history-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return data


def record_generation(root, plan, output):
    output = Path(output)
    for short in plan["shorts"]:
        for artifact in (output / f"{short['id']}.mp4", output / f"{short['id']}.srt",
                         output / "capcut_drafts" / short["id"] / "draft_content.json"):
            if not artifact.is_file():
                raise FileNotFoundError(artifact)
    url = plan["source_url"]
    relative = str(output.relative_to(root))
    context = {"record": f"{relative}/plan.json", "date": output.parent.name, "job": output.name}
    refs = [{
        "url": url, "title": plan.get("source_title"), "channel": plan["shorts"][0]["source"],
        "format": "long", "role": "source", **context,
    }, *[ref | context | {"role": "creative_reference"}
         for ref in plan.get("references", [])]]
    review_path = output / "upload-review.json"
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else None
    update_history(root, refs, {
        "source_url": url, "date": output.parent.name, "job": output.name,
        "output_directory": relative, "status": "generated",
        "permission": plan.get("permission", {"status": "unknown"}),
        "publication_status": review.get("publication_status", "unknown") if review else "unknown",
        "review_file": str(review_path.relative_to(root)) if review else None,
        "review_verdicts": {v["id"]: v["content_verdict"] for v in review["videos"]} if review else {},
        "shorts": [{"id": s["id"], "title": s["title"], "segments": s["segments"],
                    "file": f"{relative}/{s['id']}.mp4"} for s in plan["shorts"]],
    })
