import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["SHORTS_DB_TABLE_PREFIX"] = "shorts_test_"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shorts"))
import history
from history import lookup, record_generation, record_uses, video_id


class VideoIdTests(unittest.TestCase):
    def test_url_variants_and_rejection(self):
        for url in ("https://youtu.be/IvaYUWFiLDg?t=12",
                    "https://www.youtube.com/watch?v=IvaYUWFiLDg&t=12s",
                    "https://www.youtube.com/shorts/IvaYUWFiLDg"):
            self.assertEqual(video_id(url), "IvaYUWFiLDg")
        for url in ("https://youtube.com.evil/watch?v=IvaYUWFiLDg",
                    "https://youtube.com/watch?v=bad", "https://youtube.com/playlist?list=x"):
            with self.assertRaises(ValueError):
                video_id(url)


@unittest.skipUnless((ROOT / ".env").is_file(), "DB 접속 정보(.env)가 없음")
class HistoryDbTests(unittest.TestCase):
    def setUp(self):
        self.conn = history.connect(ROOT)
        self._drop()
        self.conn.close()
        self.conn = history.connect(ROOT)

    def tearDown(self):
        self._drop()
        self.conn.close()

    def _drop(self):
        with self.conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {history.PREFIX}source_uses, {history.PREFIX}generations")

    def test_reference_is_not_generation_and_records_are_idempotent(self):
        ref = {"url": "https://youtu.be/IvaYUWFiLDg", "role": "discovered", "record": "test.json"}
        record_uses(self.conn, [ref])
        record_uses(self.conn, [ref])
        data = lookup(self.conn, "IvaYUWFiLDg")
        self.assertEqual(len(data["uses"]), 1)
        self.assertEqual(data["generations"], [])

    def test_incomplete_render_is_not_recorded_and_revisions_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = {"source_url": "https://youtu.be/IvaYUWFiLDg",
                    "permission": {"status": "user_confirmed"},
                    "references": [{"url": "https://youtube.com/shorts/pcjpUReL5b0"}], "shorts": [
                {"id": "test", "title": "test", "source": "channel", "segments": [[1, 2, 0.5]]},
            ]}
            for job in ("original", "revision"):
                output = root / "output" / "2026-11-12" / job
                with self.assertRaises(FileNotFoundError):
                    record_generation(root, plan, output, self.conn)
                draft = output / "capcut_drafts" / "test" / "draft_content.json"
                draft.parent.mkdir(parents=True)
                for path in (draft, output / "test.mp4", output / "test.srt"):
                    path.touch()
                if job == "revision":
                    (output / "upload-review.json").write_text(json.dumps({
                        "publication_status": "게시 전 확인 필요",
                        "videos": [{"id": "test", "content_verdict": "수정 후 재심"}],
                    }), encoding="utf-8")
                record_generation(root, plan, output, self.conn)
                record_generation(root, plan, output, self.conn)
            data = lookup(self.conn, "IvaYUWFiLDg")
            self.assertEqual(len(data["generations"]), 2)
            self.assertEqual(data["generations"][0]["publication_status"], "unknown")
            self.assertEqual(data["generations"][1]["publication_status"], "게시 전 확인 필요")
            self.assertEqual(data["generations"][1]["review_verdict"], "수정 후 재심")
            self.assertEqual(data["generations"][1]["segments"], [[1, 2, 0.5]])
            roles = {u["role"] for u in data["uses"]}
            self.assertEqual(roles, {"source"})
            self.assertEqual(len(lookup(self.conn, "pcjpUReL5b0")["uses"]), 2)
