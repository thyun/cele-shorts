import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pymysql
from dotenv import load_dotenv

PREFIX = os.environ.get("SHORTS_DB_TABLE_PREFIX", "shorts_")

SCHEMA = """
CREATE TABLE IF NOT EXISTS {p}source_uses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  video_id VARCHAR(11) NOT NULL,
  title VARCHAR(255) NULL,
  channel VARCHAR(255) NULL,
  role VARCHAR(32) NOT NULL,
  date CHAR(10) NOT NULL DEFAULT '',
  job VARCHAR(100) NOT NULL DEFAULT '',
  record VARCHAR(255) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_use (video_id, role, date, job, record)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS {p}generations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  video_id VARCHAR(11) NOT NULL,
  date CHAR(10) NOT NULL,
  job VARCHAR(100) NOT NULL,
  short_id VARCHAR(64) NOT NULL,
  title VARCHAR(255) NOT NULL,
  segments JSON NOT NULL,
  file VARCHAR(255) NOT NULL,
  permission_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
  publication_status VARCHAR(64) NOT NULL DEFAULT 'unknown',
  review_verdict VARCHAR(64) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_generation (date, job, short_id),
  KEY idx_video (video_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


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


def connect(root=None):
    load_dotenv(Path(root) / ".env" if root else None)
    if os.environ.get("DB_DRIVER", "mysql") != "mysql":
        raise ValueError(f"지원하지 않는 DB_DRIVER: {os.environ.get('DB_DRIVER')}")
    conn = pymysql.connect(
        host=os.environ["MYSQL_HOST"], port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"], charset="utf8mb4", autocommit=True,
    )
    with conn.cursor() as cur:
        for statement in SCHEMA.format(p=PREFIX).strip().split(";"):
            if statement.strip():
                cur.execute(statement)
    return conn


def record_uses(conn, references):
    sql = (f"INSERT INTO {PREFIX}source_uses (video_id, title, channel, role, date, job, record) "
           "VALUES (%s, %s, %s, %s, %s, %s, %s) "
           "ON DUPLICATE KEY UPDATE title = COALESCE(VALUES(title), title), channel = COALESCE(VALUES(channel), channel)")
    with conn.cursor() as cur:
        for ref in references:
            cur.execute(sql, (video_id(ref["url"]), ref.get("title"), ref.get("channel"), ref["role"],
                              ref.get("date", ""), ref.get("job", ""), ref.get("record", "")))


def lookup(conn, identifier=None):
    where, params = ("WHERE video_id = %s", (identifier,)) if identifier else ("", ())
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(f"SELECT video_id, title, channel, role, date, job, record FROM {PREFIX}source_uses "
                    f"{where} ORDER BY date, id", params)
        uses = list(cur.fetchall())
        cur.execute(f"SELECT video_id, date, job, short_id, title, segments, file, permission_status, "
                    f"publication_status, review_verdict FROM {PREFIX}generations {where} ORDER BY date, job, id", params)
        generations = list(cur.fetchall())
    for row in generations:
        if isinstance(row["segments"], str):
            row["segments"] = json.loads(row["segments"])
    return {"uses": uses, "generations": generations}


def record_generation(root, plan, output, conn=None):
    output = Path(output)
    for short in plan["shorts"]:
        for artifact in (output / f"{short['id']}.mp4", output / f"{short['id']}.srt",
                         output / "capcut_drafts" / short["id"] / "draft_content.json"):
            if not artifact.is_file():
                raise FileNotFoundError(artifact)
    identifier = video_id(plan["source_url"])
    relative = str(output.relative_to(root))
    date, job = output.parent.name, output.name
    context = {"record": f"{relative}/plan.json", "date": date, "job": job}
    refs = [{"url": plan["source_url"], "title": plan.get("source_title"),
             "channel": plan["shorts"][0]["source"], "role": "source", **context},
            *[ref | context | {"role": "creative_reference"} for ref in plan.get("references", [])]]
    review_path = output / "upload-review.json"
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else None
    verdicts = {v["id"]: v["content_verdict"] for v in review["videos"]} if review else {}
    publication = (review.get("publication_status") or review.get("publication_checks", {}).get("status", "unknown")) if review else "unknown"
    permission = plan.get("permission", {}).get("status", "unknown")
    own = conn is None
    conn = conn or connect(root)
    try:
        record_uses(conn, refs)
        sql = (f"INSERT INTO {PREFIX}generations (video_id, date, job, short_id, title, segments, file, "
               "permission_status, publication_status, review_verdict) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
               "ON DUPLICATE KEY UPDATE title = VALUES(title), segments = VALUES(segments), file = VALUES(file), "
               "permission_status = VALUES(permission_status), publication_status = VALUES(publication_status), "
               "review_verdict = VALUES(review_verdict)")
        with conn.cursor() as cur:
            for s in plan["shorts"]:
                cur.execute(sql, (identifier, date, job, s["id"], s["title"], json.dumps(s["segments"]),
                                  f"{relative}/{s['id']}.mp4", permission, publication, verdicts.get(s["id"])))
    finally:
        if own:
            conn.close()


def import_json(conn, path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for entry in data["videos"].values():
        record_uses(conn, [{"url": entry["url"], "title": entry.get("title"), "channel": entry.get("channel"), **ref}
                           for ref in entry["references"] if ref.get("role")])
        for g in entry["generations"]:
            review = g.get("review_verdicts") or {}
            with conn.cursor() as cur:
                for s in g["shorts"]:
                    cur.execute(f"INSERT IGNORE INTO {PREFIX}generations (video_id, date, job, short_id, title, "
                                "segments, file, permission_status, publication_status, review_verdict) "
                                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                (entry["id"], g["date"], g["job"], s["id"], s["title"], json.dumps(s.get("segments", [])),
                                 s.get("file", f"{g['output_directory']}/{s['id']}.mp4"), g.get("permission", {}).get("status", "unknown"),
                                 g.get("publication_status", "unknown"), review.get(s["id"])))
