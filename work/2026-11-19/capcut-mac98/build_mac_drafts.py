import copy
import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
APP_DRAFTS = Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
OUTPUT = ROOT / "output/2026-11-17/sooyoung-story-final"
SOURCE = ROOT / "work/2026-11-17/sooyoung/long.mp4"
NATIVE = APP_DRAFTS / "1119 (1)"
WORK = Path(__file__).resolve().parent
ROOT_META = APP_DRAFTS / "root_meta_info.json"


def write_json(path, value, compact=False):
    kwargs = {"ensure_ascii": False}
    if compact:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = 2
    path.write_text(json.dumps(value, **kwargs) + ("" if compact else "\n"))


def main():
    if not APP_DRAFTS.is_dir() or not (NATIVE / "draft_info.json").is_file():
        raise FileNotFoundError("CapCut 9.8.0 native draft template was not found")
    if not ROOT_META.is_file():
        raise FileNotFoundError(ROOT_META)
    if subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0:
        raise RuntimeError("Close CapCut before installing generated drafts")

    native_info = json.loads((NATIVE / "draft_info.json").read_text())
    native_meta = json.loads((NATIVE / "draft_meta_info.json").read_text())
    registry = json.loads(ROOT_META.read_text())
    template_entry = next(
        entry for entry in registry["all_draft_store"]
        if entry["draft_fold_path"] == str(NATIVE)
    )
    manifest_path = WORK / "created-projects.json"
    previous = {}
    if manifest_path.is_file():
        previous = {
            entry["id"]: entry for entry in json.loads(manifest_path.read_text())
        }
    created = []
    now_us = time.time_ns() // 1000
    prepared = []
    for short_id in ("s1_vacation-cap", "s2_cream-selfcare"):
        source_json = OUTPUT / "capcut_drafts" / short_id / "draft_content.json"
        source_mp4 = OUTPUT / f"{short_id}.mp4"
        generated = json.loads(source_json.read_text())
        if not source_mp4.is_file():
            raise FileNotFoundError(source_mp4)
        broken_source = str(ROOT / "work/2026-11-17/sooyoung-story-final/long.mp4")
        for material in generated["materials"]["videos"]:
            if material["path"] == broken_source and not SOURCE.is_file():
                raise FileNotFoundError(SOURCE)
            if material["path"] == broken_source:
                material["path"] = str(SOURCE)
        media_paths = {m["path"] for m in generated["materials"]["videos"]}
        if any(not Path(path).is_file() for path in media_paths):
            raise FileNotFoundError(f"Missing media source for {short_id}: {media_paths}")

        folder_name = f"{short_id}-mac98"
        folder = APP_DRAFTS / folder_name
        if folder.exists() and not any(
            entry.get("draft_fold_path") == str(folder)
            for entry in registry["all_draft_store"]
        ):
            raise FileExistsError(f"Unregistered CapCut project already exists: {folder}")
        prepared.append((short_id, folder_name, folder, generated, source_mp4, media_paths))

    root_backup = WORK / "root_meta_info.before.json"
    if not root_backup.exists():
        shutil.copy2(ROOT_META, root_backup)

    for short_id, folder_name, folder, generated, source_mp4, media_paths in prepared:
        folder.mkdir(exist_ok=True)
        shutil.copytree(
            NATIVE,
            folder,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                "draft_info.json", "draft_info.json.bak", "draft_meta_info.json",
                "template-2.tmp", "template.tmp", "draft_cover.jpg", "Timelines",
            ),
        )

        project = copy.deepcopy(native_info)
        project.update(generated)
        old = previous.get(short_id, {})
        project["id"] = old.get("project_id", str(uuid.uuid4()).upper())
        project["name"] = folder_name
        project["version"] = native_info["version"]
        project["new_version"] = native_info["new_version"]
        project["platform"] = copy.deepcopy(native_info["platform"])
        project["last_modified_platform"] = copy.deepcopy(native_info["last_modified_platform"])

        project_json = json.dumps(project, ensure_ascii=False, separators=(",", ":"))
        (folder / "draft_info.json").write_text(project_json)
        (folder / "template-2.tmp").write_text(project_json)
        (folder / "draft_content.json").write_text(project_json)
        (folder / "draft_info.json.bak").write_text(project_json)

        legacy = json.loads((NATIVE / "template.tmp").read_text())
        legacy.update(project)
        write_json(folder / "template.tmp", legacy, compact=True)

        timeline_id = project["id"]
        timeline_dir = folder / "Timelines" / timeline_id
        timeline_dir.mkdir(parents=True, exist_ok=True)
        (timeline_dir / "draft_info.json").write_text(project_json)
        (timeline_dir / "template-2.tmp").write_text(project_json)
        (timeline_dir / "draft_info.json.bak").write_text(project_json)
        write_json(timeline_dir / "template.tmp", legacy, compact=True)
        for sidecar in ("attachment_editing.json", "attachment_pc_common.json"):
            shutil.copy2(NATIVE / sidecar, timeline_dir / sidecar)

        timeline_index = json.loads((NATIVE / "Timelines/project.json").read_text())
        timeline_index["id"] = timeline_id
        timeline_index["main_timeline_id"] = timeline_id
        timeline_index["create_time"] = now_us
        timeline_index["update_time"] = now_us
        for timeline in timeline_index["timelines"]:
            timeline["id"] = timeline_id
            timeline["name"] = "Timeline 01"
            timeline["create_time"] = now_us
            timeline["update_time"] = now_us
        write_json(folder / "Timelines/project.json", timeline_index, compact=True)

        layout = json.loads((NATIVE / "timeline_layout.json").read_text())
        for dock in layout.get("dockItems", []):
            dock["timelineIds"] = [timeline_id]
            dock["timelineNames"] = ["Timeline 01"]
        write_json(folder / "timeline_layout.json", layout, compact=True)
        settings_time = now_us // 1_000_000
        (folder / "draft_settings").write_text(
            "[General]\n"
            "cloud_last_modify_platform=mac\n"
            f"draft_create_time={settings_time}\n"
            f"draft_last_edit_time={settings_time}\n"
            "real_edit_keys=1\n"
            "real_edit_seconds=1\n"
        )

        meta = copy.deepcopy(native_meta)
        meta_id = old.get("draft_id", str(uuid.uuid4()).upper())
        meta.update({
            "draft_id": meta_id,
            "draft_name": folder_name,
            "draft_root_path": str(APP_DRAFTS),
            "draft_fold_path": str(folder),
            "draft_cover": "draft_cover.jpg",
            "draft_timeline_materials_size_": len(project_json.encode("utf-8")),
            "tm_draft_create": now_us,
            "tm_draft_modified": now_us,
            "tm_duration": project["duration"],
        })
        write_json(folder / "draft_meta_info.json", meta)
        subprocess.run([
            "ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(source_mp4),
            "-frames:v", "1", "-pix_fmt", "yuvj420p", "-y",
            str(folder / "draft_cover.jpg"),
        ], check=True)

        entry = next(
            (
                item for item in registry["all_draft_store"]
                if item.get("draft_fold_path") == str(folder)
            ),
            copy.deepcopy(template_entry),
        )
        entry.update({
            "draft_cover": str(folder / "draft_cover.jpg"),
            "draft_fold_path": str(folder),
            "draft_id": meta_id,
            "draft_json_file": str(folder / "draft_info.json"),
            "draft_name": folder_name,
            "draft_root_path": str(APP_DRAFTS),
            "draft_timeline_materials_size": len(project_json.encode("utf-8")),
            "tm_draft_create": now_us,
            "tm_draft_modified": now_us,
            "tm_draft_removed": 0,
            "tm_duration": project["duration"],
        })
        if not any(item.get("draft_fold_path") == str(folder) for item in registry["all_draft_store"]):
            registry["all_draft_store"].append(entry)
        else:
            for index, item in enumerate(registry["all_draft_store"]):
                if item.get("draft_fold_path") == str(folder):
                    registry["all_draft_store"][index] = entry
                    break
        created.append({
            "id": short_id,
            "folder": str(folder),
            "duration_us": project["duration"],
            "native_version": project["new_version"],
            "platform": project["platform"]["os"],
            "project_id": project["id"],
            "draft_id": meta_id,
            "media_paths": sorted(media_paths),
            "files": sorted(p.name for p in folder.iterdir()),
        })
        now_us += 1

    registry["draft_ids"] = json.loads(root_backup.read_text())["draft_ids"]
    temp = ROOT_META.with_name("root_meta_info.json.mac98.tmp")
    write_json(temp, registry)
    temp.replace(ROOT_META)
    manifest_path.write_text(
        json.dumps(created, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(created, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
