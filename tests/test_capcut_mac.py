import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shorts"))
from capcut_mac import create_mac98_draft


class MacCapCutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.projects = self.base / "capcut-projects"
        self.template = self.projects / "blank"
        self.template.mkdir(parents=True)
        self.output_root = self.base / "output" / "2026-11-19" / "job" / "capcut_drafts"
        self.draft = self.output_root / "s1"
        self.draft.mkdir(parents=True)
        self.source = self.base / "source.mp4"
        self.source.touch()
        self.preview = self.base / "preview.mp4"
        self.preview.touch()

        native_info = {
            "id": "TEMPLATE-ID",
            "version": 360000,
            "new_version": "193.0.0",
            "name": "",
            "duration": 0,
            "tracks": [],
            "platform": {"os": "mac", "app_version": "9.8.0"},
            "last_modified_platform": {"os": "mac", "app_version": "9.8.0"},
            "materials": {"videos": []},
        }
        meta = {"draft_id": "TEMPLATE-DRAFT-ID", "draft_name": "blank"}
        (self.template / "draft_info.json").write_text(json.dumps(native_info))
        (self.template / "draft_meta_info.json").write_text(json.dumps(meta))
        (self.template / "template.tmp").write_text(json.dumps(native_info))
        (self.template / "template-2.tmp").write_text(json.dumps(native_info))
        (self.template / "timeline_layout.json").write_text(json.dumps({
            "dockItems": [{"timelineIds": ["TEMPLATE-ID"], "timelineNames": ["Timeline 01"]}],
        }))
        (self.template / "attachment_editing.json").write_text("{}")
        (self.template / "attachment_pc_common.json").write_text("{}")
        timeline_root = self.template / "Timelines"
        timeline_root.mkdir()
        (timeline_root / "project.json").write_text(json.dumps({
            "id": "TEMPLATE-ID",
            "main_timeline_id": "TEMPLATE-ID",
            "timelines": [{"id": "TEMPLATE-ID", "name": "Timeline 01"}],
        }))
        (timeline_root / "TEMPLATE-ID").mkdir()
        (timeline_root / "TEMPLATE-ID" / "draft_info.json").write_text(json.dumps(native_info))
        (self.projects / "root_meta_info.json").write_text(json.dumps({
            "draft_ids": 3,
            "all_draft_store": [{
                "draft_fold_path": str(self.template),
                "draft_name": "blank",
                "draft_id": "TEMPLATE-DRAFT-ID",
            }],
        }))
        generated = {
            "id": "PYCAPCUT-ID",
            "version": 140000,
            "new_version": "140.0.0",
            "name": "s1",
            "duration": 12_000_000,
            "tracks": [{"id": "video-track"}],
            "platform": {"os": "windows"},
            "last_modified_platform": {"os": "windows"},
            "materials": {"videos": [{"path": str(self.source)}]},
        }
        (self.draft / "draft_content.json").write_text(json.dumps(generated))

    def fake_subprocess(self, command, **kwargs):
        if command[0] == "pgrep":
            return SimpleNamespace(returncode=1)
        Path(command[-1]).write_bytes(b"cover")
        return SimpleNamespace(returncode=0)

    def test_creates_native_output_and_registers_app_copy(self):
        with patch("capcut_mac.subprocess.run", side_effect=self.fake_subprocess):
            create_mac98_draft(
                self.draft, self.preview, "s1", self.output_root,
                projects_dir=self.projects,
            )

        output_info = json.loads((self.draft / "draft_info.json").read_text())
        self.assertEqual(output_info["platform"]["os"], "mac")
        self.assertEqual(output_info["new_version"], "193.0.0")
        self.assertNotEqual(output_info["id"], "PYCAPCUT-ID")
        self.assertTrue((self.draft / "Timelines" / output_info["id"] / "draft_info.json").is_file())
        self.assertEqual(
            json.loads((self.draft / "Timelines/project.json").read_text())["main_timeline_id"],
            output_info["id"],
        )

        registry = json.loads((self.projects / "root_meta_info.json").read_text())
        self.assertEqual(registry["draft_ids"], 3)
        self.assertEqual(len(registry["all_draft_store"]), 2)
        app_folder = Path(registry["all_draft_store"][-1]["draft_fold_path"])
        app_info = json.loads((app_folder / "draft_info.json").read_text())
        app_meta = json.loads((app_folder / "draft_meta_info.json").read_text())
        self.assertEqual(app_info["id"], output_info["id"])
        self.assertEqual(app_info["name"], "2026-11-19-job-s1-mac98")
        self.assertEqual(app_meta["draft_fold_path"], str(app_folder))
        self.assertTrue((app_folder / "draft_cover.jpg").is_file())

    def test_missing_source_media_is_rejected(self):
        content = json.loads((self.draft / "draft_content.json").read_text())
        content["materials"]["videos"][0]["path"] = str(self.base / "missing.mp4")
        (self.draft / "draft_content.json").write_text(json.dumps(content))
        with patch("capcut_mac.subprocess.run", side_effect=self.fake_subprocess):
            with self.assertRaises(FileNotFoundError):
                create_mac98_draft(
                    self.draft, self.preview, "s1", self.output_root,
                    projects_dir=self.projects,
                )
        self.assertEqual(len(json.loads(
            (self.projects / "root_meta_info.json").read_text()
        )["all_draft_store"]), 1)


if __name__ == "__main__":
    unittest.main()
