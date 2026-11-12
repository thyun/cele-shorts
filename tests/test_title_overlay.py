import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shorts"))


class TitleOverlayTests(unittest.TestCase):
    def test_title_overlay_does_not_draw_a_background_box(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps({"shorts": []}), encoding="utf-8")
            output = root / "output"
            png_dir = root / "renders"
            env = {
                "SHORTS_PLAN": str(plan_path),
                "SHORTS_SOURCE": str(root / "source.mp4"),
                "SHORTS_OUTPUT": str(output),
                "SHORTS_PNG": str(png_dir),
                "SHORTS_WORK": str(root / "work"),
            }
            spec = importlib.util.spec_from_file_location(
                "shorts_build_title_test", ROOT / "shorts" / "build.py"
            )
            module = importlib.util.module_from_spec(spec)
            with patch.dict(os.environ, env):
                spec.loader.exec_module(module)
                title_path = root / "title.png"
                module.title_png(title_path, {
                    "id": "test",
                    "title": "First line\nSecond line",
                    "title_highlights": ["First"],
                    "highlight_color": [0.0, 1.0, 0.0],
                    "source": "Channel",
                })

            title = Image.open(title_path).convert("RGBA")
            pixels = title.crop((0, 60, 1080, 350)).getdata()
            self.assertNotIn((175, 20, 50, 235), pixels)


if __name__ == "__main__":
    unittest.main()
