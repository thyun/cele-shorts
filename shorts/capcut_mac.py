import copy
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path


VERSION = "9.8.0"
NEW_VERSION = "193.0.0"


def projects_root():
    return Path(os.environ.get(
        "SHORTS_CAPCUT_PROJECTS_DIR",
        Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft",
    )).expanduser()


def find_native_template(root):
    root = Path(root)
    index_path = root / "root_meta_info.json"
    if not index_path.is_file():
        raise FileNotFoundError(f"CapCut project index not found: {index_path}")
    registered = {
        entry.get("draft_fold_path")
        for entry in _read_json(index_path).get("all_draft_store", [])
    }

    candidates = []
    for info_path in root.glob("*/draft_info.json"):
        folder = info_path.parent
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        platform = info.get("platform", {})
        timeline_id = info.get("id")
        timeline = folder / "Timelines" / str(timeline_id)
        if (
            platform.get("os") == "mac"
            and platform.get("app_version") == VERSION
            and info.get("new_version") == NEW_VERSION
            and str(folder) in registered
            and (folder / "draft_meta_info.json").is_file()
            and (folder / "template.tmp").is_file()
            and (folder / "template-2.tmp").is_file()
            and (folder / "Timelines" / "project.json").is_file()
            and (timeline / "draft_info.json").is_file()
        ):
            blank = info.get("duration") == 0 and not info.get("tracks")
            candidates.append((folder, blank))
    if not candidates:
        raise FileNotFoundError(
            "A registered native CapCut 9.8.0 project is required; "
            "create and save a project in CapCut before rendering"
        )
    return max(
        candidates,
        key=lambda item: (item[1], item[0].stat().st_mtime_ns),
    )[0]


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path, value, compact=False):
    options = {"ensure_ascii": False}
    if compact:
        options["separators"] = (",", ":")
    else:
        options["indent"] = 2
    Path(path).write_text(
        json.dumps(value, **options) + ("" if compact else "\n"),
        encoding="utf-8",
    )


def _copy_native_support(template, folder):
    shutil.copytree(
        template,
        folder,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            "draft_info.json", "draft_info.json.bak", "draft_meta_info.json",
            "template-2.tmp", "template.tmp", "draft_cover.jpg", "Timelines",
        ),
    )


def _write_project(folder, template, project, meta, meta_id, created_us):
    folder = Path(folder)
    project_json = json.dumps(project, ensure_ascii=False, separators=(",", ":"))
    for filename in ("draft_info.json", "template-2.tmp", "draft_content.json",
                     "draft_info.json.bak"):
        (folder / filename).write_text(project_json, encoding="utf-8")

    legacy = _read_json(Path(template) / "template.tmp")
    legacy.update(project)
    _write_json(folder / "template.tmp", legacy, compact=True)

    timeline_id = project["id"]
    timeline_folder = folder / "Timelines" / timeline_id
    timeline_folder.mkdir(parents=True, exist_ok=True)
    for filename in ("draft_info.json", "template-2.tmp", "draft_info.json.bak"):
        (timeline_folder / filename).write_text(project_json, encoding="utf-8")
    _write_json(timeline_folder / "template.tmp", legacy, compact=True)
    for filename in ("attachment_editing.json", "attachment_pc_common.json"):
        shutil.copy2(Path(template) / filename, timeline_folder / filename)

    index = _read_json(Path(template) / "Timelines" / "project.json")
    index["id"] = timeline_id
    index["main_timeline_id"] = timeline_id
    index["create_time"] = created_us
    index["update_time"] = created_us
    if not index.get("timelines"):
        raise ValueError(f"Native CapCut template has no timeline: {template}")
    for timeline in index["timelines"]:
        timeline.update({
            "id": timeline_id,
            "name": "Timeline 01",
            "create_time": created_us,
            "update_time": created_us,
        })
    _write_json(folder / "Timelines" / "project.json", index, compact=True)

    layout = _read_json(Path(template) / "timeline_layout.json")
    for dock in layout.get("dockItems", []):
        dock["timelineIds"] = [timeline_id]
        dock["timelineNames"] = ["Timeline 01"]
    _write_json(folder / "timeline_layout.json", layout, compact=True)

    seconds = created_us // 1_000_000
    (folder / "draft_settings").write_text(
        "[General]\n"
        "cloud_last_modify_platform=mac\n"
        f"draft_create_time={seconds}\n"
        f"draft_last_edit_time={seconds}\n"
        "real_edit_keys=1\n"
        "real_edit_seconds=1\n",
        encoding="utf-8",
    )
    meta["draft_id"] = meta_id
    meta["draft_name"] = project["name"]
    meta["draft_root_path"] = str(folder.parent)
    meta["draft_fold_path"] = str(folder)
    meta["draft_cover"] = "draft_cover.jpg"
    meta["draft_timeline_materials_size_"] = len(project_json.encode("utf-8"))
    meta["tm_draft_create"] = created_us
    meta["tm_draft_modified"] = created_us
    meta["tm_duration"] = project["duration"]
    _write_json(folder / "draft_meta_info.json", meta)


def _ensure_capcut_closed():
    result = subprocess.run(
        ["pgrep", "-x", "CapCut"], capture_output=True, check=False,
    )
    if result.returncode == 0:
        raise RuntimeError("Close CapCut before generating a native draft")
    if result.returncode != 1:
        raise RuntimeError("Could not verify whether CapCut is closed")


def _write_registry(root, registry):
    fd, temporary = tempfile.mkstemp(
        dir=root, prefix=".root_meta_info-", suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(registry, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, Path(root) / "root_meta_info.json")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def create_mac98_draft(draft_folder, rendered_video, short_id, output_root,
                       projects_dir=None):
    output_folder = Path(draft_folder)
    rendered_video = Path(rendered_video)
    root = Path(projects_dir) if projects_dir else projects_root()
    if not rendered_video.is_file():
        raise FileNotFoundError(rendered_video)
    if not (output_folder / "draft_content.json").is_file():
        raise FileNotFoundError(output_folder / "draft_content.json")
    _ensure_capcut_closed()
    template = find_native_template(root)
    index_path = root / "root_meta_info.json"
    registry = _read_json(index_path)
    template_entry = next(
        (entry for entry in registry["all_draft_store"]
         if entry.get("draft_fold_path") == str(template)),
        None,
    )
    if template_entry is None:
        raise ValueError(f"Native CapCut template is not registered: {template}")

    generated = _read_json(output_folder / "draft_content.json")
    media_paths = {
        material["path"]
        for material in generated.get("materials", {}).get("videos", [])
        if material.get("path")
    }
    missing = sorted(path for path in media_paths if not Path(path).is_file())
    if missing:
        raise FileNotFoundError(f"CapCut source media is missing: {missing}")

    now_us = time.time_ns() // 1000
    native_info = _read_json(template / "draft_info.json")
    project = copy.deepcopy(native_info)
    project.update(generated)
    project.update({
        "id": str(uuid.uuid4()).upper(),
        "name": short_id,
        "version": native_info["version"],
        "new_version": NEW_VERSION,
        "platform": copy.deepcopy(native_info["platform"]),
        "last_modified_platform": copy.deepcopy(native_info["last_modified_platform"]),
    })
    meta_id = str(uuid.uuid4()).upper()
    meta = copy.deepcopy(_read_json(template / "draft_meta_info.json"))
    _copy_native_support(template, output_folder)
    _write_project(output_folder, template, project, meta, meta_id, now_us)
    subprocess.run([
        "ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(rendered_video),
        "-frames:v", "1", "-pix_fmt", "yuvj420p", "-y",
        str(output_folder / "draft_cover.jpg"),
    ], check=True)

    output_root = Path(output_root)
    date, job = output_root.parent.parent.name, output_root.parent.name
    app_name = f"{date}-{job}-{short_id}-mac98"
    app_folder = root / app_name
    if app_folder.exists():
        raise FileExistsError(f"CapCut project already exists: {app_folder}")
    shutil.copytree(output_folder, app_folder)

    installed = _read_json(app_folder / "draft_info.json")
    installed["name"] = app_name
    installed_json = json.dumps(installed, ensure_ascii=False, separators=(",", ":"))
    for filename in ("draft_info.json", "template-2.tmp", "draft_content.json",
                     "draft_info.json.bak"):
        (app_folder / filename).write_text(installed_json, encoding="utf-8")
    installed_legacy = _read_json(app_folder / "template.tmp")
    installed_legacy.update(installed)
    _write_json(app_folder / "template.tmp", installed_legacy, compact=True)
    timeline_folder = app_folder / "Timelines" / installed["id"]
    for filename in ("draft_info.json", "template-2.tmp", "draft_info.json.bak"):
        (timeline_folder / filename).write_text(installed_json, encoding="utf-8")
    _write_json(timeline_folder / "template.tmp", installed_legacy, compact=True)

    installed_meta = _read_json(app_folder / "draft_meta_info.json")
    installed_meta.update({
        "draft_name": app_name,
        "draft_root_path": str(root),
        "draft_fold_path": str(app_folder),
        "draft_timeline_materials_size_": len(installed_json.encode("utf-8")),
    })
    _write_json(app_folder / "draft_meta_info.json", installed_meta)
    size = len(installed_json.encode("utf-8"))

    entry = copy.deepcopy(template_entry)
    entry.update({
        "draft_cover": str(app_folder / "draft_cover.jpg"),
        "draft_fold_path": str(app_folder),
        "draft_id": meta_id,
        "draft_json_file": str(app_folder / "draft_info.json"),
        "draft_name": app_name,
        "draft_root_path": str(root),
        "draft_timeline_materials_size": size,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_draft_removed": 0,
        "tm_duration": installed["duration"],
    })
    registry["all_draft_store"].append(entry)
    _write_registry(root, registry)
    print("CapCut 9.8.0 draft registered:", app_folder)
