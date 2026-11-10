import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shorts"))
from narration import narration_clips


class NarrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        (self.work / "clip.mp4").touch()
        self.probe = {
            "format": {"duration": "2.5"},
            "streams": [
                {"codec_type": "video", "width": 1080, "height": 1920},
                {"codec_type": "audio"},
            ],
        }

    def clips(self, short):
        with patch("narration.subprocess.run") as run:
            run.return_value.stdout = json.dumps(self.probe)
            return narration_clips(short, self.work)

    def test_positions_are_independent(self):
        item = {"video": "clip.mp4", "text": "자막"}
        self.assertEqual(self.clips({"id": "test"}), {})
        for positions in (("intro",), ("outro",), ("intro", "outro")):
            short = {"id": "test", **{f"narration_{p}": item for p in positions}}
            clips = self.clips(short)
            self.assertEqual(set(clips), set(positions))
            self.assertTrue(all(clip["duration"] == 2.5 for clip in clips.values()))

    def test_invalid_input_is_rejected(self):
        for item in ({"video": "../outside.mp4", "text": "자막"},
                     {"video": "clip.mp4", "text": "  "}, None):
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.clips({"id": "test", "narration_intro": item})

    def test_duration_dimensions_and_audio_are_required(self):
        for field in ("short", "long", "dimensions", "audio"):
            with self.subTest(field=field):
                original = json.loads(json.dumps(self.probe))
                if field == "short":
                    self.probe["format"]["duration"] = "1.9"
                elif field == "long":
                    self.probe["format"]["duration"] = "4.1"
                elif field == "dimensions":
                    self.probe["streams"][0]["width"] = 720
                else:
                    self.probe["streams"].pop()
                with self.assertRaises(ValueError):
                    self.clips({"id": "test", "narration_outro": {
                        "video": "clip.mp4", "text": "자막",
                    }})
                self.probe = original


if __name__ == "__main__":
    unittest.main()
