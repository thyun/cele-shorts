import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shorts"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class RenderBoundaryTests(unittest.TestCase):
    def test_following_scene_does_not_leak_into_selected_segments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            subprocess.run([
                "ffmpeg", "-v", "error", "-n",
                "-f", "lavfi", "-i", "color=red:s=128x72:r=24000/1001:d=1.6",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-vf", "drawbox=color=blue:t=fill:enable='gte(t,0.5)*lt(t,1)'",
                "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source),
            ], check=True)
            short = {
                "id": "boundary", "title": "First line\nSecond line",
                "title_highlights": ["First"], "source": "Channel",
                "segments": [[0, 0.49, 0.5], [1.05, 1.4, 0.5]],
                "captions": [],
            }
            plan = root / "plan.json"
            plan.write_text(json.dumps({"shorts": [short]}), encoding="utf-8")
            spec = importlib.util.spec_from_file_location(
                "shorts_build_boundary_test", ROOT / "shorts/build.py",
            )
            module = importlib.util.module_from_spec(spec)
            with patch.dict(os.environ, {
                "SHORTS_PLAN": str(plan), "SHORTS_SOURCE": str(source),
                "SHORTS_OUTPUT": str(root / "output"),
                "SHORTS_PNG": str(root / "renders"), "SHORTS_WORK": str(root),
                "SHORTS_SPEED": "1.2", "SHORTS_END_FADE": "0.08",
            }):
                spec.loader.exec_module(module)
                module.build(short)
            result = root / "output/boundary.mp4"
            pixels = subprocess.check_output([
                "ffmpeg", "-v", "error", "-i", str(result), "-an",
                "-vf", "crop=2:2:540:960,format=rgb24",
                "-f", "rawvideo", "-",
            ])
            self.assertTrue(pixels)
            self.assertTrue(all(red > 200 and blue < 40
                                for red, blue in zip(pixels[0::3], pixels[2::3])),
                            "A blue frame from outside the selected intervals leaked")
            duration = float(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(result),
            ], text=True))
            self.assertAlmostEqual(duration, 0.7, delta=1 / 30)


if __name__ == "__main__":
    unittest.main()
