import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shorts"))
from history import record_generation, update_history, video_id


class HistoryTests(unittest.TestCase):
    def test_url_variants_and_rejection(self):
        for url in ("https://youtu.be/IvaYUWFiLDg?t=12",
                    "https://www.youtube.com/watch?v=IvaYUWFiLDg&t=12s",
                    "https://www.youtube.com/shorts/IvaYUWFiLDg"):
            self.assertEqual(video_id(url), "IvaYUWFiLDg")
        for url in ("https://youtube.com.evil/watch?v=IvaYUWFiLDg",
                    "https://youtube.com/watch?v=bad", "https://youtube.com/playlist?list=x"):
            with self.assertRaises(ValueError):
                video_id(url)

    def test_reference_is_not_generation_and_records_are_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ref = {"url": "https://youtu.be/IvaYUWFiLDg", "role": "discovered", "record": "test.json"}
            update_history(root, [ref])
            data = update_history(root, [ref])
            entry = data["videos"]["IvaYUWFiLDg"]
            self.assertEqual(len(entry["references"]), 1)
            self.assertEqual(entry["generations"], [])

    def test_incomplete_render_is_not_recorded_and_revisions_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = {"source_url": "https://youtu.be/IvaYUWFiLDg",
                    "references": [{"url": "https://youtube.com/shorts/pcjpUReL5b0",
                                    "use": "Title structure only"}], "shorts": [
                {"id": "test", "title": "test", "source": "channel", "segments": [[1, 2, 0.5]]},
            ]}
            for job in ("original", "revision"):
                output = root / "output" / "2026-11-12" / job
                with self.assertRaises(FileNotFoundError):
                    record_generation(root, plan, output)
                draft = output / "capcut_drafts" / "test" / "draft_content.json"
                draft.parent.mkdir(parents=True)
                for path in (draft, output / "test.mp4", output / "test.srt"):
                    path.touch()
                if job == "revision":
                    (output / "upload-review.json").write_text(json.dumps({
                        "publication_status": "게시 전 확인 필요",
                        "videos": [{"id": "test", "content_verdict": "수정 후 재심"}],
                    }), encoding="utf-8")
                record_generation(root, plan, output)
                record_generation(root, plan, output)
            data = json.loads((root / "references" / "history.json").read_text())
            entry = data["videos"]["IvaYUWFiLDg"]
            self.assertEqual(len(entry["generations"]), 2)
            self.assertEqual(entry["generations"][0]["publication_status"], "unknown")
            self.assertEqual(entry["generations"][1]["publication_status"], "게시 전 확인 필요")
            self.assertEqual(entry["generations"][1]["review_verdicts"], {"test": "수정 후 재심"})
            reference = data["videos"]["pcjpUReL5b0"]
            self.assertEqual(reference["generations"], [])
            self.assertEqual(reference["references"][0]["role"], "creative_reference")
            self.assertEqual(reference["references"][0]["job"], "original")
            self.assertEqual(reference["references"][0]["use"], "Title structure only")
